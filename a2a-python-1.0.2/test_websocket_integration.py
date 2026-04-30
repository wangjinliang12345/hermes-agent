"""Integration test for WebSocket server and transport."""

import asyncio
import json

import websockets

from a2a.client.websocket_server import A2AWebSocketServer


async def mock_agent_sub(
    server_host: str, server_port: int, ready_event: asyncio.Event
):
    """Simulates an A2A agent sub connecting to the WebSocket server."""
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
                            'id': payload.get('task_id', 'task-1'),
                            'status': {
                                'state': 'COMPLETED',
                                'message': {'role': 'agent', 'parts': [{'type': 'text', 'text': 'Hello from sub'}]},
                            },
                        },
                    },
                }
                await ws.send(json.dumps(response))
            elif method == 'SendStreamingMessage':
                for i in range(3):
                    response = {
                        'request_id': request_id,
                        'payload': {
                            'task': {
                                'id': payload.get('task_id', 'task-1'),
                                'status': {
                                    'state': 'WORKING',
                                    'message': {'role': 'agent', 'parts': [{'type': 'text', 'text': f'chunk {i}'}]},
                                },
                            },
                        },
                        'stream_done': False,
                    }
                    await ws.send(json.dumps(response))
                # Final message
                final = {
                    'request_id': request_id,
                    'payload': {
                        'task': {
                            'id': payload.get('task_id', 'task-1'),
                            'status': {
                                'state': 'COMPLETED',
                                'message': {'role': 'agent', 'parts': [{'type': 'text', 'text': 'done'}]},
                            },
                        },
                    },
                    'stream_done': True,
                }
                await ws.send(json.dumps(final))


async def test_websocket_server():
    """Tests basic request/response and streaming via WebSocket server."""
    server = A2AWebSocketServer(host='127.0.0.1', port=18765)
    await server.start()
    await asyncio.sleep(0.1)

    try:
        ready = asyncio.Event()
        sub_task = asyncio.create_task(
            mock_agent_sub('127.0.0.1', 18765, ready)
        )
        await asyncio.wait_for(ready.wait(), timeout=2.0)
        await asyncio.sleep(0.1)

        # Find the agent_id for the connected sub
        assert len(server._connections) == 1
        agent_id = list(server._connections.keys())[0]
        print(f'Agent connected with ID: {agent_id}')

        # Test send_request
        response = await server.send_request(
            agent_id, 'SendMessage', {'task_id': 't-123'}
        )
        print(f'Response: {response}')
        assert response['task']['id'] == 't-123'
        assert response['task']['status']['state'] == 'COMPLETED'

        # Test send_stream_request
        chunks = []
        async for event in server.send_stream_request(
            agent_id, 'SendStreamingMessage', {'task_id': 't-456'}
        ):
            chunks.append(event)
        print(f'Stream chunks: {len(chunks)}')
        assert len(chunks) == 4  # 3 working + 1 completed
        assert chunks[-1]['task']['status']['state'] == 'COMPLETED'

        print('All WebSocket server tests passed!')

        sub_task.cancel()
        try:
            await sub_task
        except asyncio.CancelledError:
            pass
    finally:
        await server.stop()


if __name__ == '__main__':
    asyncio.run(test_websocket_server())
