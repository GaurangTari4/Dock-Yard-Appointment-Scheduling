# Identifier formats and anomaly protocol

Formats are immutable and zero-padded: `FAC-001`, `DOCK-FAC-001-001`, `YARD-FAC-001-001-01`, `CAR-0001`, `VEH-00001`, `APPT-2026-000001`, `SHP-2026-000001`, `HR-2026-000001`, `SHIFT-FAC-001-001-DAY`, `CAL-FAC-001-2026-10-22-DAY`, `RES-DOCK-2026-000001`, `RES-YARD-2026-000001`, `LABALLOC-2026-000001`, `CHECK-APPT-2026-000001-01`, `EVT-2026-0000001`, `EXC-001`, and `SCN-001`.

Injection occurs only after a deep-copied, valid baseline. Each scenario has exactly one ground-truth row with an issue type, cause, target and expected detector result. The injected target has five event sequences per appointment throughout; the missing no-show scenario substitutes a distinct audit event rather than a duplicate or filler event. The validator uses relationships and timestamps, not exception records or ground truth, to discover violations.
