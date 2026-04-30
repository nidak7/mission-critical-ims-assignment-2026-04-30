from __future__ import annotations

import unittest

from backend.app.rate_limiter import TokenBucketRateLimiter
from backend.tests.helpers import TestAppHarness


class ApiContractTests(unittest.TestCase):
    def test_health_endpoint_returns_up(self) -> None:
        harness = TestAppHarness()
        try:
            response = harness.client.get("/health")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"status": "UP"})
        finally:
            harness.close()

    def test_invalid_incident_id_returns_404(self) -> None:
        harness = TestAppHarness()
        try:
            response = harness.client.get("/api/incidents/inc-missing")
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json(), {"detail": "Incident not found."})
        finally:
            harness.close()

    def test_rate_limiter_returns_http_429_when_bucket_is_exhausted(self) -> None:
        harness = TestAppHarness(rate_limiter=TokenBucketRateLimiter(rate_per_minute=0, burst_size=2))
        try:
            payload = {
                "component_id": "API_BURST_01",
                "component_type": "API",
                "message": "Burst traffic is generating API errors.",
            }

            self.assertEqual(harness.client.post("/api/signals", json=payload).status_code, 202)
            self.assertEqual(harness.client.post("/api/signals", json=payload).status_code, 202)

            response = harness.client.post("/api/signals", json=payload)
            self.assertEqual(response.status_code, 429)
            self.assertEqual(
                response.json(),
                {"detail": "Rate limit exceeded for signal ingestion."},
            )
        finally:
            harness.close()

    def test_queue_backpressure_returns_http_503_without_crashing(self) -> None:
        harness = TestAppHarness(worker_count=0, queue_maxsize=1)
        try:
            payload = {
                "component_id": "API_QUEUE_01",
                "component_type": "API",
                "message": "Queue pressure is building on the API edge.",
            }

            self.assertEqual(harness.client.post("/api/signals", json=payload).status_code, 202)
            response = harness.client.post("/api/signals", json=payload)

            self.assertEqual(response.status_code, 503)
            self.assertEqual(
                response.json(),
                {"detail": "Signal queue is full, shedding load to preserve service health."},
            )
        finally:
            harness.close()
