from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.models import ComponentType, SignalPayload
from backend.app.service import build_service


class ServiceFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        storage_root = ROOT / "backend" / "storage" / f"service-test-{uuid4().hex}"
        storage_root.mkdir(parents=True, exist_ok=True)
        self.storage_root = storage_root
        self.service = build_service(storage_root)
        await self.service.startup()

    async def asyncTearDown(self) -> None:
        await self.service.shutdown()
        shutil.rmtree(self.storage_root, ignore_errors=True)

    async def test_same_component_bursts_attach_to_single_incident(self) -> None:
        signals = [
            SignalPayload(
                component_id="cache_cluster_01",
                component_type=ComponentType.CACHE,
                message=f"Cache timeout burst #{index}",
            )
            for index in range(100)
        ]

        for signal in signals:
            await self.service.enqueue_signal(signal)

        await self.service.queue.join()
        incidents = await self.service.list_incidents()
        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0].signal_count, 100)

        detail = await self.service.fetch_incident_detail(incidents[0].id)
        self.assertIsNotNone(detail)
        self.assertEqual(len(detail.raw_signals), 100)

    async def test_different_components_create_distinct_incidents_with_expected_routes(self) -> None:
        signals = [
            SignalPayload(
                component_id="RDBMS_PRIMARY_01",
                component_type=ComponentType.RDBMS,
                message="Primary database is refusing connections from the API pool.",
            ),
            SignalPayload(
                component_id="MCP_HOST_02",
                component_type=ComponentType.MCP_HOST,
                message="MCP host lost downstream connectivity and is returning tool failures.",
            ),
            SignalPayload(
                component_id="CACHE_CLUSTER_01",
                component_type=ComponentType.CACHE,
                message="Redis latency is climbing across the primary shard.",
            ),
        ]

        for signal in signals:
            await self.service.enqueue_signal(signal)

        await self.service.queue.join()
        incidents = await self.service.list_incidents()

        self.assertEqual(len(incidents), 3)
        self.assertEqual(
            [(incident.component_id, incident.severity.value, incident.alert_channel) for incident in incidents],
            [
                ("RDBMS_PRIMARY_01", "P0", "pagerduty://db-primary"),
                ("MCP_HOST_02", "P1", "slack://mcp-hosts"),
                ("CACHE_CLUSTER_01", "P2", "slack://cache-ops"),
            ],
        )

    async def test_health_snapshot_reports_active_incidents_and_throughput(self) -> None:
        await self.service.enqueue_signal(
            SignalPayload(
                component_id="API_EDGE_01",
                component_type=ComponentType.API,
                message="Error rate is rising sharply on the public API edge.",
            )
        )

        await self.service.queue.join()
        health = await self.service.health()

        self.assertTrue(health.ok)
        self.assertEqual(health.active_incidents, 1)
        self.assertGreater(health.throughput_per_second, 0)
