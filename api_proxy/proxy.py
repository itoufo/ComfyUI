from typing import Any

import httpx

from .config import settings

_client: httpx.AsyncClient | None = None


async def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=settings.comfyui_base_url,
            timeout=httpx.Timeout(connect=5.0, read=300.0, write=10.0, pool=5.0),
        )
    return _client


async def close_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None


async def post_prompt(workflow: dict[str, Any], client_id: str | None = None) -> dict:
    """Submit a workflow to ComfyUI."""
    client = await get_client()
    payload: dict[str, Any] = {"prompt": workflow}
    if client_id:
        payload["client_id"] = client_id
    resp = await client.post("/prompt", json=payload)
    resp.raise_for_status()
    return resp.json()


async def get_queue() -> dict:
    client = await get_client()
    resp = await client.get("/queue")
    resp.raise_for_status()
    return resp.json()


async def get_system_stats() -> dict:
    client = await get_client()
    resp = await client.get("/system_stats")
    resp.raise_for_status()
    return resp.json()


async def get_history(prompt_id: str) -> dict:
    client = await get_client()
    resp = await client.get(f"/history/{prompt_id}")
    resp.raise_for_status()
    return resp.json()


async def get_image(filename: str, subfolder: str = "", img_type: str = "output") -> httpx.Response:
    client = await get_client()
    resp = await client.get(
        "/view",
        params={"filename": filename, "subfolder": subfolder, "type": img_type},
    )
    resp.raise_for_status()
    return resp


async def post_interrupt(prompt_id: str | None = None) -> dict:
    client = await get_client()
    payload: dict[str, Any] = {}
    if prompt_id:
        payload["prompt_id"] = prompt_id
    resp = await client.post("/interrupt", json=payload)
    resp.raise_for_status()
    # Also try to delete from queue
    try:
        await client.post("/queue", json={"delete": [prompt_id]})
    except Exception:
        pass
    return {"interrupted": True}


async def health_check() -> bool:
    """Check if ComfyUI is reachable."""
    try:
        client = await get_client()
        resp = await client.get("/system_stats", timeout=5.0)
        return resp.status_code == 200
    except Exception:
        return False
