# Scheduling feasibility investigation — 2026-11-16

## Conclusion

The original 91.46% Full waitlist rate was caused by generator defects, not by genuine aggregate capacity scarcity. After focused corrections, Full schedules 12,537 of 20,000 requests (62.69%) with 7,463 waitlisted (37.32%). Remaining waitlists are deterministic peak-window contention, chiefly on docks, and are retained as useful congestion stress cases.

## Root-cause investigation

| Stage | Scheduled / reservations | Waitlisted | Waitlist rate | Avg dock utilization |
|---|---:|---:|---:|---:|
| Original export | 1,709 | 18,291 | 91.46% | 3.2916% |
| Labor corrected only | 4,440 | 15,560 | 77.80% | 8.1538% |
| Facility dock capability corrected | 5,568 | 14,432 | 72.16% | 10.7383% |
| Final balanced baseline | 12,537 | 7,463 | 37.32% | 23.1906% |

Verified defects and changes:

1. **Facility capability defect.** The global dock number determined dock type while facilities were assigned modulo 10. Consequently, a Full facility received only one type. The instrumented intermediate run found 9,050 `NO_COMPATIBLE_DOCK` decisions (6,951 standard, 1,230 refrigerated, 869 hazardous). Dock type now cycles by per-facility ordinal, yielding 6 standard, 2 refrigerated and 2 hazardous docks at every Full facility.
2. **Labor modeling defect.** A 10-dock Full facility was staffed with only 3 concurrent workers. The active baseline configuration now supplies one worker per dock (10 workers per shift); this is explicit in `config/profiles.json`.
3. **Timestamp modulo aliasing.** Arithmetic ID-based dates/hours/minutes repeatedly mapped a facility/date to one hour and five minute positions. Seeded deterministic sampling now drives weekday-weighted day, peak-weighted hour and minute selections. The same seed reproduces exactly.
4. **Special dock dimension defect.** Refrigerated/hazardous docks could be shorter than compatible specialized vehicles. Those docks now have 18 m length, retaining varied standard-dock dimensions.

No changes weaken validation, change IDs/seed/profile record targets, or combine ground truth with ordinary features.

## Final Full feasibility evidence

### Primary waitlist causes

| Primary decision cause | Requests | Share of all requests | Share of waitlisted |
|---|---:|---:|---:|
| Dock occupied at fixed requested window | 7,112 | 35.56% | 95.30% |
| Insufficient qualified labor at fixed requested window | 351 | 1.76% | 4.70% |
| No compatible dock | 0 | 0% | 0% |
| No yard capacity | 0 | 0% | 0% |
| Vehicle incompatibility | 0 | 0% | 0% |
| Facility closed | 0 | 0% | 0% |
| Other | 0 | 0% | 0% |

`REQUESTED_TIME_WINDOW_RESTRICTION` is a cross-cutting rule, not an additional exclusive cause: every request is a fixed-start request with no automatic rescheduling. It explains why otherwise adequate aggregate capacity cannot absorb dock/labor collisions. There are no unavailable facility hours: requests fall between 07:00 and 17:00 and shifts cover 06:00–22:00.

### Demand and capacity

- Facilities: exactly 2,000 requests each.
- Date demand: 128–460 requests/day; weekday demand receives the configured 3× weighting over weekends.
- Hour demand: 07:00 1,408; 08:00 2,854; 09:00 2,804; 10:00 2,902; 14:00 2,869; 15:00 2,867; 16:00 2,853; 17:00 1,443. Peak facility-hour demand is 16 requests.
- Direction: waitlisted 3,818 inbound and 3,645 outbound.
- Load: 17,376 standard / 1,538 refrigerated / 1,086 hazardous. Waitlisted: 7,000 / 269 / 194 respectively.
- Resources: 100 docks (60 standard, 20 refrigerated, 20 hazardous), 200 yard slots (160 general, 40 reefer), and 10 qualified workers per shift at every baseline facility.
- Requested service: 2,138,648 minutes; scheduled service: 1,335,779 minutes. Dock and labor capacity are each 5,760,000 minutes for the 60-day Full horizon.

Thus, aggregate capacity is larger than requested work; the residual congestion is from fixed, uneven peak timestamps plus compatibility-specific dock pools, not resource leaks or a faulty interval rule.

## Validation and event checks

- All three regenerated baselines: **0 constraint violations**.
- All injected datasets: **5 expected violations only**, one per mandatory anomaly type.
- Full event count remains 100,000: unique event IDs, unique appointment/sequence pairs, and five events per appointment.
- No duplicate/filler events, reservation overlap, unreleased reservation, invalid vehicle/dock compatibility, invalid yard compatibility, or bridge inconsistency was found in baseline validation.
- Derived waiting time changed from 9.560 minutes average before correction to **8.964 minutes** after; P95 remains **15 minutes**, a consequence of the fixed early/on-time/late arrival model.

## Testing, exports and reproducibility

- `python -m pytest -q`: **9 passed in 14.80s**. Added tests assert all facility dock capabilities, broad Full timestamp spread, and allocation-reason/state consistency, alongside existing resource, lifecycle, anomaly, metric and export tests.
- CSV/JSON/SQL parity remains covered by tests. SQL serializer emits `NULL` for nullable values.
- Regenerating Tiny, Starter and Full twice with seed `20261022` produced matching SHA-256 content for all **84 files** per profile, including baseline, injected, ground-truth, seed SQL and manifests.
- No PostgreSQL client/server is available in this workspace; live SQL seed loading remains unverified. Static schema/seed checks pass.

## Remaining limitations

The baseline intentionally has no auto-rescheduler: a waitlisted appointment is not offered nearby capacity. Therefore it is a useful fixed-window scheduling stress dataset, not evidence that a future scheduling API should reject every collision. The maximum arrival-based wait is still 15 minutes. A future scheduler phase should test alternative-window search, queue promotion and actual observed resource occupancy against a live PostgreSQL seed load.
