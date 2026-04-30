import asyncio
import websockets
import sys


async def receive_messages(websocket):
    """持续接收并打印服务器消息"""
    try:
        async for message in websocket:
            print(f"\n[收到] {message}")
            print("> ", end="", flush=True)
    except websockets.exceptions.ConnectionClosed:
        print("\n[连接已关闭]")


async def send_messages(websocket):
    """从控制台读取输入并发送"""
    loop = asyncio.get_running_loop()
    while True:
        try:
            # 在 executor 中运行阻塞的 input()
            message = await loop.run_in_executor(None, input, "> ")
            if message.strip() == "":
                continue
            if message.lower() in ("quit", "exit"):
                print("[退出中...]")
                break
            await websocket.send(message)
        except EOFError:
            print("\n[输入结束]")
            break
        except websockets.exceptions.ConnectionClosed:
            print("\n[连接已关闭，无法发送]")
            break


async def main():
    uri = "ws://127.0.0.1:8765"
    print(f"正在连接到 {uri} ...")
    try:
        async with websockets.connect(uri) as websocket:
            print("[已连接] 输入消息并按回车发送，输入 quit/exit 退出\n")
            # 并发运行接收和发送任务
            receive_task = asyncio.create_task(receive_messages(websocket))
            send_task = asyncio.create_task(send_messages(websocket))

            # 等待任意一个任务结束（比如用户输入exit或连接断开）
            done, pending = await asyncio.wait(
                [receive_task, send_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # 取消剩余任务
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
    except ConnectionRefusedError:
        print(f"[错误] 无法连接到 {uri}，请确保服务端已启动")
        sys.exit(1)
    except Exception as e:
        print(f"[错误] {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[被用户中断]")
