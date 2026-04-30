from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ComponentType(str, Enum):
    API = "API"
    MCP_HOST = "MCP_HOST"
    CACHE = "CACHE"
    ASYNC_QUEUE = "ASYNC_QUEUE"
    RDBMS = "RDBMS"
    NOSQL = "NOSQL"


class SignalKind(str, Enum):
    ERROR = "error"
    LATENCY = "latency"


class Severity(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


SEVERITY_RANK: dict[Severity, int] = {
    Severity.P0: 0,
    Severity.P1: 1,
    Severity.P2: 2,
    Severity.P3: 3,
}


class WorkItemStatus(str, Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class SignalPayload(BaseModel):
    id: str = Field(default_factory=lambda: f"sig-{uuid4().hex[:12]}")
    component_id: str = Field(min_length=3, max_length=100)
    component_type: ComponentType
    signal_kind: SignalKind = SignalKind.ERROR
    message: str = Field(min_length=5, max_length=500)
    observed_at: datetime = Field(default_factory=utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("component_id")
    @classmethod
    def normalize_component_id(cls, value: str) -> str:
        return value.strip().upper()


class AlertDecision(BaseModel):
    severity: Severity
    channel: str
    summary: str


class RCARecord(BaseModel):
    start_time: datetime
    end_time: datetime
    root_cause_category: str = Field(min_length=3, max_length=120)
    fix_applied: str = Field(min_length=10, max_length=2000)
    prevention_steps: str = Field(min_length=10, max_length=2000)

    def is_complete(self) -> bool:
        values = [
            self.root_cause_category.strip(),
            self.fix_applied.strip(),
            self.prevention_steps.strip(),
        ]
        return all(values) and self.end_time >= self.start_time


class StatusChangeRequest(BaseModel):
    status: WorkItemStatus


class IncidentSummary(BaseModel):
    id: str
    component_id: str
    component_type: ComponentType
    severity: Severity
    alert_channel: str
    title: str
    status: WorkItemStatus
    signal_count: int
    first_signal_at: datetime
    last_signal_at: datetime
    updated_at: datetime
    mttr_seconds: float | None = None


class IncidentDetail(IncidentSummary):
    rca: RCARecord | None = None
    rca_submitted_at: datetime | None = None
    raw_signals: list[dict[str, Any]] = Field(default_factory=list)


class HealthSnapshot(BaseModel):
    ok: bool
    queue_depth: int
    active_incidents: int
    worker_count: int
    signals_last_window: int
    throughput_per_second: float


class MetricsPoint(BaseModel):
    bucket_start: datetime
    severity: Severity
    count: int
