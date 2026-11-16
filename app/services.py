from __future__ import annotations
from datetime import datetime, timedelta, timezone
import json
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import HTTPException
from .config import settings

def now(): return datetime.now(timezone.utc)
def rows(db, sql, **p): return db.execute(text(sql),p).mappings().all()
def row(db, sql, **p): return db.execute(text(sql),p).mappings().first()
def event(db, aid, typ, ts, source='API', actor='system', provenance='{}'):
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext('event-id'))"))
    seq=db.execute(text("SELECT coalesce(max(sequence_no),0)+1 FROM operational_events WHERE appointment_id=:a"),{'a':aid}).scalar_one()
    eid=db.execute(text("SELECT 'EVT-' || extract(year from :t)::int || '-' || lpad((coalesce(max(substring(event_id from '[0-9]+$')::int),0)+1)::text,7,'0') FROM operational_events"),{'t':ts}).scalar_one()
    db.execute(text("INSERT INTO operational_events(event_id,appointment_id,event_type,event_ts,sequence_no,source) VALUES(:id,:a,:e,:t,:s,:src)"),{'id':eid,'a':aid,'e':typ,'t':ts,'s':seq,'src':source})
    db.execute(text("INSERT INTO appointment_state_events(appointment_id,event_type,event_ts,actor,source,rule_version,decision_provenance) VALUES(:a,:e,:t,:actor,:src,:r,CAST(:p AS jsonb))"),{'a':aid,'e':typ,'t':ts,'actor':actor,'src':source,'r':settings.rule_version,'p':provenance})
def exception(db, aid, typ, cause, severity='HIGH'):
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext('exception-id'))"))
    eid=db.execute(text("SELECT 'EXC-' || lpad((coalesce(max(substring(exception_id from '[0-9]+$')::int),0)+1)::text,6,'0') FROM exceptions" )).scalar_one()
    db.execute(text("INSERT INTO exceptions(exception_id,appointment_id,issue_type,cause_code,severity,source,status) VALUES(:i,:a,:t,:c,:s,'API','OPEN')"),{'i':eid,'a':aid,'t':typ,'c':cause,'s':severity})
def create_appointment(db, d):
    with db.begin():
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext('appointment-id'))"))
        if not row(db,"SELECT 1 FROM facilities WHERE facility_id=:v AND active",v=d.facility_id): raise HTTPException(404,'facility not found')
        if not row(db,"SELECT 1 FROM vehicles WHERE vehicle_id=:v AND active",v=d.vehicle_id): raise HTTPException(404,'vehicle not found')
        if not row(db,"SELECT 1 FROM shipments WHERE shipment_id=:v",v=d.shipment_id): raise HTTPException(404,'shipment not found')
        if row(db,"SELECT 1 FROM appointment_shipments j JOIN appointments a ON a.appointment_id=j.appointment_id WHERE j.shipment_id=:s AND a.status NOT IN ('COMPLETED','DEPARTED','NO_SHOW','CANCELLED')",s=d.shipment_id): raise HTTPException(409,'shipment is already assigned to a non-terminal appointment')
        n=db.execute(text("SELECT coalesce(max(substring(appointment_id from '[0-9]+$')::int),0)+1 FROM appointments")).scalar_one(); aid=f'APPT-{d.requested_start_ts.year}-{n:06d}'
        service=db.execute(text("SELECT service_minutes FROM handling_requirements WHERE shipment_id=:s"),{'s':d.shipment_id}).scalar_one_or_none()
        if service is None: raise HTTPException(409,'shipment has no handling requirement')
        db.execute(text("INSERT INTO appointments(appointment_id,facility_id,vehicle_id,appointment_type,requested_start_ts,status,allocation_reason,service_minutes,created_ts) VALUES(:a,:f,:v,:type,:t,'REQUESTED','PENDING',:m,:now)"),{'a':aid,'f':d.facility_id,'v':d.vehicle_id,'type':d.appointment_type,'t':d.requested_start_ts,'m':service,'now':now()})
        db.execute(text("INSERT INTO appointment_shipments(appointment_id,shipment_id,sequence_no) VALUES(:a,:s,1)"),{'a':aid,'s':d.shipment_id})
        db.execute(text("INSERT INTO derived_metrics(appointment_id,scheduled_service_minutes,actual_service_minutes,waiting_minutes,turnaround_minutes,appointment_status) VALUES(:a,:m,0,0,0,'REQUESTED')"),{'a':aid,'m':service})
        event(db,aid,'REQUESTED',d.requested_start_ts,provenance='{"decision":"created"}')
    return get_appointment(db,aid)
def get_appointment(db, aid):
    x=row(db,"SELECT * FROM appointments WHERE appointment_id=:a",a=aid)
    if not x: raise HTTPException(404,'appointment not found')
    return dict(x)
def schedule(db, aid, start, intervals=1, step=15, reschedule=False, approved_override=False, override_reason=None):
    with db.begin():
        ap=row(db,"SELECT a.*,s.load_type,v.length_m,v.capability FROM appointments a JOIN appointment_shipments j ON j.appointment_id=a.appointment_id JOIN shipments s ON s.shipment_id=j.shipment_id JOIN vehicles v ON v.vehicle_id=a.vehicle_id WHERE a.appointment_id=:a FOR UPDATE",a=aid)
        if not ap: raise HTTPException(404,'appointment not found')
        allowed=('SCHEDULED','RESCHEDULED') if reschedule else ('REQUESTED','WAITLISTED','RESCHEDULED')
        if ap['status'] not in allowed: raise HTTPException(409,f'cannot schedule from {ap["status"]}')
        if approved_override and not override_reason: raise HTTPException(422,'approved override requires override_reason')
        def waitlist(reason, event_ts):
            db.execute(text("UPDATE appointments SET status='WAITLISTED',allocation_reason=:reason WHERE appointment_id=:a"),{'a':aid,'reason':reason})
            db.execute(text("UPDATE derived_metrics SET appointment_status='WAITLISTED' WHERE appointment_id=:a"),{'a':aid})
            event(db,aid,'WAITLISTED',event_ts,provenance='{"decision":"no_feasible_slot"}')
            return get_appointment(db,aid)
        base=start or ap['requested_start_ts']; duration=timedelta(minutes=ap['service_minutes'])
        deviation=timedelta(minutes=settings.scheduling_deviation_minutes); window_start=ap['requested_start_ts']-deviation; window_end=ap['requested_start_ts']+deviation
        if not approved_override and not (window_start <= base <= window_end): raise HTTPException(409,f'candidate start outside permitted window {window_start.isoformat()} to {window_end.isoformat()}')
        if reschedule:
            for table in ('dock_reservations','yard_reservations','labor_allocations'):
                db.execute(text(f"UPDATE {table} SET status='SUPERSEDED' WHERE appointment_id=:a AND status IN ('RESERVED','ALLOCATED')"),{'a':aid})
        if ap['load_type'] != 'STANDARD' and ap['capability'] != ap['load_type']:
            return waitlist('VEHICLE_INCOMPATIBLE',base)
        db.execute(text("SELECT 1 FROM docks WHERE facility_id=:f ORDER BY dock_id FOR UPDATE"),{'f':ap['facility_id']})
        reason='NO_FEASIBLE_SLOT'
        for i in range(intervals):
            st=base+timedelta(minutes=i*step); en=st+duration
            if not approved_override and st > window_end: break
            shifts=rows(db,"SELECT * FROM labor_shifts WHERE facility_id=:f AND start_ts<=:s AND end_ts>=:e AND status='SCHEDULED' ORDER BY labor_shift_id FOR UPDATE",f=ap['facility_id'],s=st,e=en)
            compatible=rows(db,"SELECT d.dock_id FROM docks d WHERE d.facility_id=:f AND d.active AND d.dock_type=:load AND d.length_m>=:length",f=ap['facility_id'],load=ap['load_type'],length=ap['length_m'])
            if not compatible:
                reason='NO_COMPATIBLE_DOCK'; continue
            candidates=rows(db,"SELECT d.* FROM docks d WHERE d.facility_id=:f AND d.active AND d.dock_type=:load AND d.length_m>=:length AND NOT EXISTS (SELECT 1 FROM dock_reservations r WHERE r.dock_id=d.dock_id AND r.status='RESERVED' AND r.start_ts<:e AND r.end_ts>:s)",f=ap['facility_id'],load=ap['load_type'],length=ap['length_m'],s=st,e=en)
            if not candidates:
                reason='DOCK_OCCUPIED'; continue
            yard=rows(db,"SELECT y.* FROM yard_slots y WHERE y.facility_id=:f AND y.active AND (:load<>'REFRIGERATED' OR y.slot_type='REEFER') AND NOT EXISTS (SELECT 1 FROM yard_reservations r WHERE r.yard_slot_id=y.yard_slot_id AND r.status='RESERVED' AND r.start_ts<:e AND r.end_ts>:ys) LIMIT 1",f=ap['facility_id'],load=ap['load_type'],e=en,ys=st-timedelta(minutes=30))
            if not yard:
                reason='NO_YARD_CAPACITY'; continue
            shift=next((q for q in shifts if ap['load_type'] in q['skills'].split(',')),None)
            if not shift:
                reason='FACILITY_CLOSED' if not shifts else 'INSUFFICIENT_QUALIFIED_LABOR'; continue
            used=db.execute(text("SELECT coalesce(sum(l.workers_required),0) FROM labor_allocations l JOIN appointments x ON x.appointment_id=l.appointment_id WHERE l.labor_shift_id=:sh AND l.status='ALLOCATED' AND x.scheduled_start_ts<:e AND x.scheduled_end_ts>:s"),{'sh':shift['labor_shift_id'],'s':st,'e':en}).scalar_one()
            if used >= shift['workers']:
                reason='INSUFFICIENT_QUALIFIED_LABOR'; continue
            suffix=aid[-6:]; version=db.execute(text("SELECT count(*)+1 FROM dock_reservations WHERE appointment_id=:a"),{'a':aid}).scalar_one()
            db.execute(text("INSERT INTO dock_reservations(dock_reservation_id,appointment_id,dock_id,start_ts,end_ts,status) VALUES(:id,:a,:d,:s,:e,'RESERVED')"),{'id':f'RES-DOCK-{st.year}-{suffix}-{version}','a':aid,'d':candidates[0]['dock_id'],'s':st,'e':en})
            db.execute(text("INSERT INTO yard_reservations(yard_reservation_id,appointment_id,yard_slot_id,start_ts,end_ts,status) VALUES(:id,:a,:y,:s,:e,'RESERVED')"),{'id':f'RES-YARD-{st.year}-{suffix}-{version}','a':aid,'y':yard[0]['yard_slot_id'],'s':st-timedelta(minutes=30),'e':en})
            db.execute(text("INSERT INTO labor_allocations(labor_allocation_id,appointment_id,labor_shift_id,workers_required,skill,status) VALUES(:id,:a,:sh,1,:skill,'ALLOCATED')"),{'id':f'LABALLOC-{st.year}-{suffix}-{version}','a':aid,'sh':shift['labor_shift_id'],'skill':ap['load_type']})
            state='RESCHEDULED' if reschedule else 'SCHEDULED'
            db.execute(text("UPDATE appointments SET scheduled_start_ts=:s,scheduled_end_ts=:e,status=:state,allocation_reason='ALLOCATED' WHERE appointment_id=:a"),{'s':st,'e':en,'state':state,'a':aid})
            db.execute(text("UPDATE derived_metrics SET scheduled_service_minutes=:m,appointment_status=:state WHERE appointment_id=:a"),{'a':aid,'m':ap['service_minutes'],'state':state})
            event(db,aid,state,st,provenance=json.dumps({'decision':'first_feasible','approved_override':approved_override,'override_reason':override_reason}))
            return get_appointment(db,aid)
        return waitlist(reason,base)
LIFECYCLE={'SCHEDULED':'ARRIVED','RESCHEDULED':'ARRIVED','ARRIVED':'CHECKED_IN','CHECKED_IN':'IN_SERVICE','IN_SERVICE':'COMPLETED','COMPLETED':'DEPARTED'}
def transition(db, aid, target, ts=None, source='API', actor='system'):
    ts=ts or now()
    if not settings.simulation_mode and ts > now():
        raise HTTPException(409,'future event timestamps require isolated simulation mode')
    with db.begin():
        ap=row(db,"SELECT * FROM appointments WHERE appointment_id=:a FOR UPDATE",a=aid)
        if not ap: raise HTTPException(404,'appointment not found')
        if LIFECYCLE.get(ap['status'])!=target: raise HTTPException(409,f'illegal transition {ap["status"]} -> {target}')
        previous=row(db,"SELECT event_ts FROM operational_events WHERE appointment_id=:a AND event_type IN ('ARRIVED','CHECKED_IN','IN_SERVICE','COMPLETED','DEPARTED') ORDER BY sequence_no DESC LIMIT 1",a=aid)
        if previous and ts < previous['event_ts']:
            raise HTTPException(409,'event timestamp precedes the recorded lifecycle history')
        if target=='CHECKED_IN' and ts < ap['scheduled_start_ts']-timedelta(minutes=30): exception(db,aid,'CHECKIN_DATE_VIOLATION','TOO_EARLY')
        if target=='COMPLETED':
            started=row(db,"SELECT event_ts FROM operational_events WHERE appointment_id=:a AND event_type='IN_SERVICE' ORDER BY sequence_no DESC LIMIT 1",a=aid)
            if not started or ts <= started['event_ts']: raise HTTPException(409,'service completion must be after service start')
        db.execute(text("UPDATE appointments SET status=:s WHERE appointment_id=:a"),{'s':target,'a':aid}); db.execute(text("UPDATE derived_metrics SET appointment_status=:s WHERE appointment_id=:a"),{'s':target,'a':aid})
        if target=='CHECKED_IN':
            db.execute(text("INSERT INTO checkin_events(checkin_event_id,appointment_id,event_type,event_ts,arrival_class) VALUES(:id,:a,'CHECKED_IN',:t,'ON_TIME')"),{'id':f'CHECK-{aid}-01','a':aid,'t':ts})
        event(db,aid,target,ts,source,actor,'{"decision":"lifecycle"}')
        if target=='IN_SERVICE':
            arrived=row(db,"SELECT event_ts FROM operational_events WHERE appointment_id=:a AND event_type='ARRIVED' ORDER BY sequence_no LIMIT 1",a=aid)
            if arrived: db.execute(text("UPDATE derived_metrics SET waiting_minutes=:m WHERE appointment_id=:a"),{'a':aid,'m':round((ts-arrived['event_ts']).total_seconds()/60)})
        elif target=='COMPLETED':
            started=row(db,"SELECT event_ts FROM operational_events WHERE appointment_id=:a AND event_type='IN_SERVICE' ORDER BY sequence_no DESC LIMIT 1",a=aid)
            if started: db.execute(text("UPDATE derived_metrics SET actual_service_minutes=:m WHERE appointment_id=:a"),{'a':aid,'m':round((ts-started['event_ts']).total_seconds()/60)})
        elif target=='DEPARTED':
            arrived=row(db,"SELECT event_ts FROM operational_events WHERE appointment_id=:a AND event_type='ARRIVED' ORDER BY sequence_no LIMIT 1",a=aid)
            if arrived: db.execute(text("UPDATE derived_metrics SET turnaround_minutes=:m WHERE appointment_id=:a"),{'a':aid,'m':round((ts-arrived['event_ts']).total_seconds()/60)})
    return get_appointment(db,aid)

def detect_missing_no_show_events(db):
    with db.begin():
        missing=rows(db,"SELECT a.appointment_id FROM appointments a WHERE a.status='NO_SHOW' AND NOT EXISTS (SELECT 1 FROM checkin_events c WHERE c.appointment_id=a.appointment_id AND c.event_type='NO_SHOW') AND NOT EXISTS (SELECT 1 FROM exceptions e WHERE e.appointment_id=a.appointment_id AND e.issue_type='MISSING_NO_SHOW_EVENT') FOR UPDATE")
        for item in missing: exception(db,item['appointment_id'],'MISSING_NO_SHOW_EVENT','NO_SHOW_EVENT_MISSING')
    return {'detected':len(missing)}
