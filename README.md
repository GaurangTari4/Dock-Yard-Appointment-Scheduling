# Dock & Yard Appointment Scheduling

A deterministic synthetic logistics data generator, PostgreSQL-backed FastAPI scheduler, and Streamlit operations dashboard. It models appointments across compatible docks, yard slots, labor shifts, vehicles, and shipment handling requirements.

## Business problem

Dock and yard operations need to allocate scarce physical and labor resources while retaining an auditable history of appointment decisions and gate events. This project provides a reproducible synthetic baseline and a working scheduling workflow for demonstrations, integration testing, and analytics development.

## Architecture

```text
Generator + validator (fixed seed)
        |-- valid baseline SQL --> PostgreSQL 16 --> FastAPI --> Streamlit
        '-- injected anomalies + ground truth (kept outside operational tables)
```

The provided Compose workflow applies the SQL schema and Alembic migration, generates a selected dataset profile, loads only `baseline/seed_data.sql`, verifies it, then starts FastAPI and Streamlit.

## Technology stack

Python 3.12, FastAPI, Pydantic, SQLAlchemy 2, Alembic, PostgreSQL 16, Streamlit, pytest, and Docker Compose.

## Core features

- Deterministic Tiny, Starter, and Full synthetic data profiles.
- First-feasible scheduling and rescheduling with decision provenance.
- Dock, yard, labor, shipment, vehicle, load-type, and time-window constraints.
- Immutable appointment state events and preserved superseded reservations.
- Gate lifecycle operations, derived waiting/service/turnaround metrics, and exception detection.
- Calendar, availability, appointment, exception, and timeline views in Streamlit.

## Entities and relationships

Facilities own docks, yard slots, labor shifts, and capacity calendars. Carriers own vehicles and shipments; every generated shipment has one handling requirement. Appointments connect to shipments through `appointment_shipments` and may receive dock, yard, and labor reservations. Appointments also have operational events, immutable state events, check-in records, exceptions, and derived metrics.

See [entity relationships](docs/entity_relationships.md) and the [data dictionary](docs/data_dictionary.md).

## Scheduling constraints

Candidates require an active dock compatible with the shipment load type and vehicle dimensions, a compatible available yard slot, an active qualified labor shift with available capacity, and a facility operating window. Existing active reservations cannot overlap. The default requested-time deviation is zero minutes; out-of-window scheduling requires an explicit approved override and reason, recorded in immutable decision provenance.

## Synthetic datasets

All profiles use seed `20261022` and a simulation start of 2026-10-22.

| Profile | Facilities | Docks | Appointments | Operational events | Days |
|---|---:|---:|---:|---:|---:|
| Tiny | 1 | 5 | 50 | 250 | 7 |
| Starter | 2 | 20 | 1,000 | 5,000 | 14 |
| Full | 10 | 100 | 20,000 | 100,000 | 60 |

Generate data locally:

```powershell
python -m src.generator --profile tiny --seed 20261022 --output data/generated/tiny
python -m src.generator --profile starter --seed 20261022 --output data/generated/starter
python -m src.generator --profile full --seed 20261022 --output data/generated/full
python -m src.validation --input data/generated/full/baseline
```

Each output has CSV, JSON, a valid `baseline/seed_data.sql`, a manifest with SHA-256 checksums, and validation output. Rerun the same command twice and compare `manifest.json` checksums to verify reproducibility. Generated Full data is deliberately excluded from this repository.

## Controlled anomaly scenarios

The generator produces a valid `baseline/` and a separate injected output containing exactly five labelled scenarios:

1. Dock capacity overlap.
2. Incompatible dock assignment.
3. Early check-in timestamp.
4. Labor allocation outside the valid shift window.
5. Missing no-show event.

Ground-truth labels are kept in `ground_truth.csv/json` in generated injected output only. The operational baseline loader never imports those labels or injected records.

## Appointment lifecycle

The live API supports:

```text
REQUESTED -> SCHEDULED / RESCHEDULED -> ARRIVED -> CHECKED_IN
          -> IN_SERVICE -> COMPLETED -> DEPARTED
```

WAITLISTED, CANCELLED, NO_SHOW, and RESCHEDULED follow documented transition policy. Completion must be strictly after service start. History is appended, never overwritten.

## Docker setup

Docker reproducibility files are included but **were not independently executed for this publication copy**. Copy `.env.example` to `.env`, replace the password placeholder, then run from the repository root:

```powershell
Copy-Item .env.example .env
docker compose -p dockyarddemo up -d --build
docker compose -p dockyarddemo ps
```

Default published ports are PostgreSQL `55432`, API `18000` (`/docs` available there), and dashboard `18501`. Set `DATASET_PROFILE=full` in `.env` before first startup for the Full baseline. The loader uses named volumes and never silently replaces a populated database; explicitly remove only the Compose project's volumes to reload a different profile:

```powershell
docker compose -p dockyarddemo down -v
```

## Local development

Create a virtual environment, install `requirements.txt`, and set `DATABASE_URL` before importing the application. Run the API with `uvicorn app.main:app --reload` and the dashboard with `streamlit run dashboard/app.py`. Database schema is in `database/schema.sql`; migrations are in `alembic/`.

## API endpoints

- `GET /health`, `/facilities`, `/facilities/{id}/docks`
- `GET/POST /appointments`, `POST /appointments/{id}/schedule`, `/reschedule`
- `GET /availability/docks`, `/yard`, `/labor`
- `POST /appointments/{id}/arrive`, `/check-in`, `/service-start`, `/service-complete`, `/depart`
- `GET /appointments/{id}/timeline`, `GET /exceptions`, `POST /exceptions/detect`
- `GET /analytics/overview`, `GET /calendar/docks`

## Testing and verification

Generator-only checks are safe without a database:

```powershell
python -m pytest tests/test_generator.py tests/test_dashboard.py -q
```

Database integration tests require an isolated test database and explicit environment configuration. Do not aim them at production data. The bootstrap verifier is `scripts/verify_loaded_dataset.py` and validates manifest row counts, foreign-key validation, dock overlap, and event ordering.

## Data provenance and limitations

All included logic and generated data are synthetic. No production data, credentials, generated Full exports, database volumes, or `.env` files are included.

The retained acceptance report documents a known interval-aware labor-capacity audit concern: 98 overlapping-worker peaks in a fresh isolated clone and 713 in the source production snapshot. This is a known limitation, not a claimed passing constraint. Full browser form-interaction acceptance and complete POST benchmark evidence also remain outstanding. See [end-to-end acceptance](reports/end_to_end_acceptance.md).

No license is included because no existing license or user-approved licensing decision was found.
