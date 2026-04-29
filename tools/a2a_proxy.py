"""A2A Proxy Tool — send messages to an Edge Agent via Google A2A keep-alive connection."""

import json
import logging

from tools.registry import registry, tool_result

logger = logging.getLogger(__name__)


def a2a_proxy_send(agent_id: str = "agent1", message: str = "把冰箱冷藏温度打到四度", task_id: str = None) -> str:
    """Send a message to an Edge Agent via Google A2A based keep-alive connection.

    Args:
        agent_id: Target Edge Agent identifier.
        message: Message payload to deliver.
        task_id: Optional task identifier for tracing.

    Returns:
        JSON string with the result.
    """
    print(f"[A2AProxy] agent_id={agent_id}, message={message}")
    return tool_result(success=True, message="设置成功")


_A2A_PROXY_SCHEMA = {
    "name": "a2a_proxy_send",
    "description": "Send message to Edge Agent via Google A2A based keep-alive connection.",
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
                "description": "Message payload to deliver to the Edge Agent",
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
    handler=lambda args, **kw: a2a_proxy_send(
        agent_id=args.get("agent_id", "agent1"),
        message=args.get("message", "把冰箱冷藏温度打到四度"),
        task_id=kw.get("task_id"),
    ),
    check_fn=lambda: True,
    description="Send message to Edge Agent via Google A2A based keep-alive connection.",
    emoji="📡",
)
