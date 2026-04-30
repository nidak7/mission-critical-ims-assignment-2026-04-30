from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

from .alerts import AlertStrategyRouter
from .models import (
    HealthSnapshot,
    IncidentDetail,
    IncidentSummary,
    RCARecord,
    SEVERITY_RANK,
    Severity,
    SignalPayload,
    WorkItemStatus,
    utcnow,
)
from .rate_limiter import TokenBucketRateLimiter
from .storage import RawSignalStore, SqliteIncidentStore
from .workflow import TransitionError


class BackpressureError(RuntimeError):
    """Raised when the in-memory queue is saturated."""


@dataclass
class DebounceWindow:
    incident_id: str
    opened_at: Any


class IncidentService:
    def __init__(self, storage_root: Path) -> None:
        self.storage_root = storage_root
        self.signal_store = RawSignalStore(storage_root / "raw")
        self.source_of_truth = SqliteIncidentStore(storage_root / "ims.db")
        self.alert_router = AlertStrategyRouter()
        self.rate_limiter = TokenBucketRateLimiter(rate_per_minute=1800, burst_size=450)
        self.queue: asyncio.Queue[SignalPayload] = asyncio.Queue(maxsize=50000)
        self.worker_count = 4
        self._stop_event = asyncio.Event()
        self._worker_tasks: list[asyncio.Task[None]] = []
        self._metrics_task: asyncio.Task[None] | None = None
        self._component_locks: dict[str, asyncio.Lock] = {}
        self._cache_lock = asyncio.Lock()
        self._cache: dict[str, IncidentSummary] = {}
        self._debounce_windows: dict[str, DebounceWindow] = {}
        self._recent_processed: deque[float] = deque()
        self._metrics_lock = asyncio.Lock()

    async def startup(self) -> None:
        await self.source_of_truth.initialize()
        for incident in await self.source_of_truth.list_active_incidents():
            self._cache[incident.id] = incident
        self._stop_event.clear()
        self._worker_tasks = [
            asyncio.create_task(self._worker_loop(worker_number))
            for worker_number in range(self.worker_count)
        ]
        self._metrics_task = asyncio.create_task(self._metrics_loop())

    async def shutdown(self) -> None:
        self._stop_event.set()
        tasks = [*self._worker_tasks]
        if self._metrics_task is not None:
            tasks.append(self._metrics_task)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._worker_tasks = []
        self._metrics_task = None

    async def enqueue_signal(self, signal: SignalPayload) -> dict[str, str]:
        if self.queue.full():
            raise BackpressureError("Signal queue is full, shedding load to preserve service health.")
        self.queue.put_nowait(signal)
        return {"accepted": "true", "signal_id": signal.id}

    async def list_incidents(self) -> list[IncidentSummary]:
        async with self._cache_lock:
            incidents = list(self._cache.values())
        return sorted(
            incidents,
            key=lambda item: (SEVERITY_RANK[item.severity], -item.updated_at.timestamp()),
        )

    async def fetch_incident_detail(self, incident_id: str) -> IncidentDetail | None:
        detail = await self.source_of_truth.fetch_incident(incident_id)
        if detail is None:
            return None
        detail.raw_signals = await self.signal_store.fetch_incident_signals(incident_id)
        return detail

    async def submit_rca(self, incident_id: str, rca: RCARecord) -> IncidentDetail:
        detail = await self.source_of_truth.save_rca(incident_id, rca)
        detail.raw_signals = await self.signal_store.fetch_incident_signals(incident_id)
        await self._refresh_cache(incident_id)
        return detail

    async def update_status(self, incident_id: str, status: WorkItemStatus) -> IncidentSummary:
        summary = await self.source_of_truth.transition_incident(incident_id, status)
        await self._refresh_cache(incident_id)
        return summary

    async def timeseries(self, hours: int = 6) -> list[dict[str, Any]]:
        points = await self.source_of_truth.fetch_timeseries(hours=hours)
        return [point.model_dump(mode="json") for point in points]

    async def health(self) -> HealthSnapshot:
        incidents = await self.list_incidents()
        throughput = await self._throughput_last_window()
        return HealthSnapshot(
            ok=await self.source_of_truth.ping(),
            queue_depth=self.queue.qsize(),
            active_incidents=len(incidents),
            worker_count=self.worker_count,
            signals_last_window=int(throughput * 5),
            throughput_per_second=throughput,
        )

    async def _worker_loop(self, worker_number: int) -> None:
        del worker_number
        try:
            while not self._stop_event.is_set():
                signal = await self.queue.get()
                try:
                    await self._process_signal(signal)
                finally:
                    self.queue.task_done()
        except asyncio.CancelledError:
            raise

    async def _process_signal(self, signal: SignalPayload) -> None:
        component_lock = self._component_locks.setdefault(signal.component_id, asyncio.Lock())
        async with component_lock:
            incident = await self.source_of_truth.fetch_active_incident_by_component(signal.component_id)
            incident_id: str
            alert = self.alert_router.decide(signal)

            if incident is None:
                incident_id = await self.source_of_truth.create_incident(signal, alert)
                self._debounce_windows[signal.component_id] = DebounceWindow(
                    incident_id=incident_id,
                    opened_at=signal.observed_at,
                )
                await self.signal_store.append_alert(incident_id, alert)
            else:
                incident_id = incident["id"]
                debounce_window = self._debounce_windows.get(signal.component_id)
                if debounce_window is None:
                    self._debounce_windows[signal.component_id] = DebounceWindow(
                        incident_id=incident_id,
                        opened_at=signal.observed_at,
                    )
                elif signal.observed_at - debounce_window.opened_at > timedelta(seconds=10):
                    self._debounce_windows[signal.component_id] = DebounceWindow(
                        incident_id=incident_id,
                        opened_at=debounce_window.opened_at,
                    )

            await self.signal_store.append_signal(incident_id, signal)
            await self.source_of_truth.attach_signal(incident_id, signal, alert.severity)
            await self.source_of_truth.record_timeseries(alert.severity, signal.observed_at)
            await self._refresh_cache(incident_id)

        async with self._metrics_lock:
            self._recent_processed.append(utcnow().timestamp())
            self._trim_metrics_locked()

    async def _refresh_cache(self, incident_id: str) -> None:
        summary = await self.source_of_truth.fetch_incident_summary(incident_id)
        async with self._cache_lock:
            if summary is None or summary.status is WorkItemStatus.CLOSED:
                self._cache.pop(incident_id, None)
            else:
                self._cache[incident_id] = summary

    async def _metrics_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                await asyncio.sleep(5)
                throughput = await self._throughput_last_window()
                print(
                    f"[metrics] signals/sec={throughput:.2f} queue_depth={self.queue.qsize()} active_incidents={len(await self.list_incidents())}",
                    flush=True,
                )
        except asyncio.CancelledError:
            raise

    async def _throughput_last_window(self) -> float:
        async with self._metrics_lock:
            self._trim_metrics_locked()
            return len(self._recent_processed) / 5

    def _trim_metrics_locked(self) -> None:
        threshold = utcnow().timestamp() - 5
        while self._recent_processed and self._recent_processed[0] < threshold:
            self._recent_processed.popleft()


def build_service(storage_root: Path) -> IncidentService:
    return IncidentService(storage_root=storage_root)
