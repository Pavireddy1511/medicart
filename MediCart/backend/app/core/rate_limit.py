import threading
import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.exceptions import RateLimitedError


class RateLimiter:
    """Sliding-window limiter kept in process memory.

    Fine for a single uvicorn process. On a serverless platform each instance keeps
    its own counters, so treat it as a soft limit there.
    """

    def __init__(self, limit: int, window_seconds: int, scope: str):
        self.limit = limit
        self.window = window_seconds
        self.scope = scope
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            while bucket and now - bucket[0] > self.window:
                bucket.popleft()
            if len(bucket) >= self.limit:
                retry_after = int(self.window - (now - bucket[0])) + 1
                raise RateLimitedError(
                    "Too many attempts. Please wait a moment and try again.",
                    details={"retry_after_seconds": retry_after},
                )
            bucket.append(now)

    async def __call__(self, request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client = forwarded.split(",")[0].strip()
        self.check(f"{self.scope}:{client}")
