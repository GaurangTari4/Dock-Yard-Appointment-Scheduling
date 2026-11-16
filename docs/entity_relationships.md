# Entity relationships and lifecycle

There are 19 exported operational entities (11 core plus eight supporting tables). Facility 1:N Dock, YardSlot, LaborShift and CapacityCalendar; Carrier 1:N Vehicle and Shipment; Shipment 1:1 HandlingRequirement; Appointment N:M Shipment through AppointmentShipment (the generated data uses one shipment per appointment); Appointment 0:1 DockReservation, YardReservation and LaborAllocation; Appointment 1:N CheckInEvent, OperationalEvent and Exception; LaborShift 1:N LaborAllocation; and Dock/YardSlot 1:N reservations over time. `scheduled_*`, reservation, allocation and exception appointment references are nullable only where an appointment is waitlisted or an exception is system-level.

Effective dates: `facilities.effective_from` and `capacity_calendars.effective_from` establish validity; the generator emits active records at simulation start. Reservations are half-open intervals `[start_ts,end_ts)`.

Appointment lifecycle: `REQUESTED -> CONFIRMED|WAITLISTED|REJECTED`; confirmed progresses `CHECKED_IN -> IN_SERVICE -> COMPLETED`, or `NO_SHOW`/`CANCELLED`. WAITLISTED may transition to CONFIRMED, REJECTED or CANCELLED. Operational events are immutable; corrections are new events, never updates. Generated terminal appointment statuses are COMPLETED, NO_SHOW, or WAITLISTED.

Hard allocation constraints: matching facility, matching load capability, vehicle/dock length capacity, no dock or yard overlap, shift coverage, skill presence and worker capacity. The baseline meets them; waitlisted requests receive no resource reservation.
