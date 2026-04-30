from __future__ import annotations

import unittest

from backend.tests.helpers import TestAppHarness


class SignalIngestionTests(unittest.TestCase):
    def test_valid_signal_is_accepted_and_linked_to_open_incident(self) -> None:
        harness = TestAppHarness()
        try:
            response = harness.client.post(
                "/api/signals",
                json={
                    "componentId": "cache_cluster_01",
                    "componentType": "CACHE",
                    "signalKind": "latency",
                    "message": "Redis latency is climbing across the primary shard.",
                    "metadata": {"region": "ap-south-1", "latency_ms": 420},
                },
            )

            self.assertEqual(response.status_code, 202)
            incidents = harness.wait_for_incident_count(1)
            self.assertEqual(incidents[0]["status"], "OPEN")
            self.assertEqual(incidents[0]["component_id"], "CACHE_CLUSTER_01")

            detail_response = harness.client.get(f"/api/incidents/{incidents[0]['id']}")
            self.assertEqual(detail_response.status_code, 200)
            detail = detail_response.json()

            self.assertEqual(detail["signal_count"], 1)
            self.assertEqual(len(detail["raw_signals"]), 1)
            self.assertEqual(detail["raw_signals"][0]["component_id"], "CACHE_CLUSTER_01")
            self.assertEqual(detail["raw_signals"][0]["signal_kind"], "latency")
            self.assertEqual(detail["raw_signals"][0]["metadata"]["latency_ms"], 420)
        finally:
            harness.close()

    def test_invalid_payloads_fail_without_creating_incidents(self) -> None:
        harness = TestAppHarness()
        try:
            bad_payloads = [
                {
                    "component_type": "API",
                    "message": "Missing component id should fail validation.",
                },
                {
                    "component_id": "API_PRIMARY_01",
                    "component_type": "API",
                },
                {
                    "component_id": "API_PRIMARY_01",
                    "component_type": "INVALID",
                    "message": "Unknown component type should fail validation.",
                },
            ]

            for payload in bad_payloads:
                with self.subTest(payload=payload):
                    response = harness.client.post("/api/signals", json=payload)
                    self.assertEqual(response.status_code, 422)

            self.assertEqual(harness.list_incidents(), [])
        finally:
            harness.close()
