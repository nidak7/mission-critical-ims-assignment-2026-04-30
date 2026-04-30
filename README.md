# Incident Management System

Small take-home project for the IMS assignment.

## What it does

- accepts incident signals through an async API
- groups repeated signals for the same component into one incident
- stores raw signals separately from incident and RCA data
- enforces the incident flow: `OPEN -> INVESTIGATING -> RESOLVED -> CLOSED`
- blocks closing unless RCA is filled in
- shows active incidents in a simple dashboard

## Stack

- FastAPI
- asyncio
- SQLite
- HTMX

## Project structure

- `backend/` API, workflow, storage, tests
- `frontend/` dashboard
- `sample-data/` demo scripts and sample events
- `docs/` assignment notes

## Run it

```bash
python sample-data/reset_demo_state.py
python backend/run_server.py
```

Open `http://localhost:8000`

To load demo incidents:

```bash
python sample-data/send_scenario.py
```

## Demo flow

1. Open the dashboard.
2. Click the RDBMS incident.
3. Move it to `INVESTIGATING`.
4. Move it to `RESOLVED`.
5. Fill the RCA form.
6. Close the incident.

## Tests

```bash
python -m unittest backend.tests.test_rca_validation backend.tests.test_service_flow backend.tests.test_rate_limiter
```

## Notes

- `/health` returns basic service status.
- Throughput is printed every 5 seconds.
- Docker support is included through `docker-compose.yml`.
