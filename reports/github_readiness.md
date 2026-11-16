# GitHub readiness report

Date: 2026-11-16

## Status

**CONDITIONAL — clean packaging complete; Docker and Python execution were intentionally not performed.**

This publication copy was created in the requested publication folder. The original project, databases, Docker containers, networks, and volumes were not modified, reset, restarted, or inspected through Docker during this task.

## Final structure

```text
GitHub-Ready/
  app/                 FastAPI backend
  dashboard/           Streamlit application and API client
  src/                 deterministic generator, evaluator, validator
  database/             PostgreSQL schema and baseline verifier
  alembic/              lifecycle/schema migration
  config/               Tiny, Starter, Full profile configuration
  scripts/              bootstrap, database verification, benchmark utility
  tests/                generator, dashboard, and integration tests
  docs/                 data dictionary and relationship documentation
  reports/              selected Markdown evaluation evidence
  Dockerfile.api
  Dockerfile.dashboard
  compose.yaml
  .env.example
  .gitignore
  .dockerignore
  README.md
```

## Retained files

- Backend (`app/`), dashboard (`dashboard/`), deterministic generator/validation (`src/`), schema (`database/`), Alembic migration (`alembic/`), profiles (`config/`), scripts, tests, technical docs, dependencies, and selected Markdown evaluation reports.
- Docker reproduction assets are self-contained: `Dockerfile.api`, `Dockerfile.dashboard`, `compose.yaml`, `.env.example`, `scripts/bootstrap_database.sh`, and `scripts/verify_loaded_dataset.py` only reference files in this repository.
- The profile configuration retains seed `20261022`, Tiny/Starter/Full definitions, and the Full target of 10 facilities, 100 docks, 20,000 appointments, 100,000 events, and 60 days.

## Excluded files

- Generated dataset directories, including all Full CSV/JSON/SQL output and duplicated audit reproduction copies.
- `.venv`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.env`, logs, PostgreSQL dumps/volumes, Docker metadata, benchmark output JSON/CSV, temporary screenshots, and existing Git metadata.
- No source Compose file tied to the existing local services was copied.

## Lightweight validation performed

| Check | Result |
|---|---|
| Required folders/files present | PASS |
| Excluded `.env`, data, cache, and Git folders absent | PASS |
| Files larger than 10 MB | None found |
| Scan for passwords, API keys, private-key blocks, source-workspace paths, and machine paths | No matches in included files |
| README references Docker files/bootstrap scripts that exist | PASS |
| Python syntax validation | Not executed: host `python`/`py` launcher was unavailable |
| Unit tests | Not executed: no usable host Python runtime; Docker execution prohibited |
| Docker build/start/load validation | Not executed by instruction |

## Docker and data reproduction

Docker files are included but **not independently verified in this publication copy**. The documented workflow uses PostgreSQL 16, named volumes, a profile-selecting generator/loader, schema plus Alembic migration, baseline-only SQL loading, and post-load manifest/integrity verification. It preserves a populated volume rather than silently replacing it.

The README documents commands to generate Tiny, Starter, and Full outputs. Generated injected anomalies and ground truth remain separate from the baseline SQL loader.

## Known limitations

- Existing acceptance evidence records interval-aware labor-capacity overages: 98 peaks in a fresh isolated clone and 713 in the source production snapshot. This is a disclosed baseline limitation, not a passing capacity claim.
- Full browser form-interaction acceptance and complete POST benchmark coverage remain open according to retained reports.
- A license was not added because no existing license or explicit licensing decision was available.

## Manual next steps

1. Review `README.md` and choose a license.
2. Copy `.env.example` to `.env` and set a local password.
3. Run the documented Docker workflow in a clean environment.
4. Run generator/unit/integration tests with a usable Python runtime and an isolated database.
5. Initialize Git and publish manually only after review. No Git repository, commit, remote, or push was created by this task.
