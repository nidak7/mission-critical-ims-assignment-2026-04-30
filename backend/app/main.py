from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from .models import RCARecord, SignalPayload, StatusChangeRequest, WorkItemStatus
from .service import BackpressureError, build_service
from .ui import render_detail, render_incident_feed, render_overview
from .workflow import TransitionError


ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = ROOT / "frontend"
STORAGE_ROOT = ROOT / "backend" / "storage"
service = build_service(STORAGE_ROOT)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await service.startup()
    try:
        yield
    finally:
        await service.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(title="Mission-Critical IMS", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.mount("/assets", StaticFiles(directory=FRONTEND_ROOT), name="frontend-assets")

    @app.get("/", response_class=FileResponse)
    async def frontend_index() -> FileResponse:
        return FileResponse(FRONTEND_ROOT / "index.html")

    @app.get("/health")
    async def health() -> dict:
        snapshot = await service.health()
        if not snapshot.ok:
            raise HTTPException(status_code=503, detail={"status": "DOWN"})
        return {"status": "UP"}

    @app.post("/api/signals", status_code=status.HTTP_202_ACCEPTED)
    async def ingest_signal(request: Request, signal: SignalPayload) -> dict[str, str]:
        client_key = request.client.host if request.client else "anonymous"
        if not await service.rate_limiter.allow(client_key):
            raise HTTPException(status_code=429, detail="Rate limit exceeded for signal ingestion.")

        try:
            return await service.enqueue_signal(signal)
        except BackpressureError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/incidents")
    async def list_incidents() -> list[dict]:
        return [incident.model_dump(mode="json") for incident in await service.list_incidents()]

    @app.get("/api/incidents/{incident_id}")
    async def get_incident(incident_id: str) -> dict:
        detail = await service.fetch_incident_detail(incident_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Incident not found.")
        return detail.model_dump(mode="json")

    @app.post("/api/incidents/{incident_id}/status")
    async def update_status(incident_id: str, request: StatusChangeRequest) -> dict:
        try:
            summary = await service.update_status(incident_id, request.status)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Incident not found.") from exc
        except TransitionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return summary.model_dump(mode="json")

    @app.post("/api/incidents/{incident_id}/rca")
    async def save_rca(incident_id: str, rca: RCARecord) -> dict:
        try:
            detail = await service.submit_rca(incident_id, rca)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Incident not found.") from exc
        except TransitionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return detail.model_dump(mode="json")

    @app.get("/api/metrics/timeseries")
    async def metrics(hours: int = 6) -> list[dict]:
        return await service.timeseries(hours=hours)

    @app.get("/ui/overview", response_class=HTMLResponse)
    async def overview_fragment() -> HTMLResponse:
        health = (await service.health()).model_dump(mode="json")
        incidents = [item.model_dump(mode="json") for item in await service.list_incidents()]
        return HTMLResponse(render_overview(health, incidents))

    @app.get("/ui/incidents", response_class=HTMLResponse)
    async def incident_feed_fragment() -> HTMLResponse:
        incidents = [item.model_dump(mode="json") for item in await service.list_incidents()]
        return HTMLResponse(render_incident_feed(incidents))

    @app.get("/ui/incidents/{incident_id}", response_class=HTMLResponse)
    async def incident_detail_fragment(incident_id: str) -> HTMLResponse:
        detail = await service.fetch_incident_detail(incident_id)
        if detail is None:
            return HTMLResponse(render_detail(None, banner="Incident not found.", banner_kind="error"))
        return HTMLResponse(render_detail(detail.model_dump(mode="json")))

    @app.post("/ui/incidents/{incident_id}/status", response_class=HTMLResponse)
    async def incident_status_fragment(incident_id: str, request: Request) -> HTMLResponse:
        form = await request.form()
        try:
            status_value = WorkItemStatus(str(form.get("status", "")))
            await service.update_status(incident_id, status_value)
            detail = await service.fetch_incident_detail(incident_id)
            banner = f"Incident moved to {status_value.value}."
            banner_kind = "success"
        except KeyError:
            detail = None
            banner = "Incident not found."
            banner_kind = "error"
        except (ValueError, TransitionError) as exc:
            detail = await service.fetch_incident_detail(incident_id)
            banner = str(exc)
            banner_kind = "error"
        return HTMLResponse(render_detail(detail.model_dump(mode="json") if detail else None, banner=banner, banner_kind=banner_kind))

    @app.post("/ui/incidents/{incident_id}/rca", response_class=HTMLResponse)
    async def incident_rca_fragment(incident_id: str, request: Request) -> HTMLResponse:
        form = await request.form()
        try:
            rca = RCARecord(
                start_time=_parse_form_datetime(str(form.get("start_time", ""))),
                end_time=_parse_form_datetime(str(form.get("end_time", ""))),
                root_cause_category=str(form.get("root_cause_category", "")),
                fix_applied=str(form.get("fix_applied", "")),
                prevention_steps=str(form.get("prevention_steps", "")),
            )
            detail = await service.submit_rca(incident_id, rca)
            banner = "RCA saved. Close is now permitted once the incident is resolved."
            banner_kind = "success"
        except KeyError:
            detail = None
            banner = "Incident not found."
            banner_kind = "error"
        except ValidationError as exc:
            detail = await service.fetch_incident_detail(incident_id)
            banner = exc.errors()[0]["msg"]
            banner_kind = "error"
        except Exception as exc:
            detail = await service.fetch_incident_detail(incident_id)
            banner = str(exc)
            banner_kind = "error"
        return HTMLResponse(render_detail(detail.model_dump(mode="json") if detail else None, banner=banner, banner_kind=banner_kind))

    return app


def _parse_form_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
