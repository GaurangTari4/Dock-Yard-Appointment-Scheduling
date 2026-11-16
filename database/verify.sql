-- Full-baseline database verification. Emits one PASS/FAIL row per check.
WITH checks(check_name, passed, detail) AS (
  VALUES
    ('row_count.facilities', (SELECT count(*)=10 FROM facilities), (SELECT count(*)::text FROM facilities)),
    ('row_count.docks', (SELECT count(*)=100 FROM docks), (SELECT count(*)::text FROM docks)),
    ('row_count.yard_slots', (SELECT count(*)=200 FROM yard_slots), (SELECT count(*)::text FROM yard_slots)),
    ('row_count.carriers', (SELECT count(*)=40 FROM carriers), (SELECT count(*)::text FROM carriers)),
    ('row_count.vehicles', (SELECT count(*)=300 FROM vehicles), (SELECT count(*)::text FROM vehicles)),
    ('row_count.labor_shifts', (SELECT count(*)=1200 FROM labor_shifts), (SELECT count(*)::text FROM labor_shifts)),
    ('row_count.capacity_calendars', (SELECT count(*)=1200 FROM capacity_calendars), (SELECT count(*)::text FROM capacity_calendars)),
    ('row_count.shipments', (SELECT count(*)=20000 FROM shipments), (SELECT count(*)::text FROM shipments)),
    ('row_count.handling_requirements', (SELECT count(*)=20000 FROM handling_requirements), (SELECT count(*)::text FROM handling_requirements)),
    ('row_count.appointments', (SELECT count(*)=20000 FROM appointments), (SELECT count(*)::text FROM appointments)),
    ('row_count.appointment_shipments', (SELECT count(*)=20000 FROM appointment_shipments), (SELECT count(*)::text FROM appointment_shipments)),
    ('row_count.dock_reservations', (SELECT count(*)=12537 FROM dock_reservations), (SELECT count(*)::text FROM dock_reservations)),
    ('row_count.yard_reservations', (SELECT count(*)=12537 FROM yard_reservations), (SELECT count(*)::text FROM yard_reservations)),
    ('row_count.labor_allocations', (SELECT count(*)=12537 FROM labor_allocations), (SELECT count(*)::text FROM labor_allocations)),
    ('row_count.checkin_events', (SELECT count(*)=12537 FROM checkin_events), (SELECT count(*)::text FROM checkin_events)),
    ('row_count.operational_events', (SELECT count(*)=100000 FROM operational_events), (SELECT count(*)::text FROM operational_events)),
    ('row_count.exceptions', (SELECT count(*)=0 FROM exceptions), (SELECT count(*)::text FROM exceptions)),
    ('row_count.derived_metrics', (SELECT count(*)=20000 FROM derived_metrics), (SELECT count(*)::text FROM derived_metrics)),
    ('row_count.resource_utilization_metrics', (SELECT count(*)=10 FROM resource_utilization_metrics), (SELECT count(*)::text FROM resource_utilization_metrics)),
    ('nullable_waitlist_schedule', (SELECT count(*)=0 FROM appointments WHERE status='WAITLISTED' AND (scheduled_start_ts IS NOT NULL OR scheduled_end_ts IS NOT NULL)), (SELECT count(*)::text FROM appointments WHERE status='WAITLISTED' AND (scheduled_start_ts IS NOT NULL OR scheduled_end_ts IS NOT NULL))),
    ('reservation_relationships', (SELECT count(*)=0 FROM appointments a WHERE (a.status='WAITLISTED' AND EXISTS (SELECT 1 FROM dock_reservations r WHERE r.appointment_id=a.appointment_id)) OR (a.status<>'WAITLISTED' AND NOT EXISTS (SELECT 1 FROM dock_reservations r WHERE r.appointment_id=a.appointment_id))), (SELECT count(*)::text FROM appointments a WHERE (a.status='WAITLISTED' AND EXISTS (SELECT 1 FROM dock_reservations r WHERE r.appointment_id=a.appointment_id)) OR (a.status<>'WAITLISTED' AND NOT EXISTS (SELECT 1 FROM dock_reservations r WHERE r.appointment_id=a.appointment_id)))),
    ('dock_overlap', (SELECT count(*)=0 FROM dock_reservations a JOIN dock_reservations b ON a.dock_id=b.dock_id AND a.dock_reservation_id<b.dock_reservation_id AND a.start_ts<b.end_ts AND b.start_ts<a.end_ts), (SELECT count(*)::text FROM dock_reservations a JOIN dock_reservations b ON a.dock_id=b.dock_id AND a.dock_reservation_id<b.dock_reservation_id AND a.start_ts<b.end_ts AND b.start_ts<a.end_ts)),
    ('event_history', (SELECT count(*)=0 FROM (SELECT appointment_id FROM operational_events GROUP BY appointment_id HAVING count(*)<>5) q), (SELECT count(*)::text FROM (SELECT appointment_id FROM operational_events GROUP BY appointment_id HAVING count(*)<>5) q)),
    ('event_order', (SELECT count(*)=0 FROM (SELECT appointment_id, bool_and(event_ts >= lag_event_ts) AS ordered FROM (SELECT appointment_id,event_ts,lag(event_ts) OVER (PARTITION BY appointment_id ORDER BY sequence_no) lag_event_ts FROM operational_events) s GROUP BY appointment_id) q WHERE ordered IS FALSE), (SELECT count(*)::text FROM (SELECT appointment_id, bool_and(event_ts >= lag_event_ts) AS ordered FROM (SELECT appointment_id,event_ts,lag(event_ts) OVER (PARTITION BY appointment_id ORDER BY sequence_no) lag_event_ts FROM operational_events) s GROUP BY appointment_id) q WHERE ordered IS FALSE)),
    ('foreign_key_constraints_valid', (SELECT count(*)=0 FROM pg_constraint WHERE contype='f' AND NOT convalidated), (SELECT count(*)::text FROM pg_constraint WHERE contype='f' AND NOT convalidated))
)
SELECT check_name, CASE WHEN passed THEN 'PASS' ELSE 'FAIL' END AS result, detail FROM checks ORDER BY check_name;
