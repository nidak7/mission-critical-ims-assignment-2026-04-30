# Incident Management System

Take-home assignment for the Infrastructure / SRE intern role.

GitHub repo: [https://github.com/nidak7/mission-critical-ims-assignment-2026-04-30](https://github.com/nidak7/mission-critical-ims-assignment-2026-04-30)

## What is included

- `backend/` FastAPI app, workflow logic, storage, and tests
- `frontend/` dashboard
- `sample-data/` reset script and demo incident data
- `docker-compose.yml` for local startup

## Main features

- async signal ingestion
- debouncing by component
- separate raw signal and incident/RCA storage
- incident state flow: `OPEN -> INVESTIGATING -> RESOLVED -> CLOSED`
- RCA required before close
- simple dashboard for active incidents and RCA entry

## Run locally

```bash
python sample-data/reset_demo_state.py
python backend/run_server.py
```

Open `http://localhost:8000`

To load the demo incidents:

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

## Demo flow

1. Open the dashboard.
2. Select `RDBMS_PRIMARY_01`.
3. Move it to `INVESTIGATING`.
4. Move it to `RESOLVED`.
5. Fill the RCA form.
6. Close the incident.

## Non-functional items

- rate limiting on the ingestion API
- bounded async queue for backpressure
- retry logic around database writes
- `/health` endpoint
- throughput logging every 5 seconds
- transactional status updates
- unit tests for RCA and service flow

## Notes

- The app uses SQLite for structured data and JSONL files for raw signal storage.
- The repo is public and contains the code, build scripts, and config needed to run the project.
- A submission PDF can be generated with `python docs/generate_submission_pdf.py "Your Name"`.
