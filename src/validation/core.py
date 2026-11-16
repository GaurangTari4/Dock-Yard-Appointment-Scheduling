"""Independent validators; labels are read only from ground truth, never features."""
from __future__ import annotations
import csv, json, re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from src.generator.core import TABLES, load_rows

ID_PATTERNS={'facility_id':r'^FAC-\d{3}$','dock_id':r'^DOCK-FAC-\d{3}-\d{3}$','appointment_id':r'^APPT-\d{4}-\d{6}$','shipment_id':r'^SHP-\d{4}-\d{6}$','checkin_event_id':r'^CHECK-APPT-\d{4}-\d{6}-\d{2}$'}
def dt(v): return datetime.fromisoformat(v.replace('Z','+00:00'))
def issue(kind, rec, detail): return {'issue_type':kind,'record_id':rec,'detail':detail}

def validate(t):
    issues=[]
    # required IDs, uniqueness and deterministic formats
    pk_by_table={
        'facilities':'facility_id','docks':'dock_id','yard_slots':'yard_slot_id','carriers':'carrier_id','vehicles':'vehicle_id','labor_shifts':'labor_shift_id','capacity_calendars':'calendar_id','shipments':'shipment_id','handling_requirements':'handling_requirement_id','appointments':'appointment_id','appointment_shipments':None,'dock_reservations':'dock_reservation_id','yard_reservations':'yard_reservation_id','labor_allocations':'labor_allocation_id','checkin_events':'checkin_event_id','operational_events':'event_id','exceptions':'exception_id','derived_metrics':'appointment_id','resource_utilization_metrics':'facility_id'}
    for table, rows in t.items():
        pk=pk_by_table[table] if rows else None
        if pk:
            vals=[r.get(pk,'') for r in rows]
            if len(vals)!=len(set(vals)): issues.append(issue('PK_DUPLICATE',table,pk))
            if pk in ID_PATTERNS:
                for v in vals:
                    if not re.match(ID_PATTERNS[pk],v): issues.append(issue('ID_FORMAT',v,pk))
    ids={table:{r.get(pk_by_table[table],'') for r in rows} for table,rows in t.items()}
    # FK coverage selected all relationship columns which match an entity ID
    maps={'facility_id':'facilities','dock_id':'docks','yard_slot_id':'yard_slots','carrier_id':'carriers','vehicle_id':'vehicles','appointment_id':'appointments','shipment_id':'shipments','labor_shift_id':'labor_shifts'}
    for table,rows in t.items():
        for r in rows:
            for col,parent in maps.items():
                if col in r and table!=parent and r[col] and r[col] not in ids[parent]: issues.append(issue('FK_INTEGRITY',r.get(next(k for k in r if k.endswith('_id')),''),col))
    appointments={r['appointment_id']:r for r in t['appointments']}; shipments={r['shipment_id']:r for r in t['shipments']}; joins={r['appointment_id']:r['shipment_id'] for r in t['appointment_shipments']}
    # Every generated appointment has exactly one bridge row and its shipment direction agrees.
    bridge_counts=defaultdict(int)
    for r in t['appointment_shipments']: bridge_counts[r['appointment_id']]+=1
    for aid in appointments:
        if bridge_counts[aid]!=1: issues.append(issue('BRIDGE_INTEGRITY',aid,'expected exactly one shipment'))
    # legal states / event temporal ordering / duplicate semantic events
    allowed={'WAITLISTED','COMPLETED','NO_SHOW'}
    for a in t['appointments']:
        if a['status'] not in allowed: issues.append(issue('ENUM',a['appointment_id'],a['status']))
    grouped=defaultdict(list)
    for e in t['operational_events']: grouped[e['appointment_id']].append(e)
    for aid,es in grouped.items():
        seen=set(); prev=None
        for e in sorted(es,key=lambda x:int(x['sequence_no'])):
            pair=(e['event_type'],e['event_ts'])
            if pair in seen: issues.append(issue('DUPLICATE_EVENT',e['event_id'],'same type and timestamp'))
            seen.add(pair); cur=dt(e['event_ts'])
            if prev and cur<prev: issues.append(issue('TEMPORAL_ORDER',e['event_id'],'event sequence'))
            prev=cur
        if appointments[aid]['status']=='NO_SHOW' and not any(e['event_type']=='NO_SHOW' for e in es): issues.append(issue('MISSING_NO_SHOW_EVENT',aid,'no-show status without event'))
        observed=[e['event_type'] for e in sorted(es,key=lambda x:int(x['sequence_no']))]
        expected={'COMPLETED':['REQUESTED','CONFIRMED','CHECKED_IN','SERVICE_STARTED','SERVICE_COMPLETED'], 'WAITLISTED':['REQUESTED','WAITLISTED','CAPACITY_CHECKED','WAITLIST_REVIEWED','WAITLIST_FINALIZED']}
        status=appointments[aid]['status']
        if status in expected and observed!=expected[status]: issues.append(issue('INVALID_LIFECYCLE',aid,' -> '.join(observed)))
        if status=='NO_SHOW' and 'NO_SHOW' in observed and observed!=['REQUESTED','CONFIRMED','GATE_EXPECTED','NO_SHOW','EXCEPTION_RECORDED']:
            issues.append(issue('INVALID_LIFECYCLE',aid,' -> '.join(observed)))
    # reservations no overlap / compatibility
    bydock=defaultdict(list)
    for r in t['dock_reservations']: bydock[r['dock_id']].append(r)
    docktypes={r['dock_id']:r['dock_type'] for r in t['docks']}
    for dock,rs in bydock.items():
        ordered=sorted(rs,key=lambda x:x['start_ts'])
        for a,b in zip(ordered,ordered[1:]):
            if dt(a['end_ts'])>dt(b['start_ts']): issues.append(issue('DOCK_CAPACITY_EXCEEDED',b['dock_reservation_id'],dock))
        for r in rs:
            typ=shipments[joins[r['appointment_id']]]['load_type']
            if docktypes[dock]!=typ: issues.append(issue('DOCK_INCOMPATIBLE',r['dock_reservation_id'],f'{typ}/{docktypes[dock]}'))
    # Dock dimensions / vehicle capability and yard capacity/reefer requirements.
    vehicles={r['vehicle_id']:r for r in t['vehicles']}; docks={r['dock_id']:r for r in t['docks']}
    for r in t['dock_reservations']:
        ap=appointments[r['appointment_id']]; v=vehicles[ap['vehicle_id']]; d=docks[r['dock_id']]; load=shipments[joins[ap['appointment_id']]]['load_type']
        if v['capability']!=load or float(v['length_m'])>float(d['length_m']): issues.append(issue('VEHICLE_INCOMPATIBLE',r['dock_reservation_id'],'vehicle/load or length'))
    byyard=defaultdict(list); yard={r['yard_slot_id']:r for r in t['yard_slots']}
    for r in t['yard_reservations']: byyard[r['yard_slot_id']].append(r)
    for slot,rs in byyard.items():
        ordered=sorted(rs,key=lambda x:x['start_ts'])
        for a,b in zip(ordered,ordered[1:]):
            if dt(a['end_ts'])>dt(b['start_ts']): issues.append(issue('YARD_CAPACITY_EXCEEDED',b['yard_reservation_id'],slot))
        for r in rs:
            load=shipments[joins[r['appointment_id']]]['load_type']
            if load=='REFRIGERATED' and yard[slot]['slot_type']!='REEFER': issues.append(issue('YARD_INCOMPATIBLE',r['yard_reservation_id'],slot))
    # checkin cannot predate appointment request; labor shift must cover appointment
    for c in t['checkin_events']:
        # arrivals up to 30 minutes before an appointment are valid; before creation is not.
        if dt(c['event_ts']) < dt(appointments[c['appointment_id']]['created_ts']): issues.append(issue('CHECKIN_DATE_VIOLATION',c['checkin_event_id'],'before appointment creation'))
    shifts={r['labor_shift_id']:r for r in t['labor_shifts']}
    for a in t['labor_allocations']:
        ap=appointments[a['appointment_id']]; sh=shifts[a['labor_shift_id']]
        if not ap['scheduled_start_ts'] or not (dt(sh['start_ts'])<=dt(ap['scheduled_start_ts'])<dt(sh['end_ts'])): issues.append(issue('LABOR_UNAVAILABLE',a['labor_allocation_id'],'shift does not cover appointment'))
        if a['skill'] not in sh['skills'].split(','): issues.append(issue('LABOR_UNAVAILABLE',a['labor_allocation_id'],'missing skill'))
    allocations_by_shift=defaultdict(list)
    for a in t['labor_allocations']:
        ap=appointments[a['appointment_id']]; allocations_by_shift[a['labor_shift_id']].append((dt(ap['scheduled_start_ts']),dt(ap['scheduled_end_ts']),a))
    for sid,items in allocations_by_shift.items():
        workers=int(shifts[sid]['workers'])
        points=sorted([(s,1,int(a['workers_required'])) for s,e,a in items]+[(e,-1,int(a['workers_required'])) for s,e,a in items])
        used=0
        for _,kind,n in points:
            used += kind*n
            if used>workers: issues.append(issue('LABOR_CAPACITY_EXCEEDED',sid,str(used))); break
    # derived values reconciled from appointment/event source
    metrics={r['appointment_id']:r for r in t['derived_metrics']}
    for aid,a in appointments.items():
        m=metrics.get(aid)
        if not m or m['appointment_status']!=a['status'] or m['scheduled_service_minutes']!=a['service_minutes']:
            issues.append(issue('METRIC_RECONCILIATION',aid,'missing/status/scheduled mismatch')); continue
        events={e['event_type']:e for e in grouped[aid]}
        if a['status']=='COMPLETED':
            expected_actual=int((dt(events['SERVICE_COMPLETED']['event_ts'])-dt(events['CHECKED_IN']['event_ts'])).total_seconds()//60)
            expected_wait=max(0,int((dt(events['CHECKED_IN']['event_ts'])-dt(a['scheduled_start_ts'])).total_seconds()//60))
            if (int(m['actual_service_minutes']),int(m['waiting_minutes']),int(m['turnaround_minutes'])) != (expected_actual,expected_wait,expected_actual): issues.append(issue('METRIC_RECONCILIATION',aid,'event-derived mismatch'))
        elif a['status']=='NO_SHOW' and any(int(m[x])!=0 for x in ('actual_service_minutes','waiting_minutes','turnaround_minutes')): issues.append(issue('METRIC_RECONCILIATION',aid,'no-show metrics'))
    return issues

def validate_directory(path, injected=False):
    path=Path(path); t={x:load_rows(path,x) for x in TABLES}; issues=validate(t)
    expected=[]
    if injected:
        with (path/'ground_truth.csv').open(encoding='utf-8',newline='') as f: expected=[r['issue_type'] for r in csv.DictReader(f)]
    found=[x['issue_type'] for x in issues]; unexpected=sorted(set(found)-set(expected)); missing=sorted(set(expected)-set(found))
    return {'valid':not unexpected and not missing and (bool(found) if injected else not found),'issue_count':len(issues),'issues':issues,'expected_issue_types':expected,'unexpected_issue_types':unexpected,'missing_issue_types':missing}
