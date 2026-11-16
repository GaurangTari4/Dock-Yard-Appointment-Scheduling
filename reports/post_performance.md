# POST Scheduling Performance

## Environment

Dedicated Compose acceptance services: API `localhost:8002`, dashboard `localhost:8503`, PostgreSQL 16 database `logistics_test`. Production API/dashboard remained on ports 8001/8502 and the production database was not reset.

## Readiness diagnosis

The benchmark's original `ConnectionRefusedError` was a startup race. `depends_on: service_started` does not mean Uvicorn is listening. After the container had started, DNS (`logistics-api-test`), `/health`, and the configured `DATABASE_URL` to `logistics_test` were all verified. `scripts/benchmark_scheduling.py` now polls `/health` for up to 30 bounded attempts with a one-second request timeout and retains the last diagnostic instead of relying on an arbitrary fixed delay.

## Result status

The health-gated runner reached the acceptance API; its logs include successful 201 appointment creates and 200 scheduling POSTs. Aggregate benchmark stdout was not durably captured, so no mean, percentile, throughput, success-rate, or conflict-rate values are reported. The 100-request measurement matrix is therefore **not complete** and must be rerun with durable JSON output before performance acceptance.

No performance figures in this document are inferred from API logs.

## Captured measurements

The following completed workloads were copied verbatim to `post_benchmark_results.json` and `.csv`. Each row has 100 measured POST requests against `logistics_test`.

| Workload | Concurrency | Mean ms | P50 | P95 | P99 | Max | RPS | Success | Waitlists | HTTP errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Schedule | 1 | 93.589 | 93.203 | 107.044 | 116.803 | 134.619 | 10.662 | 100 | 0 | 0 |
| Schedule | 5 | 467.305 | 457.463 | 561.190 | 584.037 | 614.404 | 10.487 | 100 | 0 | 0 |
| Schedule | 10 | 925.457 | 946.549 | 1063.944 | 1071.382 | 1080.498 | 10.286 | 100 | 0 | 0 |
| Schedule | 20 | 1870.966 | 2055.290 | 2112.228 | 2129.590 | 2140.775 | 9.703 | 100 | 0 | 0 |
| Reschedule | 1 | 105.765 | 104.499 | 138.095 | 148.170 | 157.049 | 9.438 | 100 | 0 | 0 |

The reschedule concurrency-5 seed stage stopped because at least one fixture did not reach `SCHEDULED`; the script correctly stopped instead of measuring invalid 409 reschedules. The remaining reschedule concurrency levels, explicit concurrent workload rows, and intentional-conflict rows are not complete. Thus this is a partial benchmark, not performance acceptance.

## Concurrency investigation update

The subsequent concurrent reschedule run failed with PostgreSQL `DeadlockDetected` errors, not a business conflict. API logs showed transactions waiting on one another while locking resource rows. `schedule()` previously issued unordered `FOR UPDATE` scans over the facility docks and matching labor shifts. It now orders dock locks by `dock_id` and shift locks by `labor_shift_id`, preserving the same rows and constraints while enforcing a deterministic acquisition order. The benchmark must be restarted from a fresh `logistics_test` clone after this correction; no post-fix concurrency values are claimed here.
