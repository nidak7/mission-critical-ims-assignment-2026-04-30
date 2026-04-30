from __future__ import annotations

import asyncio
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import backend.app.main as main_module
from backend.app.rate_limiter import TokenBucketRateLimiter
from backend.app.service import IncidentService, build_service


class TestAppHarness:
    def __init__(
        self,
        *,
        worker_count: int | None = None,
        queue_maxsize: int | None = None,
        rate_limiter: TokenBucketRateLimiter | None = None,
    ) -> None:
        self.original_service = main_module.service
        self.storage_root = ROOT / "backend" / "storage" / f"test-app-{uuid4().hex}"
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.service: IncidentService = build_service(self.storage_root)
        if worker_count is not None:
            self.service.worker_count = worker_count
        if queue_maxsize is not None:
            self.service.queue = asyncio.Queue(maxsize=queue_maxsize)
        if rate_limiter is not None:
            self.service.rate_limiter = rate_limiter

        main_module.service = self.service
        self.app = main_module.create_app()
        self.client = TestClient(self.app)
        self.client.__enter__()

    def close(self) -> None:
        self.client.__exit__(None, None, None)
        main_module.service = self.original_service
        shutil.rmtree(self.storage_root, ignore_errors=True)

    def wait_for(self, condition: Callable[[], bool], *, timeout: float = 3.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if condition():
                return
            time.sleep(0.05)
        raise AssertionError("Timed out waiting for test condition.")

    def list_incidents(self) -> list[dict[str, Any]]:
        response = self.client.get("/api/incidents")
        response.raise_for_status()
        return response.json()

    def wait_for_incident_count(self, expected_count: int, *, timeout: float = 3.0) -> list[dict[str, Any]]:
        incidents: list[dict[str, Any]] = []

        def condition() -> bool:
            nonlocal incidents
            incidents = self.list_incidents()
            return len(incidents) == expected_count

        self.wait_for(condition, timeout=timeout)
        return incidents
