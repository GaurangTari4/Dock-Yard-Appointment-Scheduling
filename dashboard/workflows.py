NEXT_ACTION={'SCHEDULED':'arrive','RESCHEDULED':'arrive','ARRIVED':'check-in','CHECKED_IN':'service-start','IN_SERVICE':'service-complete','COMPLETED':'depart'}
def next_action(status): return NEXT_ACTION.get(status)
def valid_create(payload): return all(payload.get(k) for k in ('facility_id','vehicle_id','shipment_id','appointment_type','requested_start_ts'))
