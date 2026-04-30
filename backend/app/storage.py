from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import aiosqlite

from .models import (
    AlertDecision,
    ComponentType,
    IncidentDetail,
    IncidentSummary,
    MetricsPoint,
    RCARecord,
    SEVERITY_RANK,
    Severity,
    SignalPayload,
    WorkItemStatus,
    utcnow,
)
from .workflow import TransitionError, WorkflowStateMachine


def iso_to_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def minute_bucket(timestamp: datetime) -> datetime:
    return timestamp.astimezone(timezone.utc).replace(second=0, microsecond=0)


class RawSignalStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.audit_file = self.root / "audit-log.jsonl"
        self.alert_file = self.root / "alerts.jsonl"
        self._lock = asyncio.Lock()

    async def append_signal(self, incident_id: str, signal: SignalPayload) -> None:
        record = {
            "incident_id": incident_id,
            "signal": signal.model_dump(mode="json"),
        }
        line = json.dumps(record) + "\n"
        incident_file = self.root / f"{incident_id}.jsonl"
        async with self._lock:
            with incident_file.open("a", encoding="utf-8") as handle:
                handle.write(line)
            with self.audit_file.open("a", encoding="utf-8") as handle:
                handle.write(line)

    async def append_alert(self, incident_id: str, alert: AlertDecision) -> None:
        record = {
            "incident_id": incident_id,
            "alert": alert.model_dump(mode="json"),
            "emitted_at": utcnow().isoformat(),
        }
        async with self._lock:
            with self.alert_file.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record) + "\n")

    async def fetch_incident_signals(self, incident_id: str) -> list[dict[str, Any]]:
        incident_file = self.root / f"{incident_id}.jsonl"
        if not incident_file.exists():
            return []

        signals: list[dict[str, Any]] = []
        async with self._lock:
            with incident_file.open("r", encoding="utf-8") as handle:
                for line in handle:
                    payload = json.loads(line)
                    signals.append(payload["signal"])
        return signals


class SqliteIncidentStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.database_uri = str(self.database_path)

    async def initialize(self) -> None:
        async with aiosqlite.connect(self.database_uri) as db:
            await db.executescript(
                """
                PRAGMA journal_mode = WAL;
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS incidents (
                    id TEXT PRIMARY KEY,
                    component_id TEXT NOT NULL,
                    component_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    alert_channel TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    signal_count INTEGER NOT NULL DEFAULT 0,
                    first_signal_at TEXT NOT NULL,
                    last_signal_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    mttr_seconds REAL
                );

                CREATE TABLE IF NOT EXISTS rcas (
                    incident_id TEXT PRIMARY KEY REFERENCES incidents(id) ON DELETE CASCADE,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    root_cause_category TEXT NOT NULL,
                    fix_applied TEXT NOT NULL,
                    prevention_steps TEXT NOT NULL,
                    submitted_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS transitions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
                    from_status TEXT NOT NULL,
                    to_status TEXT NOT NULL,
                    changed_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS timeseries_aggregates (
                    bucket_start TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    count INTEGER NOT NULL,
                    PRIMARY KEY (bucket_start, severity)
                );
                """
            )
            await db.commit()

    async def ping(self) -> bool:
        async with aiosqlite.connect(self.database_uri) as db:
            async with db.execute("SELECT 1") as cursor:
                row = await cursor.fetchone()
                return bool(row and row[0] == 1)

    async def create_incident(self, signal: SignalPayload, alert: AlertDecision) -> str:
        incident_id = f"inc-{uuid4().hex[:12]}"
        now = utcnow().isoformat()
        observed_at = signal.observed_at.astimezone(timezone.utc).isoformat()

        async def operation() -> None:
            async with aiosqlite.connect(self.database_uri) as db:
                await db.execute(
                    """
                    INSERT INTO incidents (
                        id,
                        component_id,
                        component_type,
                        severity,
                        alert_channel,
                        title,
                        status,
                        signal_count,
                        first_signal_at,
                        last_signal_at,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        incident_id,
                        signal.component_id,
                        signal.component_type.value,
                        alert.severity.value,
                        alert.channel,
                        f"{signal.component_type.value} / {signal.component_id} incident",
                        WorkItemStatus.OPEN.value,
                        0,
                        observed_at,
                        observed_at,
                        now,
                        now,
                    ),
                )
                await db.commit()

        await self._run_write_with_retry(operation)
        return incident_id

    async def fetch_active_incident_by_component(self, component_id: str) -> dict[str, Any] | None:
        async with aiosqlite.connect(self.database_uri) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT * FROM incidents
                WHERE component_id = ? AND status != ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (component_id, WorkItemStatus.CLOSED.value),
            ) as cursor:
                row = await cursor.fetchone()
        return dict(row) if row else None

    async def attach_signal(self, incident_id: str, signal: SignalPayload, severity: Severity) -> None:
        async def operation() -> None:
            async with aiosqlite.connect(self.database_uri) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT severity, signal_count FROM incidents WHERE id = ?", (incident_id,)) as cursor:
                    row = await cursor.fetchone()
                if row is None:
                    raise KeyError(f"Incident {incident_id} not found.")

                current_severity = Severity(row["severity"])
                next_severity = severity
                final_severity = current_severity
                if SEVERITY_RANK[next_severity] < SEVERITY_RANK[current_severity]:
                    final_severity = next_severity

                await db.execute(
                    """
                    UPDATE incidents
                    SET signal_count = signal_count + 1,
                        last_signal_at = ?,
                        updated_at = ?,
                        severity = ?
                    WHERE id = ?
                    """,
                    (
                        signal.observed_at.astimezone(timezone.utc).isoformat(),
                        utcnow().isoformat(),
                        final_severity.value,
                        incident_id,
                    ),
                )
                await db.commit()

        await self._run_write_with_retry(operation)

    async def save_rca(self, incident_id: str, rca: RCARecord) -> IncidentDetail:
        if not rca.is_complete():
            raise TransitionError("RCA submission is incomplete.")

        async def operation() -> None:
            async with aiosqlite.connect(self.database_uri) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT first_signal_at FROM incidents WHERE id = ?", (incident_id,)) as cursor:
                    incident = await cursor.fetchone()
                if incident is None:
                    raise KeyError(f"Incident {incident_id} not found.")

                submitted_at = utcnow()
                mttr_seconds = (rca.end_time - rca.start_time).total_seconds()

                await db.execute(
                    """
                    INSERT INTO rcas (
                        incident_id,
                        start_time,
                        end_time,
                        root_cause_category,
                        fix_applied,
                        prevention_steps,
                        submitted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(incident_id) DO UPDATE SET
                        start_time = excluded.start_time,
                        end_time = excluded.end_time,
                        root_cause_category = excluded.root_cause_category,
                        fix_applied = excluded.fix_applied,
                        prevention_steps = excluded.prevention_steps,
                        submitted_at = excluded.submitted_at
                    """,
                    (
                        incident_id,
                        rca.start_time.astimezone(timezone.utc).isoformat(),
                        rca.end_time.astimezone(timezone.utc).isoformat(),
                        rca.root_cause_category.strip(),
                        rca.fix_applied.strip(),
                        rca.prevention_steps.strip(),
                        submitted_at.isoformat(),
                    ),
                )
                await db.execute(
                    "UPDATE incidents SET mttr_seconds = ?, updated_at = ? WHERE id = ?",
                    (mttr_seconds, submitted_at.isoformat(), incident_id),
                )
                await db.commit()

        await self._run_write_with_retry(operation)

        detail = await self.fetch_incident(incident_id)
        if detail is None:
            raise KeyError(f"Incident {incident_id} not found after RCA save.")
        return detail

    async def transition_incident(self, incident_id: str, target_status: WorkItemStatus) -> IncidentSummary:
        async def operation() -> None:
            async with aiosqlite.connect(self.database_uri) as db:
                db.row_factory = aiosqlite.Row
                await db.execute("BEGIN IMMEDIATE")
                async with db.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)) as cursor:
                    incident = await cursor.fetchone()
                if incident is None:
                    await db.rollback()
                    raise KeyError(f"Incident {incident_id} not found.")

                async with db.execute("SELECT * FROM rcas WHERE incident_id = ?", (incident_id,)) as cursor:
                    rca = await cursor.fetchone()

                rca_complete = False
                if rca:
                    candidate = RCARecord(
                        start_time=iso_to_dt(rca["start_time"]),
                        end_time=iso_to_dt(rca["end_time"]),
                        root_cause_category=rca["root_cause_category"],
                        fix_applied=rca["fix_applied"],
                        prevention_steps=rca["prevention_steps"],
                    )
                    rca_complete = candidate.is_complete()

                WorkflowStateMachine.transition(
                    WorkItemStatus(incident["status"]),
                    target_status,
                    rca_complete=rca_complete,
                )

                changed_at = utcnow().isoformat()
                await db.execute(
                    """
                    UPDATE incidents
                    SET status = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (target_status.value, changed_at, incident_id),
                )
                await db.execute(
                    """
                    INSERT INTO transitions (incident_id, from_status, to_status, changed_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (incident_id, incident["status"], target_status.value, changed_at),
                )
                await db.commit()

        await self._run_write_with_retry(operation)

        summary = await self.fetch_incident_summary(incident_id)
        if summary is None:
            raise KeyError(f"Incident {incident_id} not found after transition.")
        return summary

    async def record_timeseries(self, severity: Severity, observed_at: datetime) -> None:
        bucket = minute_bucket(observed_at).isoformat()
        async def operation() -> None:
            async with aiosqlite.connect(self.database_uri) as db:
                await db.execute(
                    """
                    INSERT INTO timeseries_aggregates (bucket_start, severity, count)
                    VALUES (?, ?, 1)
                    ON CONFLICT(bucket_start, severity)
                    DO UPDATE SET count = count + 1
                    """,
                    (bucket, severity.value),
                )
                await db.commit()

        await self._run_write_with_retry(operation)

    async def list_active_incidents(self) -> list[IncidentSummary]:
        async with aiosqlite.connect(self.database_uri) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT * FROM incidents
                WHERE status != ?
                ORDER BY
                    CASE severity
                        WHEN 'P0' THEN 0
                        WHEN 'P1' THEN 1
                        WHEN 'P2' THEN 2
                        ELSE 3
                    END ASC,
                    updated_at DESC
                """
                ,
                (WorkItemStatus.CLOSED.value,),
            ) as cursor:
                rows = await cursor.fetchall()
        return [self._summary_from_row(dict(row)) for row in rows]

    async def fetch_incident_summary(self, incident_id: str) -> IncidentSummary | None:
        async with aiosqlite.connect(self.database_uri) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)) as cursor:
                row = await cursor.fetchone()
        return self._summary_from_row(dict(row)) if row else None

    async def fetch_incident(self, incident_id: str) -> IncidentDetail | None:
        async with aiosqlite.connect(self.database_uri) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)) as cursor:
                incident = await cursor.fetchone()
            if incident is None:
                return None
            async with db.execute("SELECT * FROM rcas WHERE incident_id = ?", (incident_id,)) as cursor:
                rca_row = await cursor.fetchone()

        summary = self._summary_from_row(dict(incident))
        detail = IncidentDetail(**summary.model_dump())
        if rca_row:
            detail.rca = RCARecord(
                start_time=iso_to_dt(rca_row["start_time"]),
                end_time=iso_to_dt(rca_row["end_time"]),
                root_cause_category=rca_row["root_cause_category"],
                fix_applied=rca_row["fix_applied"],
                prevention_steps=rca_row["prevention_steps"],
            )
            detail.rca_submitted_at = iso_to_dt(rca_row["submitted_at"])
        return detail

    async def fetch_timeseries(self, hours: int = 6) -> list[MetricsPoint]:
        start = utcnow() - timedelta(hours=hours)
        async with aiosqlite.connect(self.database_uri) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT bucket_start, severity, count
                FROM timeseries_aggregates
                WHERE bucket_start >= ?
                ORDER BY bucket_start ASC
                """,
                (start.isoformat(),),
            ) as cursor:
                rows = await cursor.fetchall()
        return [
            MetricsPoint(
                bucket_start=iso_to_dt(row["bucket_start"]),
                severity=Severity(row["severity"]),
                count=row["count"],
            )
            for row in rows
        ]

    def _summary_from_row(self, row: dict[str, Any]) -> IncidentSummary:
        return IncidentSummary(
            id=row["id"],
            component_id=row["component_id"],
            component_type=ComponentType(row["component_type"]),
            severity=Severity(row["severity"]),
            alert_channel=row["alert_channel"],
            title=row["title"],
            status=WorkItemStatus(row["status"]),
            signal_count=row["signal_count"],
            first_signal_at=iso_to_dt(row["first_signal_at"]),
            last_signal_at=iso_to_dt(row["last_signal_at"]),
            updated_at=iso_to_dt(row["updated_at"]),
            mttr_seconds=row["mttr_seconds"],
        )

    async def _run_write_with_retry(self, operation: Any) -> Any:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                return await operation()
            except aiosqlite.OperationalError as exc:
                last_error = exc
                if attempt == 2:
                    break
                await asyncio.sleep(0.1 * (2**attempt))
        if last_error is not None:
            raise last_error
