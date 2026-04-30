"""WebSocket transport for the A2A client.

This transport sends A2A requests over WebSocket connections managed by
A2AWebSocketServer instead of using HTTP JSON-RPC.
"""

import logging
from collections.abc import AsyncGenerator
from typing import Any

from google.protobuf import json_format

from a2a.client.client import ClientCallContext
from a2a.client.errors import A2AClientError
from a2a.client.transports.base import ClientTransport
from a2a.client.websocket_server import A2AWebSocketServer
from a2a.types.a2a_pb2 import (
    AgentCard,
    CancelTaskRequest,
    DeleteTaskPushNotificationConfigRequest,
    GetExtendedAgentCardRequest,
    GetTaskPushNotificationConfigRequest,
    GetTaskRequest,
    ListTaskPushNotificationConfigsRequest,
    ListTaskPushNotificationConfigsResponse,
    ListTasksRequest,
    ListTasksResponse,
    SendMessageRequest,
    SendMessageResponse,
    StreamResponse,
    SubscribeToTaskRequest,
    Task,
    TaskPushNotificationConfig,
)
from a2a.utils.errors import JSON_RPC_ERROR_CODE_MAP

logger = logging.getLogger(__name__)

_JSON_RPC_ERROR_CODE_TO_A2A_ERROR = {
    code: error_type for error_type, code in JSON_RPC_ERROR_CODE_MAP.items()
}


class WebSocketTransport(ClientTransport):
    """A WebSocket transport for the A2A client.

    Routes requests to agents via an A2AWebSocketServer using agent IDs.
    """

    def __init__(
        self,
        agent_card: AgentCard,
        url: str,
        websocket_server: A2AWebSocketServer,
    ):
        """Initializes the WebSocketTransport.

        Args:
            agent_card: The agent card.
            url: The agent ID used to route messages via the WebSocket server.
            websocket_server: The WebSocket server managing sub connections.
        """
        self.agent_card = agent_card
        self.agent_id = url
        self.websocket_server = websocket_server

    async def send_message(
        self,
        request: SendMessageRequest,
        *,
        context: ClientCallContext | None = None,
    ) -> SendMessageResponse:
        """Sends a non-streaming message request to the agent."""
        payload = json_format.MessageToDict(request)
        response_data = await self.websocket_server.send_request(
            self.agent_id, 'SendMessage', payload
        )
        response: SendMessageResponse = json_format.ParseDict(
            response_data, SendMessageResponse()
        )
        return response

    async def send_message_streaming(
        self,
        request: SendMessageRequest,
        *,
        context: ClientCallContext | None = None,
    ) -> AsyncGenerator[StreamResponse]:
        """Sends a streaming message request and yields responses."""
        payload = json_format.MessageToDict(request)
        async for event in self.websocket_server.send_stream_request(
            self.agent_id, 'SendStreamingMessage', payload
        ):
            response: StreamResponse = json_format.ParseDict(
                event, StreamResponse()
            )
            yield response

    async def get_task(
        self,
        request: GetTaskRequest,
        *,
        context: ClientCallContext | None = None,
    ) -> Task:
        """Retrieves the current state and history of a specific task."""
        payload = json_format.MessageToDict(request)
        response_data = await self.websocket_server.send_request(
            self.agent_id, 'GetTask', payload
        )
        response: Task = json_format.ParseDict(response_data, Task())
        return response

    async def list_tasks(
        self,
        request: ListTasksRequest,
        *,
        context: ClientCallContext | None = None,
    ) -> ListTasksResponse:
        """Retrieves tasks for an agent."""
        payload = json_format.MessageToDict(request)
        response_data = await self.websocket_server.send_request(
            self.agent_id, 'ListTasks', payload
        )
        response: ListTasksResponse = json_format.ParseDict(
            response_data, ListTasksResponse()
        )
        return response

    async def cancel_task(
        self,
        request: CancelTaskRequest,
        *,
        context: ClientCallContext | None = None,
    ) -> Task:
        """Requests the agent to cancel a specific task."""
        payload = json_format.MessageToDict(request)
        response_data = await self.websocket_server.send_request(
            self.agent_id, 'CancelTask', payload
        )
        response: Task = json_format.ParseDict(response_data, Task())
        return response

    async def create_task_push_notification_config(
        self,
        request: TaskPushNotificationConfig,
        *,
        context: ClientCallContext | None = None,
    ) -> TaskPushNotificationConfig:
        """Sets or updates push notification configuration for a task."""
        payload = json_format.MessageToDict(request)
        response_data = await self.websocket_server.send_request(
            self.agent_id, 'CreateTaskPushNotificationConfig', payload
        )
        response: TaskPushNotificationConfig = json_format.ParseDict(
            response_data, TaskPushNotificationConfig()
        )
        return response

    async def get_task_push_notification_config(
        self,
        request: GetTaskPushNotificationConfigRequest,
        *,
        context: ClientCallContext | None = None,
    ) -> TaskPushNotificationConfig:
        """Retrieves push notification configuration for a task."""
        payload = json_format.MessageToDict(request)
        response_data = await self.websocket_server.send_request(
            self.agent_id, 'GetTaskPushNotificationConfig', payload
        )
        response: TaskPushNotificationConfig = json_format.ParseDict(
            response_data, TaskPushNotificationConfig()
        )
        return response

    async def list_task_push_notification_configs(
        self,
        request: ListTaskPushNotificationConfigsRequest,
        *,
        context: ClientCallContext | None = None,
    ) -> ListTaskPushNotificationConfigsResponse:
        """Lists push notification configurations for a task."""
        payload = json_format.MessageToDict(request)
        response_data = await self.websocket_server.send_request(
            self.agent_id, 'ListTaskPushNotificationConfigs', payload
        )
        response: ListTaskPushNotificationConfigsResponse = (
            json_format.ParseDict(
                response_data, ListTaskPushNotificationConfigsResponse()
            )
        )
        return response

    async def delete_task_push_notification_config(
        self,
        request: DeleteTaskPushNotificationConfigRequest,
        *,
        context: ClientCallContext | None = None,
    ) -> None:
        """Deletes push notification configuration for a task."""
        payload = json_format.MessageToDict(request)
        await self.websocket_server.send_request(
            self.agent_id, 'DeleteTaskPushNotificationConfig', payload
        )

    async def subscribe(
        self,
        request: SubscribeToTaskRequest,
        *,
        context: ClientCallContext | None = None,
    ) -> AsyncGenerator[StreamResponse]:
        """Reconnects to get task updates."""
        payload = json_format.MessageToDict(request)
        async for event in self.websocket_server.send_stream_request(
            self.agent_id, 'SubscribeToTask', payload
        ):
            response: StreamResponse = json_format.ParseDict(
                event, StreamResponse()
            )
            yield response

    async def get_extended_agent_card(
        self,
        request: GetExtendedAgentCardRequest,
        *,
        context: ClientCallContext | None = None,
    ) -> AgentCard:
        """Retrieves the agent's card."""
        card = self.agent_card
        if not card.capabilities.extended_agent_card:
            return card

        payload = json_format.MessageToDict(request)
        response_data = await self.websocket_server.send_request(
            self.agent_id, 'GetExtendedAgentCard', payload
        )
        response: AgentCard = json_format.ParseDict(
            response_data, AgentCard()
        )
        return response

    async def close(self) -> None:
        """No-op: WebSocket server lifecycle is managed externally."""
        pass

    def _create_jsonrpc_error(
        self, error_dict: dict[str, Any]
    ) -> Exception:
        """Creates the appropriate A2AError from an error dictionary."""
        code = error_dict.get('code')
        message = error_dict.get('message', str(error_dict))
        data = error_dict.get('data')

        if (
            isinstance(code, int)
            and code in _JSON_RPC_ERROR_CODE_TO_A2A_ERROR
        ):
            return _JSON_RPC_ERROR_CODE_TO_A2A_ERROR[code](
                message, data=data
            )

        return A2AClientError(f'Error {code}: {message}')
