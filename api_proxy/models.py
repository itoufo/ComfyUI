from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# --- Request models ---

class GenerateRequest(BaseModel):
    """Simple prompt or full ComfyUI workflow."""

    prompt: str | dict[str, Any] = Field(
        ...,
        description="Text prompt (uses Flux Dev template) or full ComfyUI workflow dict",
    )
    # Simple-mode parameters (ignored when prompt is a full workflow)
    width: int = Field(default=1024, ge=64, le=2048)
    height: int = Field(default=1024, ge=64, le=2048)
    steps: int = Field(default=20, ge=1, le=100)
    cfg: float = Field(default=1.0, ge=0.0, le=30.0)
    seed: int | None = Field(default=None, description="Random seed; None = random")
    negative_prompt: str = Field(default="")


# --- Response models ---

class HealthResponse(BaseModel):
    status: str = "ok"
    comfyui: str = "unknown"


class GenerateResponse(BaseModel):
    prompt_id: str


class StatusResponse(BaseModel):
    queue_running: int
    queue_pending: int
    system_stats: dict[str, Any] | None = None


class ResultResponse(BaseModel):
    status: str  # "running", "pending", "completed", "not_found"
    outputs: dict[str, Any] | None = None


class CancelResponse(BaseModel):
    cancelled: bool


class ErrorResponse(BaseModel):
    detail: str
