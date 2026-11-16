# Data quality audit — 2026-11-16

## Scope and method

Audited the PostgreSQL schema, generator, validator, data dictionary, existing exports, and pytest suite. All profiles were regenerated twice with seed `20261022`; this report refers to the regenerated exports under `data/`. Baseline records were checked independently of `ground_truth.*`; ground truth is read only by the wrapper that compares detector output with expected labels.

## Corrections made during audit

Three verified defects were corrected, then all affected profiles/tests were rerun:

1. Appointment day selection used a stride that collapsed Tiny and Starter workload onto too few dates. It now cycles deterministically over a weekday-weighted day list with a coprime stride. Weekend demand is one-third of weekday demand.
2. Baseline allocation did not enforce vehicle capability/length, reefer-yard selection, yard overlap, or concurrent labor capacity. The allocator and independent validator now enforce these constraints.
3. SQL seeds serialized optional values as `''`; PostgreSQL cannot cast that to nullable timestamp/FK types. Empty optional values now serialize as `NULL`.

The deterministic no-show rule was also changed from a single record per profile to recurring `i % 37 == 1` candidates, preserving seed and ID formats while producing a non-trivial no-show pattern.

## Actual exported row counts

| Entity | Tiny | Starter | Full |
|---|---:|---:|---:|
| facilities | 1 | 2 | 10 |
| docks / yard_slots | 5 / 10 | 20 / 40 | 100 / 200 |
| carriers / vehicles | 5 / 15 | 8 / 60 | 40 / 300 |
| labor_shifts / capacity_calendars | 15 / 14 | 57 / 56 | 1,201 / 1,200 |
| shipments / handling_requirements | 50 / 50 | 1,000 / 1,000 | 20,000 / 20,000 |
| appointments / appointment_shipments | 50 / 50 | 1,000 / 1,000 | 20,000 / 20,000 |
| dock_reservations / yard_reservations / labor_allocations | 34 / 34 / 34 | 234 / 234 / 234 | 1,709 / 1,709 / 1,709 |
| checkin_events / operational_events | 34 / 250 | 234 / 5,000 | 1,709 / 100,000 |
| exceptions / derived_metrics / utilization metrics | 5 / 50 / 1 | 5 / 1,000 / 2 | 5 / 20,000 / 10 |

## Validation and anomaly findings

Every baseline had **0 issues**. Each injected dataset had exactly **5 issues**, one each of `DOCK_CAPACITY_EXCEEDED`, `DOCK_INCOMPATIBLE`, `CHECKIN_DATE_VIOLATION`, `LABOR_UNAVAILABLE`, and `MISSING_NO_SHOW_EVENT`; no unexpected or missing issue types occurred.

The validator exercises PK/FK and bridge integrity; dock/yard interval capacity; dock, vehicle and reefer-yard compatibility; labor shift coverage, skill and concurrent worker capacity; event sequence ordering/lifecycle; no-show event presence; and event-derived metric reconciliation. The Full export has 100,000 unique event IDs, 100,000 unique `(appointment_id, sequence_no)` pairs, and exactly five events for each of 20,000 appointments. No duplicate or filler event was found.

## Operational measurements

| Profile | Avg dock utilization | Average wait (min) | P95 wait (min) | No-shows | Waitlisted |
|---|---:|---:|---:|---:|---:|
| Tiny | 10.6429% | 9.844 | 15 | 2 | 16 |
| Starter | 8.9836% | 9.145 | 15 | 6 | 766 |
| Full | 3.2916% | 9.560 | 15 | 49 | 18,291 |

Demand is weekday weighted (approximately 417 Full requests on weekdays and 139 on weekend days). The high Full waitlist percentage and low average utilization are intentional consequences of rigid peak-hour requested slots with no rescheduling; this gives useful congestion/waitlist cases, but is a modeling caveat rather than a representation of a continuously optimized yard.

## Export and reproducibility checks

CSV and JSON records were compared by test, and every SQL seed has one `INSERT` per exported record. The SQL seed references only schema tables and now emits `NULL` for nullable values. PostgreSQL-compatible syntax and type casting were statically checked; no `psql` client/server was available in the workspace for a live load test.

Each profile was regenerated twice to `data/<profile>` and `reports/audit_repro/<profile>`. All **84 files** in each profile export (including baseline files, manifests, ground truth and SQL) had identical relative names and SHA-256 content hashes.

## Tests executed

`python -m pytest -q` completed successfully: **7 passed in 5.09s**. Tests cover all baseline profiles, anomaly labels, reproducibility, yard-capacity boundary, event order, missing no-show event, metric reconciliation, and CSV/JSON/SQL parity.

## Remaining risks and readiness

The generated data is ready for the next development phase as a deterministic, constraint-valid synthetic dataset. Remaining modeling risks: fixed arrival offsets cap P95 wait at 15 minutes; utilization is aggregate scheduled utilization rather than event-observed occupancy; and SQL was not loaded into a live PostgreSQL instance in this environment. A future scheduler integration should add a database-backed seed-load test and may choose richer rescheduling/queue behavior.
