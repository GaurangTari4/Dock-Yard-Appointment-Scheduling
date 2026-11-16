from datetime import datetime
from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session
from .database import get_db
from .schemas import AppointmentCreate, ArrivalRequest, ScheduleRequest
from . import services
from .config import settings

app=FastAPI(title='Dock & Yard Scheduling API',version='0.1.0')
@app.get('/health')
def health(db:Session=Depends(get_db)): db.execute(text('SELECT 1')); return {'status':'ok'}
@app.get('/facilities')
def facilities(db:Session=Depends(get_db)): return services.rows(db,'SELECT * FROM facilities ORDER BY facility_id')
@app.get('/facilities/{facility_id}')
def facility(facility_id:str,db:Session=Depends(get_db)):
    x=services.row(db,'SELECT * FROM facilities WHERE facility_id=:f',f=facility_id)
    if not x: raise HTTPException(404,'facility not found')
    return x
@app.get('/facilities/{facility_id}/docks')
def docks(facility_id:str,db:Session=Depends(get_db)): return services.rows(db,'SELECT * FROM docks WHERE facility_id=:f ORDER BY dock_id',f=facility_id)
@app.get('/appointments')
def appointments(facility_id:str|None=None,status:str|None=None,start_date:str|None=None,end_date:str|None=None,limit:int=Query(100,le=500),offset:int=Query(0,ge=0),db:Session=Depends(get_db)):
    where=[]; params={'l':limit}
    if facility_id: where.append('facility_id=:f'); params['f']=facility_id
    if status: where.append('status=:s'); params['s']=status
    if start_date: where.append('requested_start_ts >= CAST(:start AS date)'); params['start']=start_date
    if end_date: where.append('requested_start_ts < CAST(:finish AS date)+interval \'1 day\''); params['finish']=end_date
    params['o']=offset
    return services.rows(db,'SELECT * FROM appointments'+(' WHERE '+' AND '.join(where) if where else '')+' ORDER BY requested_start_ts LIMIT :l OFFSET :o',**params)
@app.get('/appointments/{appointment_id}')
def appointment(appointment_id:str,db:Session=Depends(get_db)): return services.get_appointment(db,appointment_id)
@app.post('/appointments',status_code=201)
def create(payload:AppointmentCreate,db:Session=Depends(get_db)): return services.create_appointment(db,payload)
@app.post('/appointments/{appointment_id}/schedule')
def schedule(appointment_id:str,payload:ScheduleRequest,db:Session=Depends(get_db)): return services.schedule(db,appointment_id,payload.start_ts,payload.candidate_intervals,payload.interval_minutes,False,payload.approved_override,payload.override_reason)
@app.post('/appointments/{appointment_id}/reschedule')
def reschedule(appointment_id:str,payload:ScheduleRequest,db:Session=Depends(get_db)): return services.schedule(db,appointment_id,payload.start_ts,payload.candidate_intervals,payload.interval_minutes,True,payload.approved_override,payload.override_reason)
@app.get('/scheduling/policy')
def scheduling_policy(): return {'deviation_minutes':settings.scheduling_deviation_minutes,'override_requires_reason':True}
@app.get('/availability/docks')
def dock_availability(facility_id:str,start_ts:datetime,end_ts:datetime,load_type:str='STANDARD',db:Session=Depends(get_db)):
    return services.rows(db,"SELECT d.* FROM docks d WHERE d.facility_id=:f AND d.dock_type=:l AND NOT EXISTS (SELECT 1 FROM dock_reservations r WHERE r.dock_id=d.dock_id AND r.status='RESERVED' AND r.start_ts<:e AND r.end_ts>:s)",f=facility_id,l=load_type,s=start_ts,e=end_ts)
@app.get('/availability/yard')
def yard_availability(facility_id:str,start_ts:datetime,end_ts:datetime,load_type:str='STANDARD',db:Session=Depends(get_db)):
    return services.rows(db,"SELECT y.* FROM yard_slots y WHERE y.facility_id=:f AND (:l<>'REFRIGERATED' OR y.slot_type='REEFER') AND NOT EXISTS (SELECT 1 FROM yard_reservations r WHERE r.yard_slot_id=y.yard_slot_id AND r.status='RESERVED' AND r.start_ts<:e AND r.end_ts>:s)",f=facility_id,l=load_type,s=start_ts,e=end_ts)
@app.get('/availability/labor')
def labor_availability(facility_id:str,start_ts:datetime,end_ts:datetime,skill:str='STANDARD',db:Session=Depends(get_db)):
    return services.rows(db,"SELECT s.*, s.workers-coalesce((SELECT sum(a.workers_required) FROM labor_allocations a JOIN appointments p ON p.appointment_id=a.appointment_id WHERE a.labor_shift_id=s.labor_shift_id AND a.status='ALLOCATED' AND p.scheduled_start_ts<:e AND p.scheduled_end_ts>:st),0) AS workers_available FROM labor_shifts s WHERE s.facility_id=:f AND s.start_ts<=:st AND s.end_ts>=:e AND position(:skill in s.skills)>0",f=facility_id,st=start_ts,e=end_ts,skill=skill)
def op(aid,target,payload,db): return services.transition(db,aid,target,payload.event_ts,payload.source,payload.actor)
@app.post('/appointments/{appointment_id}/arrive')
def arrive(appointment_id:str,payload:ArrivalRequest,db:Session=Depends(get_db)): return op(appointment_id,'ARRIVED',payload,db)
@app.post('/appointments/{appointment_id}/check-in')
def checkin(appointment_id:str,payload:ArrivalRequest,db:Session=Depends(get_db)): return op(appointment_id,'CHECKED_IN',payload,db)
@app.post('/appointments/{appointment_id}/service-start')
def service_start(appointment_id:str,payload:ArrivalRequest,db:Session=Depends(get_db)): return op(appointment_id,'IN_SERVICE',payload,db)
@app.post('/appointments/{appointment_id}/service-complete')
def service_complete(appointment_id:str,payload:ArrivalRequest,db:Session=Depends(get_db)): return op(appointment_id,'COMPLETED',payload,db)
@app.post('/appointments/{appointment_id}/depart')
def depart(appointment_id:str,payload:ArrivalRequest,db:Session=Depends(get_db)): return op(appointment_id,'DEPARTED',payload,db)
@app.get('/appointments/{appointment_id}/timeline')
def timeline(appointment_id:str,db:Session=Depends(get_db)): return services.rows(db,"SELECT event_type,event_ts,source, 'generator' AS actor, 'generator' AS rule_version, '{}'::jsonb AS decision_provenance FROM operational_events WHERE appointment_id=:a UNION ALL SELECT event_type,event_ts,source,actor,rule_version,decision_provenance FROM appointment_state_events WHERE appointment_id=:a ORDER BY event_ts",a=appointment_id)
@app.get('/exceptions')
def exceptions(status:str|None=None,cause_code:str|None=None,severity:str|None=None,db:Session=Depends(get_db)):
    where=[]; params={}
    for key,value in [('status',status),('cause_code',cause_code),('severity',severity)]:
        if value: where.append(f'{key}=:{key}'); params[key]=value
    return services.rows(db,"SELECT * FROM exceptions"+(" WHERE "+' AND '.join(where) if where else "")+" ORDER BY exception_id",**params)
@app.post('/exceptions/detect')
def detect_exceptions(db:Session=Depends(get_db)):
    return services.detect_missing_no_show_events(db)
@app.get('/analytics/overview')
def overview(facility_id:str|None=None,start_date:str|None=None,end_date:str|None=None,db:Session=Depends(get_db)):
    filters=[]; p={'f':facility_id}
    if facility_id: filters.append('a.facility_id=:f'); p['f']=facility_id
    if start_date: filters.append('a.requested_start_ts >= CAST(:start AS date)'); p['start']=start_date
    if end_date: filters.append("a.requested_start_ts < CAST(:finish AS date)+interval '1 day'"); p['finish']=end_date
    clause=' WHERE '+' AND '.join(filters) if filters else ''
    return services.row(db,f"SELECT count(*) AS total, count(DISTINCT a.facility_id) AS active_facilities, count(*) FILTER (WHERE a.status IN ('SCHEDULED','RESCHEDULED','ARRIVED','CHECKED_IN','IN_SERVICE')) AS scheduled, count(*) FILTER (WHERE a.status='WAITLISTED') AS waitlisted, count(*) FILTER (WHERE a.status IN ('COMPLETED','DEPARTED')) AS completed, count(*) FILTER (WHERE a.status='NO_SHOW') AS no_show, round(avg(waiting_minutes)::numeric,2) AS average_wait_minutes, percentile_cont(.95) WITHIN GROUP (ORDER BY waiting_minutes) AS p95_wait_minutes, (SELECT count(*) FROM docks d WHERE (CAST(:f AS varchar(16)) IS NULL OR d.facility_id=:f)) AS active_docks, (SELECT round(avg(dock_utilization)*100,2) FROM resource_utilization_metrics u WHERE (CAST(:f AS varchar(16)) IS NULL OR u.facility_id=:f)) AS dock_utilization_percent, (SELECT count(*) FROM exceptions e LEFT JOIN appointments x ON x.appointment_id=e.appointment_id WHERE e.status='OPEN' AND (CAST(:f AS varchar(16)) IS NULL OR x.facility_id=:f)) AS open_exceptions FROM appointments a LEFT JOIN derived_metrics m ON m.appointment_id=a.appointment_id{clause}",**p)
@app.get('/calendar/docks')
def calendar(facility_id:str,date:str,db:Session=Depends(get_db)):
    return {'docks':services.rows(db,"SELECT d.dock_id,d.dock_type,d.length_m, r.appointment_id,r.start_ts,r.end_ts,r.status FROM docks d LEFT JOIN dock_reservations r ON r.dock_id=d.dock_id AND r.start_ts < CAST(:date AS date)+interval '1 day' AND r.end_ts >= CAST(:date AS date) WHERE d.facility_id=:f ORDER BY d.dock_id,r.start_ts",f=facility_id,date=date)}
