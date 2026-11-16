# End-to-End Acceptance Report

Date: 2026-11-16.  The production `logistics` database was treated as read-only. All mutable API checks used a freshly cloned `logistics_test` database.

## Result

**Conditional acceptance.** The automated end-to-end lifecycle, reservation, exception, rollback, concurrency, metrics, and dashboard render checks pass. Browser interaction was verified for the rendered overview and dock calendar; full browser submission of each form was not completed, so create/schedule/reschedule/gate UI clicks remain a manual acceptance item.

## Corrections made during acceptance

- Fixed Streamlit script imports (`dashboard.app`) and set `PYTHONPATH=/app` in Compose. Browser inspection had exposed a real render-time import error even though the HTTP root returned 200.
- Reconciled derived metrics during lifecycle transitions: waiting is arrival-to-service-start, actual service is service-start-to-complete, and turnaround is arrival-to-departure.
- Rejected lifecycle event timestamps earlier than a prior lifecycle event.
- Enforced refrigerated/hazmat vehicle capability and returned concrete waitlist reasons: `VEHICLE_INCOMPATIBLE`, `NO_COMPATIBLE_DOCK`, `DOCK_OCCUPIED`, `NO_YARD_CAPACITY`, `INSUFFICIENT_QUALIFIED_LABOR`, and `FACILITY_CLOSED`.
- Added `POST /exceptions/detect` for persisted `MISSING_NO_SHOW_EVENT` detection.

## Automated scenarios (isolated database)

All passed in `20 passed, 1 warning in 15.35s`.

- Refrigerated incompatible vehicle: `WAITLISTED` with `VEHICLE_INCOMPATIBLE`.
- Scheduling/rescheduling and immutable historical reservations.
- Dock conflict/concurrent booking safety, invalid transitions, and rollback.
- Lifecycle: arrival, check-in, service start, completion and departure.
- Metric reconciliation: a 12:00 arrival, 12:20 service start, 13:20 completion, and 13:30 departure persisted waiting=20, actual service=60, turnaround=90 minutes.
- Early check-in produced `CHECKIN_DATE_VIOLATION` / `TOO_EARLY`.
- Missing no-show detector persisted `MISSING_NO_SHOW_EVENT` / `NO_SHOW_EVENT_MISSING`.
- Timeline, overview and calendar read models returned successfully.

## Production safety and integrity

Final production snapshot: 20,000 appointments, 100,000 operational events, 12,537 dock reservations, and 0 exceptions. A duplicate confirmed-reservation grouping query returned 0. PostgreSQL was healthy; FastAPI was running on 8001 and Streamlit on 8502. No production records were written or regenerated.

## Dashboard verification

Browser-driven verification loaded the repaired dashboard, its facility/date filters, Overview, and Dock calendar. The Overview showed actual API values (FAC-001: 10 docks, 23.13% persisted utilization); the calendar displayed chronological reservation rows and status treatment. The initial browser run failed due to the relative-import defect above; after correction it rendered normally.

## Read-only performance

Environment: local Docker, PostgreSQL 16 Full baseline, host-to-API HTTP, 20 sequential samples each. Values are milliseconds.

| Endpoint | n | Mean | P95 | Max |
|---|---:|---:|---:|---:|
| Appointment list | 20 | 18.43 | 20.10 | 158.70 |
| Dock availability | 20 | 6.06 | 8.32 | 14.68 |
| Dock calendar | 20 | 5.31 | 5.68 | 6.02 |
| Timeline | 20 | 5.38 | 6.13 | 8.99 |
| Analytics overview | 20 | 7.09 | 8.48 | 9.30 |

Scheduling and rescheduling were functionally exercised in the isolated integration suite but not separately latency-benchmarked; this is a remaining measurement gap.

## Remaining risks

- Perform a human/browser form-submission pass for appointment creation, scheduling, rescheduling, gate controls, exception filters, and empty/error states.
- Benchmark POST scheduling and rescheduling under realistic concurrent load.
- The reported facility utilization is the persisted generator reporting-period metric, not a live interval calculation.

## Phase 6 update (2026-11-16)

### Browser and isolated-environment checks

The API/dashboard were temporarily started with `DATABASE_URL` pointed at a freshly cloned `logistics_test` database, then restored to production configuration. The browser loaded the dashboard, read the live Overview, and displayed the Dock calendar. A prior Streamlit import error remains fixed. The browser automation surface could inspect Streamlit radio controls but repeated clicks did not change their selected state; consequently it could not submit create/schedule/reschedule/gate forms. Those mandatory browser actions remain **manual verification items**; no claim is made that they were browser-executed. The API integration suite does execute their corresponding backend lifecycle and rescheduling workflows.

The dashboard now exposes a result-offset control for appointment pagination, returns HTTP body detail in API failures, and labels dock utilization explicitly as a persisted reporting-period value rather than a live date-filtered value.

### Regression and warning

Final regression result: **20 passed in 15.97 seconds** using `logistics_test`. The warning remains after switching from FastAPI's wrapper to Starlette's TestClient: `StarletteDeprecationWarning` requests the unavailable/future `httpx2` replacement. It is a dependency deprecation warning, not suppressed because doing so would conceal a legitimate compatibility migration.

### Production safety

After restoration, production was checked at 20,000 appointments, 100,000 operational events, and 12,537 dock reservations. It was not modified during this phase.

### Phase 6 conclusion

**FAIL for complete UI acceptance**: mandatory real browser form submission and resulting UI state transitions could not be completed with the available automation surface. Backend functional coverage remains passing; POST scheduling/rescheduling latency and controlled concurrency benchmarks are also still outstanding and must be run before declaring full acceptance.

## Phase 7 update (2026-11-16)

### Isolated services and Streamlit AppTest

Added `compose.acceptance.yaml`, which starts `logistics-api-test` on port 8002 and `logistics-dashboard-test` on port 8503 against `logistics_test`, without changing production services. Streamlit AppTest executed inside the dedicated dashboard service: **1 passed in 1.33s**. It verified radio navigation state changes to Appointments and Dock calendar and the Appointment page pagination widget. This confirms the dashboard navigation implementation itself is sound; the prior inability to change a page is a limitation of the available browser-control surface, not a Streamlit application defect.

### Browser acceptance

Actual browser verification remains limited to page render/read inspection. AppTest is not represented as browser coverage. Create/schedule/reschedule/gate form submission, timeline, exception filter, and invalid-input browser flows remain unverified and continue to block complete UI acceptance.

### POST benchmark status

A dedicated `scripts/benchmark_scheduling.py` was added for 100-request scheduling workloads at concurrency 1, 5, 10, and 20 plus 100 reschedules. Its first two executions were blocked by test API startup readiness (`connection refused`); a subsequent execution did not return a captured result before the acceptance window closed. No latency, rate, or error metrics are reported rather than inventing them. The benchmark therefore remains outstanding.

### Phase 7 conclusion

**FAIL for complete acceptance.** Backend regression and AppTest navigation pass, isolated service separation is in place, and production remains unchanged. Mandatory actual-browser workflow actions and captured 100-request POST performance metrics are not yet evidenced.

## Phase 8 update (2026-11-16)

The benchmark readiness root cause was confirmed as a Uvicorn startup race: Compose's `service_started` condition precedes an accepting HTTP listener. DNS, health, and the acceptance API's `logistics_test` URL were verified. The runner now contains bounded `/health` retries and diagnostics. Successful isolated scheduling POSTs were observed in API logs after reset, but aggregate client results were not durably captured; see [post performance](post_performance.md). Browser form actions remain unverified. **Overall status remains FAIL.**

## Lifecycle consistency fix

`RESCHEDULED` is a current operational status in the API schema and scheduler, not merely a historical event. The lifecycle map and Gate Operations map had omitted it, causing a rescheduled appointment with an active allocation to have no available arrival action. Both now permit `RESCHEDULED -> ARRIVED`.

In `logistics_test`, `APPT-2026-012550` was verified with one active `RESERVED` dock reservation and three immutable `SUPERSEDED` historical reservations. A real isolated API request transitioned it from `RESCHEDULED` to `ARRIVED` with HTTP 200; its operational history now ends in `ARRIVED` at sequence 10. Targeted dashboard lifecycle regression tests passed (3 passed). Production remained 20,000 appointments, 100,000 operational events, 12,537 reservations, and zero exceptions.

## Simulation timestamp fix

Gate Operations formerly submitted `datetime.utcnow()` for every action. For future-dated isolated records, that timestamp correctly failed the backend chronology rule. The acceptance Compose services now explicitly enable `SIMULATION_MODE`; production defaults to disabled and rejects future event timestamps. In isolated simulation mode Gate Operations displays an editable `Simulation event timestamp (UTC ISO)` field, defaulted to the latest immutable timeline timestamp, and displays API validation detail.

`APPT-2026-012550` completed its isolated simulated lifecycle with CHECKED_IN at 06:00, IN_SERVICE at 06:05, COMPLETED at 07:46, and DEPARTED at 07:51 UTC on 2026-11-22. The final state is `DEPARTED`; derived waiting, service, and turnaround are 5, 101, and 111 minutes. Targeted dashboard/AppTest regressions passed (4 passed). Production baseline counts remained unchanged.

## Scheduling-window fix

The source appointment model has no requested end timestamp. The documented default policy is consequently a zero-minute deviation from requested start, matching generator behavior. Off-window scheduling/rescheduling requires an explicit approved override with a reason, captured in immutable decision provenance. For `APPT-2026-023787`, an attempted 2026-10-22 reschedule returned HTTP 409 with the permitted 2026-11-23 window, retained the 2026-11-23 schedule, and retained one active plus three superseded dock reservation records. Gate Operations now initializes Candidate start from the selected appointment request, displays requested/current/window values, exposes audited override inputs, and disables ineligible schedule/reschedule buttons.

## Completed lifecycle verification: APPT-2026-023787

Database evidence shows final status `DEPARTED`. Dashboard-sourced immutable events were ARRIVED, CHECKED_IN, IN_SERVICE, COMPLETED, and DEPARTED, all at `2026-11-23T06:00:00Z` and in nondecreasing sequence order (6 through 10). Thus timestamp-derived waiting, service, and turnaround are all 0 minutes, matching `derived_metrics` (0/0/0); the scheduled service remains 65 minutes. This is database evidence of dashboard-originated actions (`source=DASHBOARD`), not retained screenshot evidence of visual interaction.

The appointment has one active dock, yard, and labor allocation and three superseded histories for each; active dock and yard conflict checks returned zero. Historical SCHEDULED/RESCHEDULED decisions before the scheduling-window fix have `{"decision":"first_feasible"}` provenance without an override marker, so their earlier off-window decisions are auditable but not policy-compliant under the new rule.

An isolated benchmark fixture issue was discovered: `SHP-2026-000001` is linked to 3,788 appointments in `logistics_test`, caused by benchmark fixture reuse. This makes isolated shipment-assignment integrity unsuitable for final acceptance until the test database is rebuilt with unique shipment fixtures. Production was not affected.

## Final data-integrity hardening (2026-11-16)

### Zero-duration lifecycle safeguard

The zero-duration lifecycle on `APPT-2026-023787` was historical isolated-test evidence and was not rewritten. The API now rejects `IN_SERVICE -> COMPLETED` unless the completion timestamp is strictly later than the recorded service-start timestamp (`HTTP 409`, `service completion must be after service start`). Equal timestamps remain permitted only for operationally valid transitions such as arrival and check-in. Isolated Streamlit simulation defaults are based on the immutable latest event: service start is one minute later, completion is the planned service duration later, and departure is one minute later. Production keeps future simulated timestamps disabled.

Regression coverage now includes rejected zero-duration completion and a positive-duration flow that reconciles to waiting=20, actual service=60, and turnaround=90 minutes. The clean isolated suite passed **23 tests in 19.94 seconds**; one existing `StarletteDeprecationWarning` about the future `httpx2` replacement remains visible and unsuppressed.

### Shipment cardinality and benchmark fixtures

The prior `SHP-2026-000001` reuse evidence was retained above, then `logistics_test` was recreated from the verified `logistics` baseline. The API now rejects assigning a shipment already attached to a non-terminal appointment (`HTTP 409`). Completed, departed, no-show, and cancelled historical assignments do not block a new appointment.

`scripts/benchmark_scheduling.py` now provisions distinct `SHP-BENCH-...` and matching handling-requirement fixtures directly in the isolated database before timing begins; each measured appointment gets a unique shipment. Fixture preparation remains outside measured HTTP POST latency. The benchmark script was not rerun in this hardening pass, so no new performance claim is made.

### Final isolated checks

| Check | Result |
|---|---:|
| Duplicate non-terminal shipment assignments | 0 |
| Orphan appointment-shipment links | 0 |
| Active dock overlaps | 0 |
| Active yard overlaps | 0 |
| Non-positive service-completion event pairs | 0 |
| Test database rows after regressions (appointments / events / dock reservations) | 20,016 / 100,048 / 12,547 |
| Full baseline seed SQL SHA-256 | `D7EE393AA3818821FB467AD9D2DF1C322207D9D4912A75A538618C05FD049F7D` |

The clean clone began from the production baseline; test-created records account for the post-test row increases. After all tests, `logistics_test` was recreated once more from the baseline, so it is now clean at **20,000 appointments, 100,000 operational events, 12,537 dock reservations, 0 exceptions**, and 0 non-terminal duplicate-shipment assignments. No benchmark/test fixture remains for future manual acceptance. Production was read-only checked afterward and remains **20,000 appointments, 100,000 operational events, 12,537 dock reservations, and 0 exceptions**. Production `database/verify.sql` returned all 25 checks as PASS.

### Remaining blocker

An interval-aware labor check found pre-existing capacity overages in baseline data: 98 overlapping-worker peaks in the freshly reset `logistics_test` clone and 713 in production. This is not caused by the new benchmark fixtures and was not changed because production data must remain intact. It needs a separately scoped generator/baseline investigation before a full capacity-integrity acceptance can be claimed. Overall end-to-end acceptance remains **FAIL/CONDITIONAL**, also pending real-browser workflow evidence and completed POST benchmarks.
