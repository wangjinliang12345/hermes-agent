# Changes Summary

## 1. New Tool: A2A Proxy (`tools/a2a_proxy.py`)
- Implemented `a2a_proxy_send` tool to send messages to Edge Agents via Google A2A keep-alive connection.
- Parameters:
  - `agent_id` (string, default: `"agent1"`): Target Edge Agent identifier.
  - `message` (string, default: `"把冰箱冷藏温度打到四度"`): Message payload to deliver.
- Registered in `tools.registry` under the `"a2a"` toolset with emoji `📡`.
- **Note:** Current implementation is a stub — it prints the call parameters and returns a hardcoded success result. Full A2A protocol integration is pending.

## 2. Toolset Registration (`toolsets.py`)
- Added `a2a_proxy_send` to `_HERMES_CORE_TOOLS`.
- Added `"a2a"` toolset definition in `TOOLSETS`:
  - Description: "A2A Proxy — send messages to Edge Agents via Google A2A keep-alive connection"
  - Tools: `["a2a_proxy_send"]`

## 3. CLI Toolset Configuration (`hermes_cli/tools_config.py`)
- Added `("a2a", "📡 A2A Proxy", "send messages to Edge Agents via Google A2A")` to `CONFIGURABLE_TOOLSETS`.
- This makes the A2A toolset discoverable and toggleable in the CLI tools configuration menu.

## 4. New Skill: Fridge Control (`skills/smart-home/fridge-control/`)
- Added `SKILL.md` defining the `fridge-control` skill (v1.0.0).
- Provides a usage pattern wrapper around `a2a_proxy_send` specifically for refrigerator temperature control.
- Key conventions documented:
  - Always use `agent_id="agent1"` for fridge control.
  - Message format: `"把冰箱冷藏温度调到X度"` (Chinese).
  - Always return the full tool result to the user.
- Tagged with: `fridge`, `smart-home`, `a2a`, `temperature`.

## Files Changed
| Status | File |
|--------|------|
| Modified | `hermes_cli/tools_config.py` |
| Modified | `toolsets.py` |
| Untracked | `tools/a2a_proxy.py` |
| Untracked | `skills/smart-home/fridge-control/SKILL.md` |


## 5. A2A WebSocket Transport Integration

### 5.1 Environment Variables (`OPTIONAL_ENV_VARS` in `hermes_cli/config.py`)
- Registered 4 new env vars in `OPTIONAL_ENV_VARS`:
  - `A2A_WEBSOCKET_ENABLED` — whether to start the embedded WebSocket server.
  - `A2A_WEBSOCKET_HOST` — bind host (default: `0.0.0.0`).
  - `A2A_WEBSOCKET_PORT` — plain-text ws port (default: `8765`).
  - `A2A_WEBSOCKET_SECURE_PORT` — TLS wss port (default: `8766`).
- Users configure these in `~/.hermes/.env`.

### 5.2 `.env` Templates
- Updated both `/workspaces/hermes-agent/.env` and `/workspaces/hermes-agent/.env.example` with the A2A WebSocket section.

### 5.3 Dependencies (`pyproject.toml`)
- Added `protobuf>=5.29.5,<6`, `json-rpc>=1.15.0,<2`, and `websockets>=14.0,<17` to Hermes core dependencies so the embedded a2a SDK works out of the box.
- Installed the local `a2a-python-1.0.2` package into the Hermes venv via `uv pip install -e a2a-python-1.0.2/`.

### 5.4 Tool Rewrite (`tools/a2a_proxy.py`)
- **Removed** the hard-coded stub (`print` + `tool_result(success=True, message="设置成功")`).
- **Added** lazy-start `A2AWebSocketServer` (`_ensure_server_async`) bound to the env-configured host/port.
- **Added** real A2A request construction using `SendMessageRequest` protobuf + `json_format`.
- **Added** WebSocket routing via `_server.send_request(agent_id, "SendMessage", payload)`.
- Returns the **actual sub response** (extracted from `task.status.message.parts[0].text`).
- Graceful fallback when:
  - `A2A_WEBSOCKET_ENABLED` is not set or `false`.
  - a2a SDK dependencies are missing.
  - No WebSocket sub is connected.
- Registered with `is_async=True` so Hermes' `_run_async` bridge handles the sync/async boundary.

### 5.5 Documentation (`a2a-python-1.0.2/websocket.md`)
- Added **"端到端演示（End-to-End Demo）"** section in Chinese.
- Included run command, expected output, key points, and a quick copy-paste snippet.

### 5.6 Tests
- Updated `tests/tools/test_registry.py` (`TestBuiltinDiscovery`) to include `"tools.a2a_proxy"` in the expected built-in tool set.

## Files Changed
| Status | File |
|--------|------|
| Modified | `hermes_cli/config.py` |
| Modified | `hermes_cli/tools_config.py` |
| Modified | `toolsets.py` |
| Modified | `pyproject.toml` |
| Modified | `.env` |
| Modified | `.env.example` |
| Modified | `tests/tools/test_registry.py` |
| Modified | `a2a-python-1.0.2/websocket.md` |
| Untracked | `tools/a2a_proxy.py` |
| Untracked | `skills/smart-home/fridge-control/SKILL.md` |

## 6. A2A WebSocket 协议消息格式

### 6.1 Sub 接收到的请求（由 Hermes 发出）

```json
{
  "request_id": "fbab82ad-2a73-4d0f-8e74-e1e2323108ea",
  "method": "SendMessage",
  "payload": {
    "message": {
      "role": "ROLE_USER",
      "parts": [{"text": "把冰箱冷藏温度调到5度"}]
    }
  }
}
```

### 6.2 Sub 应回复的响应格式

```json
{
  "request_id": "fbab82ad-2a73-4d0f-8e74-e1e2323108ea",
  "task": {
    "id": "task-xxx",
    "status": {
      "state": "TASK_STATE_COMPLETED",
      "message": {
        "role": "ROLE_AGENT",
        "parts": [{"text": "已把冰箱冷藏温度设置为5度"}]
      }
    }
  }
}
```

**关键字段说明：**

| 字段 | 说明 |
|------|------|
| `request_id` | **必须原样带回**，server 靠它匹配等待中的 future |
| `task.status.state` | `"TASK_STATE_COMPLETED"` 表示成功；client 据此判断 `success=true` |
| `task.status.message.parts[0].text` | 实际返回给用户的文本内容 |

### 6.3 Python sub 端最小实现示例

```python
import asyncio, json, websockets

async def handler(websocket):
    async for message in websocket:
        data = json.loads(message)
        req_id = data.get("request_id")
        payload = data.get("payload", {})
        user_text = payload["message"]["parts"][0]["text"]

        response = {
            "request_id": req_id,
            "task": {
                "status": {
                    "state": "TASK_STATE_COMPLETED",
                    "message": {
                        "parts": [{"text": f"已完成：{user_text}"}]
                    }
                }
            }
        }
        await websocket.send(json.dumps(response))

asyncio.run(websockets.serve(handler, "127.0.0.1", 8765))
```

## Demo 在对话框里面输入冰箱相关控制后，会自动调用a2a_proxy工具a2a_proxy_send并输出工具调用结果
websocket_client.py 为websocket的 test client
● 把冰箱冷藏温度调到10度

────────────────────────────────────────

  ┊ ⚡ a2a_proxy   0.1s
[A2AProxy] _a2a_available=True, _ENABLED=True, _server=<A2AWebSocketServer ...>
[A2AProxy] will send to websocket client
 ─  ⚕ Hermes
  已成功将冰箱冷藏室温度设置为10度。
  工具执行结果：
json
{"success": true, "message": "Hello from WebSocket sub! You said: 把冰箱冷藏温度调到10度"}


websocket server启动 时候

2026-04-30 06:15:53,387 INFO tools.a2a_proxy: A2A WebSocket server pre-started eagerly on ws://0.0.0.0:8765


client连接websocket时
2026-04-30 06:16:08,001 INFO a2a.client.websocket_server: Registered new agent 63e633e5-27ff-4240-9fae-5d352d3cc508 for sub 127.0.0.1:54032
2026-04-30 06:16:08,001 INFO a2a.client.websocket_server: Sub connected: 127.0.0.1:54032 -> agent_id=63e633e5-27ff-4240-9fae-5d352d3cc508


用A2A工具发送 websocket请求(30s 超时)
[A2AProxy] _a2a_available=True, _ENABLED=True, _server=<a2a.client.websocket_server.A2AWebSocketServer object at 0x7e91ad198390>
[A2AProxy] will send to websocket client
  ┊ ⚡ a2a_proxy   19.9s




WebSocket client收到请求

[收到] {"request_id": "9b2b546c-f203-402e-af6e-98355184e4a5", "method": "SendMessage", "payload": {"message": {"role": "ROLE_USER", "parts": [{"text": "\u628a\u51b0\u7bb1\u51b7\u85cf\u6e29\u5ea6\u8c03\u523010\u5ea6"}]}}}

回复(requestid需要与 reqeust里的相同)

 {"request_id": "9b2b546c-f203-402e-af6e-98355184e4a5","task": {"id": "task-xxx", "status": {"state": "TASK_STATE_COMPLETED","message": {"role": "ROLE_AGENT","parts": [{"text": "已把冰箱冷藏温度设置好"}] } }}}




Hermes 打印
已把冰箱冷藏温度设置好 

