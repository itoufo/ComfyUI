import time
from dataclasses import dataclass, field

from fastapi import HTTPException, Request, status

from .config import settings


@dataclass
class _Bucket:
    tokens: float
    last_refill: float


class TokenBucketLimiter:
    """Per-IP token bucket rate limiter."""

    def __init__(
        self,
        rate_per_minute: int = settings.RATE_LIMIT_PER_MINUTE,
        burst: int = settings.RATE_LIMIT_BURST,
    ):
        self.rate: float = rate_per_minute / 60.0  # tokens per second
        self.burst: int = burst
        self._buckets: dict[str, _Bucket] = {}

    def _get_ip(self, request: Request) -> str:
        # Prefer Cloudflare header, fall back to X-Forwarded-For, then client IP
        return (
            request.headers.get("CF-Connecting-IP")
            or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or (request.client.host if request.client else "unknown")
        )

    def _refill(self, bucket: _Bucket) -> None:
        now = time.monotonic()
        elapsed = now - bucket.last_refill
        bucket.tokens = min(self.burst, bucket.tokens + elapsed * self.rate)
        bucket.last_refill = now

    async def __call__(self, request: Request) -> None:
        ip = self._get_ip(request)
        bucket = self._buckets.get(ip)
        if bucket is None:
            bucket = _Bucket(tokens=float(self.burst), last_refill=time.monotonic())
            self._buckets[ip] = bucket
        self._refill(bucket)
        if bucket.tokens < 1.0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Try again later.",
            )
        bucket.tokens -= 1.0


rate_limiter = TokenBucketLimiter()
