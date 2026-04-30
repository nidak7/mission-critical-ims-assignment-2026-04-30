from __future__ import annotations

import unittest

from backend.tests.helpers import TestAppHarness


class DashboardStateTests(unittest.TestCase):
    def test_empty_dashboard_fragments_render_cleanly(self) -> None:
        harness = TestAppHarness()
        try:
            feed_response = harness.client.get("/ui/incidents")
            self.assertEqual(feed_response.status_code, 200)
            self.assertIn("No active incidents", feed_response.text)

            detail_response = harness.client.get("/ui/incidents/inc-missing")
            self.assertEqual(detail_response.status_code, 200)
            self.assertIn("Incident not found.", detail_response.text)
        finally:
            harness.close()

    def test_dashboard_sorts_by_severity_and_renders_raw_signal_content(self) -> None:
        harness = TestAppHarness()
        try:
            payloads = [
                {
                    "component_id": "CACHE_CLUSTER_01",
                    "component_type": "CACHE",
                    "message": "Cache latency is rising during peak read-through traffic.",
                    "metadata": {"region": "ap-south-1"},
                },
                {
                    "component_id": "RDBMS_PRIMARY_01",
                    "component_type": "RDBMS",
                    "message": "Primary database is refusing connections from the API pool.",
                    "metadata": {"cluster": "orders-db"},
                },
                {
                    "component_id": "MCP_HOST_02",
                    "component_type": "MCP_HOST",
                    "message": "MCP host lost downstream connectivity and is returning tool failures.",
                    "metadata": {"service": "customer-resolution-host"},
                },
            ]
            for payload in payloads:
                self.assertEqual(harness.client.post("/api/signals", json=payload).status_code, 202)

            incidents = harness.wait_for_incident_count(3)
            self.assertEqual([incident["severity"] for incident in incidents], ["P0", "P1", "P2"])
            self.assertEqual(
                [incident["component_id"] for incident in incidents],
                ["RDBMS_PRIMARY_01", "MCP_HOST_02", "CACHE_CLUSTER_01"],
            )

            detail_response = harness.client.get(f"/ui/incidents/{incidents[0]['id']}")
            self.assertEqual(detail_response.status_code, 200)
            self.assertIn("Primary database is refusing connections", detail_response.text)
            self.assertIn("metadata keys: cluster", detail_response.text)
        finally:
            harness.close()

    def test_workflow_buttons_match_current_status(self) -> None:
        harness = TestAppHarness()
        try:
            response = harness.client.post(
                "/api/signals",
                json={
                    "component_id": "RDBMS_PRIMARY_01",
                    "component_type": "RDBMS",
                    "message": "Primary database is refusing connections from the API pool.",
                },
            )
            self.assertEqual(response.status_code, 202)
            incidents = harness.wait_for_incident_count(1)
            incident_id = incidents[0]["id"]

            open_detail = harness.client.get(f"/ui/incidents/{incident_id}")
            self.assertIn("Mark Investigating", open_detail.text)
            self.assertNotIn("Mark Resolved", open_detail.text)
            self.assertNotIn("Close Incident", open_detail.text)

            investigating_detail = harness.client.post(
                f"/ui/incidents/{incident_id}/status",
                data={"status": "INVESTIGATING"},
            )
            self.assertIn("Incident moved to INVESTIGATING.", investigating_detail.text)
            self.assertIn("Mark Resolved", investigating_detail.text)
            self.assertNotIn("Close Incident", investigating_detail.text)

            resolved_detail = harness.client.post(
                f"/ui/incidents/{incident_id}/status",
                data={"status": "RESOLVED"},
            )
            self.assertIn("Incident moved to RESOLVED.", resolved_detail.text)
            self.assertIn("Close Incident", resolved_detail.text)
            self.assertNotIn("Mark Investigating", resolved_detail.text)

            rca_detail = harness.client.post(
                f"/ui/incidents/{incident_id}/rca",
                data={
                    "start_time": "2026-04-30T19:00",
                    "end_time": "2026-04-30T19:30",
                    "root_cause_category": "Dependency Failure",
                    "fix_applied": "Traffic was failed over to the healthy replica and connection pools were recycled.",
                    "prevention_steps": "Add failover readiness checks and stronger dependency alerts before the API cutover.",
                },
            )
            self.assertIn("RCA saved.", rca_detail.text)
            self.assertIn("30m", rca_detail.text)

            closed_detail = harness.client.post(
                f"/ui/incidents/{incident_id}/status",
                data={"status": "CLOSED"},
            )
            self.assertIn("Incident moved to CLOSED.", closed_detail.text)
            self.assertIn("Incident closed", closed_detail.text)
            self.assertNotIn("Close Incident", closed_detail.text)
        finally:
            harness.close()
