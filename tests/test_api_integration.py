"""Runs only when API_TEST_DATABASE_URL points at an isolated PostgreSQL database."""
import os
from concurrent.futures import ThreadPoolExecutor
import pytest

TEST_URL=os.getenv('API_TEST_DATABASE_URL')
if not TEST_URL: pytest.skip('API_TEST_DATABASE_URL not configured',allow_module_level=True)
os.environ['DATABASE_URL']=TEST_URL
from starlette.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from sqlalchemy import text

@pytest.fixture(scope='module')
def client():
    with TestClient(app) as c: yield c
def fixture_shipment(key, load_type='STANDARD'):
    """Create an isolated, valid shipment rather than reusing a baseline load."""
    shipment_id=f'SHP-TEST-{key:06d}'
    requirement_id=f'HR-TEST-{key:06d}'
    with SessionLocal.begin() as db:
        carrier=db.execute(text('SELECT carrier_id FROM carriers ORDER BY carrier_id LIMIT 1')).scalar_one()
        db.execute(text("""INSERT INTO shipments
            (shipment_id,carrier_id,direction,load_type,weight_kg,pallet_count,status)
            VALUES (:s,:c,'INBOUND',:l,1000,10,'PLANNED') ON CONFLICT (shipment_id) DO NOTHING"""),
            {'s':shipment_id,'c':carrier,'l':load_type})
        db.execute(text("""INSERT INTO handling_requirements
            (handling_requirement_id,shipment_id,requirement_type,requires_reefer,requires_hazmat_cert,service_minutes)
            VALUES (:h,:s,:l,:reefer,:hazmat,60) ON CONFLICT (shipment_id) DO NOTHING"""),
            {'h':requirement_id,'s':shipment_id,'l':load_type,
             'reefer':load_type=='REFRIGERATED','hazmat':load_type=='HAZMAT'})
    return shipment_id
def create(client, shipment_key=1, load_type='STANDARD', vehicle='VEH-00001', requested='2026-10-22T06:00:00Z'):
    shipment=fixture_shipment(shipment_key,load_type)
    r=client.post('/appointments',json={'facility_id':'FAC-001','vehicle_id':vehicle,'shipment_id':shipment,'appointment_type':'INBOUND','requested_start_ts':requested})
    assert r.status_code==201, r.text; return r.json()['appointment_id']
def test_lifecycle_and_history(client):
    aid=create(client,requested='2026-12-18T06:00:00Z'); assert client.post(f'/appointments/{aid}/schedule',json={'start_ts':'2026-12-18T06:00:00Z','candidate_intervals':48}).json()['status']=='SCHEDULED'
    for path, expected, ts in [('arrive','ARRIVED','2026-12-18T06:10:00Z'),('check-in','CHECKED_IN','2026-12-18T06:10:00Z'),('service-start','IN_SERVICE','2026-12-18T06:10:00Z'),('service-complete','COMPLETED','2026-12-18T07:10:00Z'),('depart','DEPARTED','2026-12-18T07:11:00Z')]:
        r=client.post(f'/appointments/{aid}/{path}',json={'event_ts':ts})
        assert r.status_code==200 and r.json()['status']==expected, r.text
    assert len(client.get(f'/appointments/{aid}/timeline').json()) >= 7
def test_invalid_transition_and_reschedule_history(client):
    aid=create(client,2,requested='2026-12-17T06:00:00Z')
    assert client.post(f'/appointments/{aid}/arrive',json={}).status_code==409
    assert client.get(f'/appointments/{aid}').json()['status']=='REQUESTED'  # failed transition rolls back
    assert client.post(f'/appointments/{aid}/schedule',json={'start_ts':'2026-12-17T06:00:00Z','candidate_intervals':48}).json()['status']=='SCHEDULED'
    assert client.post(f'/appointments/{aid}/reschedule',json={'start_ts':'2026-12-17T18:00:00Z','candidate_intervals':12,'approved_override':True,'override_reason':'integration test'}).status_code==200
    assert client.get(f'/appointments/{aid}').json()['status']=='RESCHEDULED'
    assert client.post(f'/appointments/{aid}/arrive',json={'event_ts':'2026-12-17T18:00:00Z'}).json()['status']=='ARRIVED'
    for path, expected, ts in [('check-in','CHECKED_IN','2026-12-17T18:01:00Z'),('service-start','IN_SERVICE','2026-12-17T18:01:00Z'),('service-complete','COMPLETED','2026-12-17T19:01:00Z'),('depart','DEPARTED','2026-12-17T19:02:00Z')]:
        assert client.post(f'/appointments/{aid}/{path}',json={'event_ts':ts}).json()['status']==expected
def test_concurrent_first_feasible_booking(client):
    def request(index):
        aid=create(client,300+index,requested='2026-12-16T06:00:00Z')
        return client.post(f'/appointments/{aid}/schedule',json={'start_ts':'2026-12-16T06:00:00Z'}).json()['status']
    with ThreadPoolExecutor(max_workers=8) as pool: states=list(pool.map(request,range(8)))
    assert states.count('SCHEDULED') <= 6
    assert set(states) <= {'SCHEDULED','WAITLISTED'}
def test_early_checkin_persists_exception(client):
    aid=create(client,4,requested='2026-12-18T10:00:00Z')
    assert client.post(f'/appointments/{aid}/schedule',json={'start_ts':'2026-12-18T10:00:00Z','candidate_intervals':48}).json()['status']=='SCHEDULED'
    assert client.post(f'/appointments/{aid}/arrive',json={'event_ts':'2026-12-18T09:00:00Z'}).status_code==200
    assert client.post(f'/appointments/{aid}/check-in',json={'event_ts':'2026-12-18T09:00:00Z'}).status_code==200
    assert any(e['appointment_id']==aid and e['issue_type']=='CHECKIN_DATE_VIOLATION' for e in client.get('/exceptions').json())
def test_metric_reconciliation_and_event_order(client):
    aid=create(client,5,requested='2026-12-14T12:00:00Z')
    assert client.post(f'/appointments/{aid}/schedule',json={'start_ts':'2026-12-14T12:00:00Z','candidate_intervals':48}).json()['status']=='SCHEDULED'
    for path,ts in [('arrive','2026-12-14T12:00:00Z'),('check-in','2026-12-14T12:05:00Z'),('service-start','2026-12-14T12:20:00Z')]:
        assert client.post(f'/appointments/{aid}/{path}',json={'event_ts':ts}).status_code==200
    assert client.post(f'/appointments/{aid}/service-complete',json={'event_ts':'2026-12-14T12:20:00Z'}).status_code==409
    for path,ts in [('service-complete','2026-12-14T13:20:00Z'),('depart','2026-12-14T13:30:00Z')]:
        assert client.post(f'/appointments/{aid}/{path}',json={'event_ts':ts}).status_code==200
    with SessionLocal() as db:
        metrics=db.execute(text("SELECT waiting_minutes,actual_service_minutes,turnaround_minutes FROM derived_metrics WHERE appointment_id=:a"),{'a':aid}).mappings().one()
    assert dict(metrics)=={'waiting_minutes':20,'actual_service_minutes':60,'turnaround_minutes':90}
    assert client.post(f'/appointments/{aid}/depart',json={'event_ts':'2026-12-14T12:00:00Z'}).status_code==409
def test_incompatible_vehicle_is_explainably_waitlisted(client):
    aid=create(client,13,'REFRIGERATED','VEH-00012','2026-12-11T06:00:00Z')
    scheduled=client.post(f"/appointments/{aid}/schedule",json={'start_ts':'2026-12-11T06:00:00Z','candidate_intervals':1}).json()
    assert scheduled['status']=='WAITLISTED' and scheduled['allocation_reason']=='VEHICLE_INCOMPATIBLE'
def test_shipment_cannot_back_two_open_appointments(client):
    shipment=fixture_shipment(99)
    first=client.post('/appointments',json={'facility_id':'FAC-001','vehicle_id':'VEH-00001','shipment_id':shipment,'appointment_type':'INBOUND','requested_start_ts':'2026-10-22T06:00:00Z'})
    assert first.status_code==201
    duplicate=client.post('/appointments',json={'facility_id':'FAC-001','vehicle_id':'VEH-00001','shipment_id':shipment,'appointment_type':'INBOUND','requested_start_ts':'2026-10-22T06:00:00Z'})
    assert duplicate.status_code==409
def test_scheduling_window_and_audited_override(client):
    aid=create(client,7,requested='2026-12-10T06:00:00Z')
    assert client.post(f'/appointments/{aid}/schedule',json={'start_ts':'2026-12-09T06:00:00Z'}).status_code==409
    assert client.post(f'/appointments/{aid}/schedule',json={'start_ts':'2026-12-11T06:00:00Z'}).status_code==409
    assert client.post(f'/appointments/{aid}/schedule',json={'start_ts':'2026-12-10T06:00:00Z','candidate_intervals':48}).json()['status']=='SCHEDULED'
def test_missing_no_show_detector(client):
    aid=create(client,6)
    with SessionLocal.begin() as db:
        db.execute(text("UPDATE appointments SET status='NO_SHOW' WHERE appointment_id=:a"),{'a':aid})
    assert client.post('/exceptions/detect').json()['detected'] >= 1
    assert any(e['appointment_id']==aid and e['issue_type']=='MISSING_NO_SHOW_EVENT' for e in client.get('/exceptions').json())
def test_dashboard_read_models(client):
    overview=client.get('/analytics/overview',params={'facility_id':'FAC-001','start_date':'2026-10-22','end_date':'2026-10-22'})
    assert overview.status_code==200
    assert {'total','active_facilities','active_docks','dock_utilization_percent','open_exceptions'} <= set(overview.json())
    calendar=client.get('/calendar/docks',params={'facility_id':'FAC-001','date':'2026-10-22'})
    assert calendar.status_code==200 and isinstance(calendar.json()['docks'],list)
