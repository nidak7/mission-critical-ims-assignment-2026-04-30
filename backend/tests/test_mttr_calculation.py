from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.alerts import AlertDecision
from backend.app.models import ComponentType, RCARecord, Severity, SignalPayload
from backend.app.storage import SqliteIncidentStore


class MttrCalculationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        storage_root = ROOT / "backend" / "storage"
        storage_root.mkdir(parents=True, exist_ok=True)
        self.database_path = storage_root / f"mttr-{uuid4().hex}.db"
        self.store = SqliteIncidentStore(self.database_path)
        await self.store.initialize()

        signal = SignalPayload(
            component_id="API_GATEWAY_01",
            component_type=ComponentType.API,
            message="Gateway latency is breaching the alert threshold.",
        )
        alert = AlertDecision(
            severity=Severity.P1,
            channel="slack://api-oncall",
            summary="API degradation detected.",
        )
        self.incident_id = await self.store.create_incident(signal, alert)
        await self.store.attach_signal(self.incident_id, signal, Severity.P1)

    async def asyncTearDown(self) -> None:
        if self.database_path.exists():
            self.database_path.unlink()
        wal_path = self.database_path.with_suffix(".db-wal")
        shm_path = self.database_path.with_suffix(".db-shm")
        if wal_path.exists():
            wal_path.unlink()
        if shm_path.exists():
            shm_path.unlink()

    async def test_mttr_is_30_minutes(self) -> None:
        detail = await self.store.save_rca(
            self.incident_id,
            RCARecord(
                start_time=datetime(2026, 5, 1, 7, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 5, 1, 7, 30, tzinfo=timezone.utc),
                root_cause_category="Dependency Failure",
                fix_applied="Traffic was failed over to the healthy upstream cluster.",
                prevention_steps="Add pre-cutover checks and a rollback health gate.",
            ),
        )
        self.assertEqual(detail.mttr_seconds, 1800)

    async def test_mttr_is_60_minutes_and_reflected_in_detail(self) -> None:
        await self.store.save_rca(
            self.incident_id,
            RCARecord(
                start_time=datetime(2026, 5, 1, 7, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc),
                root_cause_category="Deployment Regression",
                fix_applied="The bad deployment was rolled back and pods were recycled.",
                prevention_steps="Add canary health checks before widening rollout scope.",
            ),
        )
        detail = await self.store.fetch_incident(self.incident_id)
        self.assertIsNotNone(detail)
        self.assertEqual(detail.mttr_seconds, 3600)
        self.assertNotEqual(detail.mttr_seconds, None)

    async def test_duplicate_rca_submission_updates_mttr_safely(self) -> None:
        await self.store.save_rca(
            self.incident_id,
            RCARecord(
                start_time=datetime(2026, 5, 1, 7, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 5, 1, 7, 30, tzinfo=timezone.utc),
                root_cause_category="Dependency Failure",
                fix_applied="Traffic was failed over to the healthy upstream cluster.",
                prevention_steps="Add pre-cutover checks and a rollback health gate.",
            ),
        )

        detail = await self.store.save_rca(
            self.incident_id,
            RCARecord(
                start_time=datetime(2026, 5, 1, 7, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc),
                root_cause_category="Deployment Regression",
                fix_applied="The bad deployment was rolled back and pods were recycled.",
                prevention_steps="Add canary health checks before widening rollout scope.",
            ),
        )

        self.assertEqual(detail.mttr_seconds, 3600)
