from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass


@dataclass
class BucketState:
    tokens: float
    last_refill: float


class TokenBucketRateLimiter:
    def __init__(self, rate_per_minute: int, burst_size: int) -> None:
        self.rate_per_second = rate_per_minute / 60
        self.burst_size = burst_size
        self._buckets: dict[str, BucketState] = {}
        self._lock = asyncio.Lock()

    async def allow(self, key: str) -> bool:
        now = time.monotonic()
        async with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = BucketState(tokens=self.burst_size, last_refill=now)
                self._buckets[key] = bucket

            elapsed = now - bucket.last_refill
            bucket.tokens = min(
                self.burst_size,
                bucket.tokens + elapsed * self.rate_per_second,
            )
            bucket.last_refill = now
            if bucket.tokens < 1:
                return False
            bucket.tokens -= 1
            return True
