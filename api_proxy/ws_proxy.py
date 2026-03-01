import asyncio
import logging
import uuid

import websockets
from fastapi import WebSocket, WebSocketDisconnect

from .config import settings

logger = logging.getLogger("api_proxy")


async def ws_proxy(client_ws: WebSocket) -> None:
    """Bidirectional WebSocket proxy between the API client and ComfyUI."""
    client_id = str(uuid.uuid4())
    comfyui_url = f"{settings.comfyui_ws_url}/ws?clientId={client_id}"

    try:
        async with websockets.connect(comfyui_url) as backend_ws:
            # Forward messages in both directions
            async def client_to_backend() -> None:
                try:
                    while True:
                        data = await client_ws.receive_text()
                        await backend_ws.send(data)
                except WebSocketDisconnect:
                    pass

            async def backend_to_client() -> None:
                try:
                    async for message in backend_ws:
                        if isinstance(message, str):
                            await client_ws.send_text(message)
                        else:
                            await client_ws.send_bytes(message)
                except websockets.exceptions.ConnectionClosed:
                    pass

            # Run both directions concurrently
            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(client_to_backend()),
                    asyncio.create_task(backend_to_client()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
    except Exception as exc:
        logger.warning("WebSocket proxy error: %s", exc)
    finally:
        try:
            await client_ws.close()
        except Exception:
            pass
