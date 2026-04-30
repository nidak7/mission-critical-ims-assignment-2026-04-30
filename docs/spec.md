# Assignment Spec

## Original prompt

Build a resilient Incident Management System (IMS) with:

- Async signal ingestion and backpressure handling for bursts up to 10,000 signals/sec.
- A debouncing rule that collapses many signals for one component into a single work item.
- Separate storage concerns for raw payloads, transactional work items/RCAs, dashboard cache, and time-series aggregates.
- Strategy and State patterns for alert routing and workflow transitions.
- Mandatory RCA enforcement before the `CLOSED` transition.
- A responsive frontend with live feed, incident detail, and RCA form.
- Rate limiting, `/health`, throughput logging, retry-friendly async architecture, tests, and delivery docs.

## Implementation choices

- Backend framework: FastAPI
- Async primitives: `asyncio.Queue`, `asyncio.TaskGroup`, `asyncio.Lock`
- Transactional store: SQLite with WAL mode via `aiosqlite`
- Raw signal sink: JSONL audit files per incident plus a global append-only log
- Frontend: HTMX + static HTML/CSS, served by the backend for zero-build local setup
- Timeseries: minute-bucket aggregates in SQLite
