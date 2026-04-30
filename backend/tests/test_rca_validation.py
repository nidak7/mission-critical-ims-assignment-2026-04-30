from __future__ import annotations

import sys
import unittest
from datetime import timedelta
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.alerts import AlertDecision
from backend.app.models import ComponentType, RCARecord, Severity, SignalPayload, WorkItemStatus, utcnow
from backend.app.storage import SqliteIncidentStore
from backend.app.workflow import TransitionError


class RcaValidationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        storage_root = ROOT / "backend" / "storage"
        storage_root.mkdir(parents=True, exist_ok=True)
        self.database_path = storage_root / f"test-{uuid4().hex}.db"
        self.store = SqliteIncidentStore(self.database_path)
        await self.store.initialize()

        signal = SignalPayload(
            component_id="RDBMS_PRIMARY",
            component_type=ComponentType.RDBMS,
            message="Primary database is refusing connections.",
        )
        alert = AlertDecision(
            severity=Severity.P0,
            channel="pagerduty://db-primary",
            summary="Database failure detected.",
        )
        self.incident_id = await self.store.create_incident(signal, alert)
        await self.store.attach_signal(self.incident_id, signal, Severity.P0)

    async def asyncTearDown(self) -> None:
        if self.database_path.exists():
            self.database_path.unlink()
        wal_path = self.database_path.with_suffix(".db-wal")
        shm_path = self.database_path.with_suffix(".db-shm")
        if wal_path.exists():
            wal_path.unlink()
        if shm_path.exists():
            shm_path.unlink()

    async def test_cannot_close_without_rca(self) -> None:
        await self.store.transition_incident(self.incident_id, WorkItemStatus.INVESTIGATING)
        await self.store.transition_incident(self.incident_id, WorkItemStatus.RESOLVED)
        with self.assertRaises(TransitionError):
            await self.store.transition_incident(self.incident_id, WorkItemStatus.CLOSED)

    async def test_can_close_after_complete_rca(self) -> None:
        await self.store.transition_incident(self.incident_id, WorkItemStatus.INVESTIGATING)
        await self.store.transition_incident(self.incident_id, WorkItemStatus.RESOLVED)
        await self.store.save_rca(
            self.incident_id,
            RCARecord(
                start_time=utcnow() - timedelta(minutes=14),
                end_time=utcnow() - timedelta(minutes=2),
                root_cause_category="Dependency Failure",
                fix_applied="Failover was forced to the standby node and connection pools were recycled.",
                prevention_steps="Add replica health prechecks and tighten failover alert thresholds.",
            ),
        )
        summary = await self.store.transition_incident(self.incident_id, WorkItemStatus.CLOSED)
        self.assertEqual(summary.status, WorkItemStatus.CLOSED)


if __name__ == "__main__":
    unittest.main()
