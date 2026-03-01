"""ComfyUI Secure API Proxy — FastAPI application."""

import hmac
import logging
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Query, Request, WebSocket, status
from fastapi.responses import JSONResponse, Response

from .auth import require_api_key
from .config import settings
from .models import (
    CancelResponse,
    ErrorResponse,
    GenerateRequest,
    GenerateResponse,
    HealthResponse,
    ResultResponse,
    StatusResponse,
)
from .proxy import close_client, get_image, get_history, get_object_info, get_queue, get_system_stats, health_check, post_interrupt, post_prompt
from .rate_limiter import rate_limiter
from .validators import validate_filename, validate_workflow
from .workflows.flux_dev import build_workflow
from .ws_proxy import ws_proxy

# Logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("api_proxy")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("API proxy starting on %s:%d", settings.PROXY_HOST, settings.PROXY_PORT)
    logger.info("Proxying to ComfyUI at %s", settings.comfyui_base_url)
    yield
    await close_client()
    logger.info("API proxy shut down")


app = FastAPI(
    title="ComfyUI API Proxy",
    lifespan=lifespan,
    # Disable docs in production
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


# --- Middleware: request logging ---

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    elapsed = (time.monotonic() - start) * 1000
    ip = (
        request.headers.get("CF-Connecting-IP")
        or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )
    logger.info(
        "%s %s %s → %d (%.0fms)",
        ip,
        request.method,
        request.url.path,
        response.status_code,
        elapsed,
    )
    return response


# --- Health (no auth) ---

@app.get("/health", response_model=HealthResponse)
async def health():
    comfyui_ok = await health_check()
    return HealthResponse(
        status="ok",
        comfyui="connected" if comfyui_ok else "unreachable",
    )


# --- System Stats ---

@app.get(
    "/system_stats",
    dependencies=[Depends(require_api_key), Depends(rate_limiter)],
)
async def system_stats():
    try:
        data = await get_system_stats()
        return data
    except Exception as exc:
        logger.error("Failed to fetch system_stats: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": f"ComfyUI error: {exc}"},
        )


# --- Generate ---

@app.post(
    "/generate",
    response_model=GenerateResponse,
    responses={400: {"model": ErrorResponse}, 413: {"model": ErrorResponse}},
    dependencies=[Depends(require_api_key), Depends(rate_limiter)],
)
async def generate(req: GenerateRequest):
    if isinstance(req.prompt, str):
        # Simple mode: build Flux Dev workflow from text prompt
        workflow = build_workflow(
            prompt=req.prompt,
            negative_prompt=req.negative_prompt,
            width=req.width,
            height=req.height,
            steps=req.steps,
            cfg=req.cfg,
            seed=req.seed,
        )
    else:
        # Full workflow mode
        workflow = req.prompt

    validate_workflow(workflow)

    try:
        result = await post_prompt(workflow)
    except Exception as exc:
        logger.error("ComfyUI prompt submission failed: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": f"ComfyUI error: {exc}"},
        )

    if "node_errors" in result and result["node_errors"]:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "Workflow validation errors", "errors": result["node_errors"]},
        )

    return GenerateResponse(prompt_id=result["prompt_id"])


# --- Status ---

@app.get(
    "/status",
    response_model=StatusResponse,
    dependencies=[Depends(require_api_key), Depends(rate_limiter)],
)
async def queue_status():
    try:
        queue = await get_queue()
        stats = await get_system_stats()
    except Exception as exc:
        logger.error("Failed to fetch status: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": f"ComfyUI unreachable: {exc}"},
        )
    return StatusResponse(
        queue_running=len(queue.get("queue_running", [])),
        queue_pending=len(queue.get("queue_pending", [])),
        system_stats=stats,
    )


# --- Result ---

@app.get(
    "/result/{prompt_id}",
    response_model=ResultResponse,
    dependencies=[Depends(require_api_key), Depends(rate_limiter)],
)
async def result(prompt_id: str):
    try:
        # Check if still in queue
        queue = await get_queue()
        running_ids = [item[1] for item in queue.get("queue_running", [])]
        pending_ids = [item[1] for item in queue.get("queue_pending", [])]

        if prompt_id in running_ids:
            return ResultResponse(status="running")
        if prompt_id in pending_ids:
            return ResultResponse(status="pending")

        # Check history
        history = await get_history(prompt_id)
        if prompt_id in history:
            outputs = history[prompt_id].get("outputs", {})
            return ResultResponse(status="completed", outputs=outputs)

        return ResultResponse(status="not_found")
    except Exception as exc:
        logger.error("Failed to fetch result: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": f"ComfyUI error: {exc}"},
        )


# --- Image download ---

@app.get(
    "/image/{filename}",
    dependencies=[Depends(require_api_key), Depends(rate_limiter)],
)
async def image(
    filename: str,
    subfolder: str = Query(default="", max_length=255),
    type: str = Query(default="output", pattern="^(output|input|temp)$"),
):
    validate_filename(filename)
    if subfolder:
        validate_filename(subfolder)

    try:
        resp = await get_image(filename, subfolder, type)
    except Exception as exc:
        logger.error("Failed to fetch image: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": f"ComfyUI error: {exc}"},
        )

    content_type = resp.headers.get("content-type", "image/png")
    return Response(content=resp.content, media_type=content_type)


# --- Cancel ---

@app.post(
    "/cancel/{prompt_id}",
    response_model=CancelResponse,
    dependencies=[Depends(require_api_key), Depends(rate_limiter)],
)
async def cancel(prompt_id: str):
    try:
        await post_interrupt(prompt_id)
        return CancelResponse(cancelled=True)
    except Exception as exc:
        logger.error("Failed to cancel: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": f"ComfyUI error: {exc}"},
        )


# --- Object Info ---

@app.get(
    "/object_info",
    dependencies=[Depends(require_api_key), Depends(rate_limiter)],
)
@app.get(
    "/object_info/{node_class}",
    dependencies=[Depends(require_api_key), Depends(rate_limiter)],
)
async def object_info(node_class: str | None = None):
    try:
        data = await get_object_info(node_class)
        return data
    except Exception as exc:
        logger.error("Failed to fetch object_info: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": f"ComfyUI error: {exc}"},
        )


# --- WebSocket ---

@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(default=None),
    clientId: str = Query(default=None),
):
    # Authenticate via query parameter
    if token is None or not hmac.compare_digest(token, settings.API_KEY):
        await websocket.close(code=4001, reason="Unauthorized")
        return
    await websocket.accept()
    await ws_proxy(websocket)
