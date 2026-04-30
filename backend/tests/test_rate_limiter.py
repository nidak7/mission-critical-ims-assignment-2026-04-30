from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.rate_limiter import TokenBucketRateLimiter


class RateLimiterTests(unittest.IsolatedAsyncioTestCase):
    async def test_burst_limit_is_enforced(self) -> None:
        limiter = TokenBucketRateLimiter(rate_per_minute=0, burst_size=2)

        self.assertTrue(await limiter.allow("reviewer"))
        self.assertTrue(await limiter.allow("reviewer"))
        self.assertFalse(await limiter.allow("reviewer"))
