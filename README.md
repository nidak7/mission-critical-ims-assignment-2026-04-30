# Incident Management System

This repository contains my submission for the Infrastructure / SRE intern assignment.

GitHub: [https://github.com/nidak7/mission-critical-ims-assignment-2026-04-30](https://github.com/nidak7/mission-critical-ims-assignment-2026-04-30)

## Overview

The project is a small Incident Management System built around three main ideas:

- ingest signals asynchronously
- group repeated signals from the same component into a single incident
- drive the incident through a simple workflow until RCA is completed and the incident can be closed

The application includes a backend API, a lightweight dashboard, sample data, tests, and local packaging through Docker Compose.

## Tech stack

- FastAPI
- asyncio
- SQLite
- HTMX

## Repository structure

- `backend/` application code, workflow logic, storage, and tests
- `frontend/` dashboard assets
- `sample-data/` demo/reset scripts
- `docs/` supporting material, including the PDF generator

## Running locally

Start from a clean demo state:

```bash
python sample-data/reset_demo_state.py
python backend/run_server.py
```

Then open:

```text
http://localhost:8000
```

To load sample incidents:

```bash
python sample-data/send_scenario.py
```

## Docker

```bash
docker compose up --build
```

## Tests

```bash
python -m unittest backend.tests.test_rca_validation backend.tests.test_service_flow backend.tests.test_rate_limiter
```

## Expected demo flow

1. Open the dashboard.
2. Select `RDBMS_PRIMARY_01`.
3. Move it to `INVESTIGATING`.
4. Move it to `RESOLVED`.
5. Fill in the RCA form.
6. Close the incident.

## Non-functional work included

The assignment also asked for attention to operational concerns, so the following are included:

- rate limiting on the ingestion endpoint
- bounded async queue for backpressure
- retry logic for database writes
- transactional status updates
- `/health` endpoint
- throughput logging every 5 seconds
- unit tests for RCA validation, service flow, and rate limiting

## Notes

- Structured incident and RCA data are stored in SQLite.
- Raw signal payloads are stored separately as JSONL files.
- The repository is public and includes the code, config, and build scripts needed to run the project.
