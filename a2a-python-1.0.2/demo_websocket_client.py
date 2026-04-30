"""Demo: Start A2AWebSocketServer and test with A2A Client.

Run this script from the a2a-python-1.0.2 directory:

    PYTHONPATH=src python demo_websocket_client.py

What it does:
1. Starts an A2AWebSocketServer on ws://127.0.0.1:18767
2. Spawns a mock agent sub that connects to the server
3. Builds an AgentCard with a WEBSOCKET interface
4. Uses ClientFactory + WebSocketTransport to send a message
5. Optionally demonstrates streaming
"""

import asyncio
import json

import websockets

from a2a.client.client_factory import ClientFactory
from a2a.client.client import ClientConfig
from a2a.client.websocket_server import A2AWebSocketServer
from a2a.types.a2a_pb2 import (
    AgentCard,
    AgentCapabilities,
    AgentInterface,
    SendMessageRequest,
)
from a2a.utils.constants import TransportProtocol


async def mock_agent_sub(
    server_host: str, server_port: int, ready_event: asyncio.Event
):
    """Mock A2A agent that connects to the WebSocket server and replies."""
    uri = f'ws://{server_host}:{server_port}'
    async with websockets.connect(uri) as ws:
        ready_event.set()
        print(f'[Sub] Connected to {uri}')
        async for message in ws:
            data = json.loads(message)
            request_id = data['request_id']
            method = data['method']
            payload = data.get('payload', {})
            print(f'[Sub] Received {method} (req={request_id})')

            user_text = (
                payload.get('message', {}).get('parts', [{}])[0].get('text')
                or 'no text'
            )

            if method == 'SendMessage':
                response = {
                    'request_id': request_id,
                    'payload': {
                        'task': {
                            'id': 'demo-task-sync',
                            'status': {
                                'state': 'TASK_STATE_COMPLETED',
                                'message': {
                                    'role': 'ROLE_AGENT',
                                    'parts': [
                                        {
                                            'text': (
                                                'Hello from WebSocket sub! '
                                                f'You said: {user_text}'
                                            ),
                                        }
                                    ],
                                },
                            },
                        },
                    },
                }
                await ws.send(json.dumps(response))
                print(f'[Sub] Replied to {method}')

            elif method == 'SendStreamingMessage':
                # Simulate 3 streaming chunks + 1 final
                for i in range(3):
                    chunk = {
                        'request_id': request_id,
                        'payload': {
                            'task': {
                                'id': 'demo-task-stream',
                                'status': {
                                    'state': 'TASK_STATE_WORKING',
                                    'message': {
                                        'role': 'ROLE_AGENT',
                                        'parts': [
                                            {'text': f'Streaming chunk {i + 1}'}
                                        ],
                                    },
                                },
                            },
                        },
                        'stream_done': False,
                    }
                    await ws.send(json.dumps(chunk))
                    await asyncio.sleep(0.05)

                final = {
                    'request_id': request_id,
                    'payload': {
                        'task': {
                            'id': 'demo-task-stream',
                            'status': {
                                'state': 'TASK_STATE_COMPLETED',
                                'message': {
                                    'role': 'ROLE_AGENT',
                                    'parts': [
                                        {'text': 'Stream finished'}
                                    ],
                                },
                            },
                        },
                    },
                    'stream_done': True,
                }
                await ws.send(json.dumps(final))
                print(f'[Sub] Replied to {method} (streaming)')

            else:
                # Generic echo for other methods
                response = {
                    'request_id': request_id,
                    'payload': {'echo': method},
                }
                await ws.send(json.dumps(response))
                print(f'[Sub] Echoed {method}')


async def main() -> None:
    host = '127.0.0.1'
    port = 18767

    # 1. Start the WebSocket server
    server = A2AWebSocketServer(host=host, port=port)
    await server.start()
    print(f'[Server] Started on ws://{host}:{port}')

    try:
        # 2. Start the mock agent sub in the background
        ready = asyncio.Event()
        sub_task = asyncio.create_task(
            mock_agent_sub(host, port, ready)
        )
        await asyncio.wait_for(ready.wait(), timeout=5.0)
        await asyncio.sleep(0.2)  # Let the server register the connection

        # 3. Discover the agent_id assigned to our sub
        assert len(server._connections) == 1, 'Expected exactly one sub'
        agent_id = list(server._connections.keys())[0]
        print(f'[Client] Discovered agent_id: {agent_id}')

        # 4. Build an AgentCard that advertises WEBSOCKET transport
        card = AgentCard(
            name='DemoWebSocketAgent',
            description='A demo agent reached via WebSocket',
            version='1.0',
            capabilities=AgentCapabilities(streaming=True),
            default_input_modes=['text'],
            default_output_modes=['text'],
            skills=[],
            supported_interfaces=[
                AgentInterface(
                    protocol_binding=TransportProtocol.WEBSOCKET,
                    url=agent_id,
                )
            ],
        )

        # 5. Configure the client to use the WebSocket server
        config = ClientConfig(
            streaming=True,
            supported_protocol_bindings=[TransportProtocol.WEBSOCKET],
            websocket_server=server,
        )

        # 6. Create the client via ClientFactory
        factory = ClientFactory(config)
        client = factory.create(card)
        print('[Client] Created A2A client with WebSocket transport')

        # 7. Non-streaming client test (config.streaming=False)
        non_stream_config = ClientConfig(
            streaming=False,
            supported_protocol_bindings=[TransportProtocol.WEBSOCKET],
            websocket_server=server,
        )
        non_stream_factory = ClientFactory(non_stream_config)
        non_stream_client = non_stream_factory.create(card)

        request = SendMessageRequest()
        request.message.role = 'ROLE_USER'
        part = request.message.parts.add()
        part.text = 'Hello WebSocket agent!'

        print('\n--- Non-streaming send_message ---')
        responses = []
        async for resp in non_stream_client.send_message(request):
            responses.append(resp)

        assert len(responses) == 1
        task = responses[0].task
        print(f'Task ID : {task.id}')
        print(f'State   : {task.status.state}')  # enum value number
        print(f'Reply   : {task.status.message.parts[0].text}')
        await non_stream_client.close()

        # 8. Streaming client test (config.streaming=True)
        stream_request = SendMessageRequest()
        stream_request.message.role = 'ROLE_USER'
        stream_part = stream_request.message.parts.add()
        stream_part.text = 'Stream me some data'

        print('\n--- Streaming send_message ---')
        chunk_count = 0
        async for resp in client.send_message(stream_request):
            chunk_count += 1
            t = resp.task
            print(
                f'Chunk {chunk_count}: state={t.status.state} | '
                f'text={t.status.message.parts[0].text}'
            )

        print(f'\nTotal stream chunks received: {chunk_count}')

        # 9. Cleanup
        await client.close()
        print('[Client] Closed')

        sub_task.cancel()
        try:
            await sub_task
        except asyncio.CancelledError:
            pass
        print('[Sub] Stopped')

    finally:
        await server.stop()
        print('[Server] Stopped')


if __name__ == '__main__':
    asyncio.run(main())
