# Build Prompt Record

This repository was built against the following engineering brief:

> Engineering Challenge: Mission-Critical Incident Management System (IMS)
>
> Build a resilient incident management platform for a distributed stack. The system must ingest high-volume signals, debounce duplicate bursts, store raw payloads separately from transactional work items, enforce a workflow with mandatory RCA before closure, expose health and throughput metrics, and provide a responsive frontend for incident triage and RCA entry.

Additional implementation intent:

- Optimize for clear separation of responsibilities so the reviewer can see how each rubric item maps to code.
- Keep the frontend zero-build and easy to run in a take-home review environment.
- Prefer explicit code constructs and documentation over magic abstractions.
