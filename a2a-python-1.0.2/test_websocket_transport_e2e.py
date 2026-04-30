"""End-to-end test for WebSocket transport with ClientFactory."""

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
    """Simulates an A2A agent sub."""
    uri = f'ws://{server_host}:{server_port}'
    async with websockets.connect(uri) as ws:
        ready_event.set()
        async for message in ws:
            data = json.loads(message)
            request_id = data['request_id']
            method = data['method']
            payload = data['payload']

            if method == 'SendMessage':
                response = {
                    'request_id': request_id,
                    'payload': {
                        'task': {
                            'id': 'ws-task-1',
                            'status': {
                                'state': 'TASK_STATE_COMPLETED',
                                'message': {
                                    'role': 'ROLE_AGENT',
                                    'parts': [
                                        {
                                            'text': 'Hello from WebSocket sub',
                                        }
                                    ],
                                },
                            },
                        },
                    },
                }
                await ws.send(json.dumps(response))
            elif method == 'SendStreamingMessage':
                final = {
                    'request_id': request_id,
                    'payload': {
                        'task': {
                            'id': 'ws-task-1',
                            'status': {
                                'state': 'TASK_STATE_COMPLETED',
                                'message': {
                                    'role': 'ROLE_AGENT',
                                    'parts': [
                                        {
                                            'text': 'stream done',
                                        }
                                    ],
                                },
                            },
                        },
                    },
                    'stream_done': True,
                }
                await ws.send(json.dumps(final))


async def test_websocket_transport_e2e():
    """Tests ClientFactory + WebSocketTransport end-to-end."""
    server = A2AWebSocketServer(host='127.0.0.1', port=18766)
    await server.start()
    await asyncio.sleep(0.1)

    try:
        ready = asyncio.Event()
        sub_task = asyncio.create_task(
            mock_agent_sub('127.0.0.1', 18766, ready)
        )
        await asyncio.wait_for(ready.wait(), timeout=2.0)
        await asyncio.sleep(0.1)

        agent_id = list(server._connections.keys())[0]
        print(f'Sub connected with agent_id: {agent_id}')

        # Build an AgentCard that uses WEBSOCKET transport
        card = AgentCard(
            name='TestAgent',
            description='Test agent via WebSocket',
            version='1.0',
            capabilities=AgentCapabilities(streaming=False),
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

        config = ClientConfig(
            streaming=False,
            supported_protocol_bindings=[TransportProtocol.WEBSOCKET],
            websocket_server=server,
        )
        factory = ClientFactory(config)
        client = factory.create(card)

        # Build a simple SendMessageRequest
        request = SendMessageRequest()
        msg = request.message
        msg.role = 'ROLE_USER'
        part = msg.parts.add()
        part.text = 'Hello agent'

        # Send message
        responses = []
        async for resp in client.send_message(request):
            responses.append(resp)

        assert len(responses) == 1
        task = responses[0].task
        assert task.id == 'ws-task-1'
        assert task.status.state == 3  # TASK_STATE_COMPLETED
        print(f'Task response: {task.status.message.parts[0].text}')

        await client.close()
        print('WebSocket transport E2E test passed!')

        sub_task.cancel()
        try:
            await sub_task
        except asyncio.CancelledError:
            pass
    finally:
        await server.stop()


if __name__ == '__main__':
    asyncio.run(test_websocket_transport_e2e())
