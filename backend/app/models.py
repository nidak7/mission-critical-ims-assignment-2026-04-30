from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator


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
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: f"sig-{uuid4().hex[:12]}")
    component_id: str = Field(
        min_length=3,
        max_length=100,
        validation_alias=AliasChoices("component_id", "componentId"),
    )
    component_type: ComponentType = Field(
        validation_alias=AliasChoices("component_type", "componentType"),
    )
    signal_kind: SignalKind = Field(
        default=SignalKind.ERROR,
        validation_alias=AliasChoices("signal_kind", "signalKind"),
    )
    message: str = Field(min_length=5, max_length=500)
    observed_at: datetime = Field(
        default_factory=utcnow,
        validation_alias=AliasChoices("observed_at", "observedAt"),
    )
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
    model_config = ConfigDict(populate_by_name=True)

    start_time: datetime = Field(validation_alias=AliasChoices("start_time", "startTime"))
    end_time: datetime = Field(validation_alias=AliasChoices("end_time", "endTime"))
    root_cause_category: str = Field(
        min_length=3,
        max_length=120,
        validation_alias=AliasChoices("root_cause_category", "rootCauseCategory"),
    )
    fix_applied: str = Field(
        min_length=10,
        max_length=2000,
        validation_alias=AliasChoices("fix_applied", "fixApplied"),
    )
    prevention_steps: str = Field(
        min_length=10,
        max_length=2000,
        validation_alias=AliasChoices("prevention_steps", "preventionSteps"),
    )

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def normalize_timestamp(cls, value: datetime, info: ValidationInfo) -> datetime:
        del info
        if isinstance(value, datetime):
            parsed = value
        else:
            parsed = datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_time_range(self) -> "RCARecord":
        if self.end_time < self.start_time:
            raise ValueError("end_time must be greater than or equal to start_time.")
        return self

    def is_complete(self) -> bool:
        values = [
            self.root_cause_category.strip(),
            self.fix_applied.strip(),
            self.prevention_steps.strip(),
        ]
        return all(values)


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
