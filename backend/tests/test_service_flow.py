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
            for index in range(5)
        ]

        for signal in signals:
            await self.service.enqueue_signal(signal)

        await self.service.queue.join()
        incidents = await self.service.list_incidents()
        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0].signal_count, 5)

        detail = await self.service.fetch_incident_detail(incidents[0].id)
        self.assertIsNotNone(detail)
        self.assertEqual(len(detail.raw_signals), 5)
