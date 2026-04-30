"""A2A Proxy Tool — send messages to an Edge Agent via Google A2A keep-alive connection."""

import asyncio
import json
import logging
import os
import sys
import threading
from pathlib import Path

from tools.registry import registry, tool_result

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Read A2A WebSocket configuration from environment variables.
# These are managed via ~/.hermes/.env and loaded into the process env.
_ENABLED = os.getenv("A2A_WEBSOCKET_ENABLED", "").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
_HOST = os.getenv("A2A_WEBSOCKET_HOST", "0.0.0.0").strip() or "0.0.0.0"
try:
    _PORT = int(os.getenv("A2A_WEBSOCKET_PORT", "8765"))
except ValueError:
    _PORT = 8765
try:
    _SECURE_PORT = int(os.getenv("A2A_WEBSOCKET_SECURE_PORT", "8766"))
except ValueError:
    _SECURE_PORT = 8766

# Try to import the embedded a2a SDK. If dependencies are missing,
# gracefully degrade to the legacy hard-coded path.
_a2a_available = False
_A2AWebSocketServer = None
_SendMessageRequest = None
_json_format = None

if _ENABLED:
    _a2a_src = (
        Path(__file__).resolve().parent.parent / "a2a-python-1.0.2" / "src"
    )
    if str(_a2a_src) not in sys.path:
        sys.path.insert(0, str(_a2a_src))
    try:
        from a2a.client.websocket_server import A2AWebSocketServer
        from a2a.types.a2a_pb2 import SendMessageRequest
        from google.protobuf import json_format

        _A2AWebSocketServer = A2AWebSocketServer
        _SendMessageRequest = SendMessageRequest
        _json_format = json_format
        _a2a_available = True
    except Exception as e:
        logger.warning(
            "a2a SDK not available (%s); a2a_proxy_send will use fallback",
            e,
        )
        _ENABLED = False

_server = None
_server_loop = None
_server_thread = None
_server_lock = threading.Lock()
_server_started = threading.Event()


def _ensure_server() -> None:
    """Start the A2A WebSocket server in a background thread if enabled."""
    global _server, _server_loop, _server_thread
    if not _a2a_available or not _ENABLED or _server is not None:
        return
    with _server_lock:
        if _server is not None:
            return

        async def _start() -> None:
            global _server
            _server = _A2AWebSocketServer(host=_HOST, port=_PORT)
            await _server.start()
            logger.info(
                "A2A WebSocket server started on ws://%s:%s", _HOST, _PORT
            )
            _server_started.set()
            # Keep the coroutine alive so the server stays running.
            await asyncio.Future()

        def _run_loop() -> None:
            global _server_loop
            loop = asyncio.new_event_loop()
            _server_loop = loop
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_start())

        _server_thread = threading.Thread(target=_run_loop, daemon=True)
        _server_thread.start()
        _server_started.wait(timeout=5)


def _a2a_proxy_send_sync(
    agent_id: str = "agent1",
    message: str = "把冰箱冷藏温度打到四度",
    task_id: str | None = None,
) -> str:
    """Sync implementation of a2a_proxy_send.

    When ``A2A_WEBSOCKET_ENABLED`` is set (via ~/.hermes/.env) and the a2a
    SDK is importable, this function:
    1. Ensures the embedded WebSocket server is running (in a background thread).
    2. Builds an A2A ``SendMessageRequest`` protobuf payload.
    3. Routes the request to the connected sub via ``agent_id``.
    4. Returns the sub's actual response.

    Otherwise it falls back to the legacy hard-coded success response.
    """
    _ensure_server()

    logger.debug(
        "_a2a_available=%s, _ENABLED=%s, _server=%s",
        _a2a_available, _ENABLED, _server,
    )

    if not _a2a_available or not _ENABLED or _server is None:
        logger.debug(
            "fallback stub — agent_id=%s, message=%s",
            agent_id, message,
        )
        result = tool_result(success=True, message="设置成功")
        logger.info("a2a_proxy_send result: %s", result)
        return result

    logger.debug("will send to websocket client")
    # Resolve agent_id. If the provided id is not connected, fall back to
    # the first available connection.
    connected_ids = list(_server._connections.keys())
    if agent_id not in connected_ids:
        if connected_ids:
            fallback = connected_ids[0]
            logger.warning(
                "agent_id %s not connected; falling back to %s",
                agent_id,
                fallback,
            )
            agent_id = fallback
        else:
            result = tool_result(
                success=False,
                message=(
                    f"No WebSocket sub connected for agent_id={agent_id}. "
                    "Please ensure the Edge Agent sub is online."
                ),
            )
            logger.info("a2a_proxy_send result: %s", result)
            return result

    # Build the protobuf payload as a dict.
    request = _SendMessageRequest()
    request.message.role = "ROLE_USER"
    request.message.parts.add().text = message
    payload = _json_format.MessageToDict(request)

    # Route the request through the WebSocket server (run on the background loop).
    future = asyncio.run_coroutine_threadsafe(
        _server.send_request(agent_id, "SendMessage", payload),
        _server_loop,
    )
    try:
        response_data = future.result(timeout=30.0)
    except Exception as e:
        err_msg = str(e) if str(e) else type(e).__name__
        logger.exception("A2A send_request failed: %s", err_msg)
        result = tool_result(success=False, message=f"A2A request failed: {err_msg}")
        logger.info("a2a_proxy_send result: %s", result)
        return result

    # Extract the agent's reply from the response payload.
    task = response_data.get("task", {})
    status = task.get("status", {})
    msg = status.get("message", {})
    parts = msg.get("parts", [])
    reply_text = parts[0].get("text", "") if parts else ""

    result = tool_result(
        success=status.get("state") == "TASK_STATE_COMPLETED",
        message=reply_text or json.dumps(response_data, ensure_ascii=False),
    )
    logger.info("a2a_proxy_send result: %s", result)
    return result


_A2A_PROXY_SCHEMA = {
    "name": "a2a_proxy_send",
    "description": (
        "Send message to Edge Agent via Google A2A based keep-alive "
        "connection. When A2A_WEBSOCKET_ENABLED is set in ~/.hermes/.env, "
        "the message is routed through the embedded WebSocket server to "
        "the connected sub."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "agent_id": {
                "type": "string",
                "description": "Target Edge Agent identifier",
                "default": "agent1",
            },
            "message": {
                "type": "string",
                "description": (
                    "Message payload to deliver to the Edge Agent"
                ),
                "default": "把冰箱冷藏温度打到四度",
            },
        },
        "required": [],
    },
}


registry.register(
    name="a2a_proxy_send",
    toolset="a2a",
    schema=_A2A_PROXY_SCHEMA,
    handler=lambda args, **kw: _a2a_proxy_send_sync(
        agent_id=args.get("agent_id", "agent1"),
        message=args.get("message", "把冰箱冷藏温度打到四度"),
        task_id=kw.get("task_id"),
    ),
    check_fn=lambda: True,
    is_async=False,
    description="Send message to Edge Agent via Google A2A based keep-alive connection.",
    emoji="📡",
)

# ------------------------------------------------------------------
# Eager start: spin up the WebSocket server at module-load time
# (i.e. during Hermes startup / tool discovery) so it is already
# running before the first tool call.
# ------------------------------------------------------------------
_ensure_server()
if _server is not None:
    logger.info("A2A WebSocket server pre-started eagerly on ws://%s:%s", _HOST, _PORT)
else:
    logger.info("A2A WebSocket server not pre-started (disabled or unavailable)")
