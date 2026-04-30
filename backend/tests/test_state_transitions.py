from __future__ import annotations

import sys
import unittest
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.alerts import AlertDecision
from backend.app.models import ComponentType, RCARecord, Severity, SignalPayload, WorkItemStatus, utcnow
from backend.app.storage import SqliteIncidentStore
from backend.app.workflow import TransitionError


class StateTransitionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        storage_root = ROOT / "backend" / "storage"
        storage_root.mkdir(parents=True, exist_ok=True)
        self.database_path = storage_root / f"transition-{uuid4().hex}.db"
        self.store = SqliteIncidentStore(self.database_path)
        await self.store.initialize()

        signal = SignalPayload(
            component_id="QUEUE_PRIMARY_01",
            component_type=ComponentType.ASYNC_QUEUE,
            message="Queue lag is growing rapidly.",
        )
        alert = AlertDecision(
            severity=Severity.P1,
            channel="slack://queue-ops",
            summary="Queue pressure detected.",
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

    async def test_open_cannot_jump_to_closed(self) -> None:
        with self.assertRaises(TransitionError):
            await self.store.transition_incident(self.incident_id, WorkItemStatus.CLOSED)

    async def test_open_cannot_skip_to_resolved(self) -> None:
        with self.assertRaises(TransitionError):
            await self.store.transition_incident(self.incident_id, WorkItemStatus.RESOLVED)

    async def test_valid_transition_path_reaches_closed_after_rca(self) -> None:
        investigating = await self.store.transition_incident(self.incident_id, WorkItemStatus.INVESTIGATING)
        self.assertEqual(investigating.status, WorkItemStatus.INVESTIGATING)

        resolved = await self.store.transition_incident(self.incident_id, WorkItemStatus.RESOLVED)
        self.assertEqual(resolved.status, WorkItemStatus.RESOLVED)

        await self.store.save_rca(
            self.incident_id,
            RCARecord(
                start_time=utcnow(),
                end_time=utcnow(),
                root_cause_category="Dependency Failure",
                fix_applied="Consumer throughput was restored by draining stuck workers and recycling queue consumers.",
                prevention_steps="Add queue lag SLO alerts and canary checks before increasing consumer concurrency.",
            ),
        )

        closed = await self.store.transition_incident(self.incident_id, WorkItemStatus.CLOSED)
        self.assertEqual(closed.status, WorkItemStatus.CLOSED)

    async def test_cannot_reopen_or_reclose_after_closed(self) -> None:
        await self.store.transition_incident(self.incident_id, WorkItemStatus.INVESTIGATING)
        await self.store.transition_incident(self.incident_id, WorkItemStatus.RESOLVED)
        await self.store.save_rca(
            self.incident_id,
            RCARecord(
                start_time=utcnow(),
                end_time=utcnow(),
                root_cause_category="Dependency Failure",
                fix_applied="Consumer throughput was restored by draining stuck workers and recycling queue consumers.",
                prevention_steps="Add queue lag SLO alerts and canary checks before increasing consumer concurrency.",
            ),
        )
        await self.store.transition_incident(self.incident_id, WorkItemStatus.CLOSED)

        with self.assertRaises(TransitionError):
            await self.store.transition_incident(self.incident_id, WorkItemStatus.INVESTIGATING)

        with self.assertRaises(TransitionError):
            await self.store.transition_incident(self.incident_id, WorkItemStatus.CLOSED)
