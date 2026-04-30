"""WebSocket server for accepting A2A agent sub connections.

This module provides a WebSocket server that runs alongside the A2A client.
Subscribers (agent servers) connect to this server. Each connection is
identified by the remote IP and port, and assigned a unique agent ID.
The client can then route requests to a specific agent by its ID over the
existing WebSocket connection instead of using HTTP JSON-RPC.
"""

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import websockets
from websockets.server import WebSocketServerProtocol

logger = logging.getLogger(__name__)


class A2AWebSocketServer:
    """Manages WebSocket connections from A2A agent subs.

    Attributes:
        host: Host address to bind the WebSocket server.
        port: Port to bind the WebSocket server.
    """

    def __init__(self, host: str = '0.0.0.0', port: int = 8765):
        """Initializes the WebSocket server.

        Args:
            host: Host address to bind.
            port: Port to bind.
        """
        self.host = host
        self.port = port
        self._connections: dict[str, WebSocketServerProtocol] = {}
        self._agent_ids: dict[tuple[str, int], str] = {}
        self._pending_responses: dict[str, asyncio.Future] = {}
        self._pending_streams: dict[str, asyncio.Queue] = {}
        self._server = None

    def _get_agent_id(
        self, remote_ip: str, remote_port: int
    ) -> str:
        """Gets or creates an agent ID for a remote address.

        Args:
            remote_ip: Remote IP address.
            remote_port: Remote port.

        Returns:
            The agent ID associated with the remote address.
        """
        key = (remote_ip, remote_port)
        if key not in self._agent_ids:
            agent_id = str(uuid.uuid4())
            self._agent_ids[key] = agent_id
            logger.info(
                'Registered new agent %s for sub %s:%s',
                agent_id, remote_ip, remote_port
            )
        return self._agent_ids[key]

    async def _handler(
        self, websocket: WebSocketServerProtocol
    ) -> None:
        """Handles an incoming WebSocket connection.

        Args:
            websocket: The WebSocket protocol instance.
        """
        remote_ip = websocket.remote_address[0]
        remote_port = websocket.remote_address[1]
        agent_id = self._get_agent_id(remote_ip, remote_port)
        self._connections[agent_id] = websocket
        logger.info(
            'Sub connected: %s:%s -> agent_id=%s',
            remote_ip, remote_port, agent_id
        )

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    logger.warning('Received invalid JSON: %s', message)
                    continue

                request_id = data.get('request_id')
                logger.info(
                    'WS recv: request_id=%s method=%s',
                    request_id, data.get('method'),
                )
                if (
                    request_id
                    and request_id in self._pending_responses
                ):
                    future = self._pending_responses.pop(request_id)
                    if not future.done():
                        logger.info(
                            'WS response: request_id=%s payload=%s',
                            request_id, data.get('payload'),
                        )
                        future.set_result(data)
                elif (
                    request_id
                    and request_id in self._pending_streams
                ):
                    logger.info(
                        'WS stream chunk: request_id=%s payload=%s',
                        request_id, data.get('payload'),
                    )
                    self._pending_streams[request_id].put_nowait(data)
        except websockets.exceptions.ConnectionClosed:
            logger.info('Connection closed for agent_id=%s', agent_id)
        finally:
            self._connections.pop(agent_id, None)
            logger.info('Sub disconnected: agent_id=%s', agent_id)

    async def start(self) -> None:
        """Starts the WebSocket server."""
        self._server = await websockets.serve(
            self._handler, self.host, self.port
        )
        logger.info(
            'A2A WebSocket server started on ws://%s:%s',
            self.host, self.port
        )

    async def stop(self) -> None:
        """Stops the WebSocket server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info('A2A WebSocket server stopped')

    async def send_request(
        self,
        agent_id: str,
        method: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Sends a request to an agent and waits for a response.

        Args:
            agent_id: The target agent ID.
            method: The A2A method name (e.g. 'SendMessage').
            payload: The protobuf message as a dictionary.

        Returns:
            The response payload dictionary.

        Raises:
            RuntimeError: If no connection exists for the agent ID.
            asyncio.TimeoutError: If the response times out.
        """
        if agent_id not in self._connections:
            raise RuntimeError(
                f'No websocket connection for agent_id={agent_id}'
            )

        request_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        self._pending_responses[request_id] = future

        message = json.dumps({
            'request_id': request_id,
            'method': method,
            'payload': payload,
        })

        try:
            logger.info(
                'WS send: agent_id=%s request_id=%s method=%s payload=%s',
                agent_id, request_id, method, payload,
            )
            await self._connections[agent_id].send(message)
            response_data = await asyncio.wait_for(
                future, timeout=30.0
            )
            logger.info(
                'WS received: agent_id=%s request_id=%s response=%s',
                agent_id, request_id, response_data.get('payload', response_data),
            )
            return response_data.get('payload', response_data)
        finally:
            self._pending_responses.pop(request_id, None)

    async def send_stream_request(
        self,
        agent_id: str,
        method: str,
        payload: dict[str, Any],
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Sends a streaming request to an agent and yields responses.

        Args:
            agent_id: The target agent ID.
            method: The A2A method name (e.g. 'SendStreamingMessage').
            payload: The protobuf message as a dictionary.

        Yields:
            Response payload dictionaries as they arrive.

        Raises:
            RuntimeError: If no connection exists for the agent ID.
        """
        if agent_id not in self._connections:
            raise RuntimeError(
                f'No websocket connection for agent_id={agent_id}'
            )

        request_id = str(uuid.uuid4())
        queue: asyncio.Queue = asyncio.Queue()
        self._pending_streams[request_id] = queue

        message = json.dumps({
            'request_id': request_id,
            'method': method,
            'payload': payload,
        })

        logger.info(
            'WS stream send: agent_id=%s request_id=%s method=%s payload=%s',
            agent_id, request_id, method, payload,
        )
        await self._connections[agent_id].send(message)

        try:
            while True:
                try:
                    data = await asyncio.wait_for(
                        queue.get(), timeout=60.0
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        'Stream timeout for agent_id=%s request_id=%s',
                        agent_id, request_id
                    )
                    break

                logger.info(
                    'WS stream received: agent_id=%s request_id=%s chunk=%s',
                    agent_id, request_id, data.get('payload', data),
                )
                yield data.get('payload', data)
                if data.get('stream_done'):
                    break
        finally:
            self._pending_streams.pop(request_id, None)
