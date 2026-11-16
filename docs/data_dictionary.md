# Data dictionary

All IDs are immutable strings and primary keys unless marked FK. Dates are ISO-8601 UTC timestamps; `*_minutes` are integer minutes and `length_m`, `weight_kg` use metres and kilograms. Required means non-null in generated rows.

| Entity | Fields (type; required) | Values / validation |
|---|---|---|
| Facility | facility_id text; name text; timezone text; effective_from timestamptz; active bool | `FAC-###`; unique; IANA timezone |
| Dock | dock_id text; facility_id FK; dock_type enum; length_m decimal; capacity_units int; active bool | `DOCK-FAC-###-###`; STANDARD/REFRIGERATED/HAZMAT; capacity >0 |
| YardSlot | yard_slot_id text; facility_id FK; slot_type enum; capacity_units int; active bool | unique; capacity >0 |
| Carrier | carrier_id text; name text; scac text; active bool | `CAR-####`; SCAC unique |
| Vehicle | vehicle_id text; carrier_id FK; vehicle_type text; length_m decimal; capability enum; active bool | `VEH-#####`; length >0 |
| Appointment | appointment_id text; facility_id FK; vehicle_id FK; appointment_type enum; requested/scheduled start/end timestamptz; status enum; allocation_reason enum; service_minutes int; created_ts | `APPT-YYYY-######`; scheduled fields optional for waitlist; reasons are ALLOCATED, NO_COMPATIBLE_DOCK, DOCK_OCCUPIED, NO_YARD_CAPACITY, or INSUFFICIENT_QUALIFIED_LABOR; end > start |
| Shipment | shipment_id text; carrier_id FK; direction enum; load_type enum; weight_kg decimal; pallet_count int; status text | `SHP-YYYY-######`; INBOUND/OUTBOUND and supported load types |
| LaborShift | labor_shift_id text; facility_id FK; shift_code; start/end; workers int; skills csv; status | workers >0; end > start |
| HandlingRequirement | handling_requirement_id text; shipment_id FK; requirement_type; requires_reefer bool; requires_hazmat_cert bool; service_minutes int | shipment unique (1:1); derived from load |
| CheckInEvent | checkin_event_id text; appointment_id FK; event_type; event_ts; arrival_class | `CHECK-APPT-YYYY-######-##`; CHECKED_IN/NO_SHOW; EARLY/ON_TIME/LATE |
| Exception | exception_id text; appointment_id nullable FK; issue_type; cause_code; severity; source; status | separate operational record; status defaults to OPEN; no ground-truth fields |
| CapacityCalendar | calendar_id; facility_id FK; labor_shift_id FK; date; dock/yard/labor capacity; effective_from | unique facility/date/shift |
| AppointmentShipment | appointment_id FK; shipment_id FK; sequence_no int | composite unique; N:M bridge |
| DockReservation | dock_reservation_id; appointment_id FK; dock_id FK; start/end; status | 0:1 per generated appointment; non-overlap baseline |
| YardReservation | yard_reservation_id; appointment_id FK; yard_slot_id FK; start/end; status | 0:1 per generated appointment |
| LaborAllocation | labor_allocation_id; appointment_id FK; labor_shift_id FK; workers_required; skill; status | skill and coverage required |
| OperationalEvent | event_id; appointment_id FK; event_type; event_ts; sequence_no; source | immutable; unique appointment/sequence |
| DerivedMetric | appointment_id FK; scheduled/actual/waiting/turnaround minutes; appointment_status | source-derived only, never randomized |
| ResourceUtilizationMetric | facility_id FK; period start/end; dock/yard/labor utilization decimals; no-show/exception counts | aggregate source-derived facility metric |

`ground_truth.csv/json` is an evaluation-only file with `scenario_id`, `issue_type`, `cause_code`, affected entity/record and expected outcome. It is deliberately absent from regular feature tables.
