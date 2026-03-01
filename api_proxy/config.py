import os
import secrets
from pathlib import Path

from pydantic_settings import BaseSettings

ENV_PATH = Path(__file__).resolve().parent / ".env"


def _ensure_api_key() -> None:
    """Generate .env with a random API key if it doesn't exist."""
    if ENV_PATH.exists():
        return
    key = secrets.token_urlsafe(48)  # 64-char base64
    ENV_PATH.write_text(f"API_KEY={key}\n", encoding="utf-8")


_ensure_api_key()


class Settings(BaseSettings):
    # Authentication
    API_KEY: str

    # ComfyUI backend
    COMFYUI_HOST: str = "127.0.0.1"
    COMFYUI_PORT: int = 8188

    # Proxy server
    PROXY_HOST: str = "127.0.0.1"
    PROXY_PORT: int = 8189

    # Rate limiting (per IP)
    RATE_LIMIT_PER_MINUTE: int = 10
    RATE_LIMIT_BURST: int = 3

    # Validation
    MAX_WORKFLOW_SIZE: int = 512 * 1024  # 512 KB
    MAX_NODE_COUNT: int = 200

    # Logging
    LOG_LEVEL: str = "INFO"

    model_config = {"env_file": str(ENV_PATH), "env_file_encoding": "utf-8"}

    @property
    def comfyui_base_url(self) -> str:
        return f"http://{self.COMFYUI_HOST}:{self.COMFYUI_PORT}"

    @property
    def comfyui_ws_url(self) -> str:
        return f"ws://{self.COMFYUI_HOST}:{self.COMFYUI_PORT}"


settings = Settings()
