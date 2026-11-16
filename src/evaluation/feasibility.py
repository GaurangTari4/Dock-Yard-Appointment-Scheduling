"""Read-only scheduling feasibility measurements for generated profile exports."""
from __future__ import annotations
import json, math
from collections import Counter, defaultdict
from pathlib import Path
from src.generator.core import load_rows

def report(path: str | Path) -> dict:
    path=Path(path); appts=load_rows(path,'appointments'); ships={r['shipment_id']:r for r in load_rows(path,'shipments')}
    loads={a['appointment_id']:ships[f"SHP-2026-{a['appointment_id'][-6:]}"]['load_type'] for a in appts}
    wait=[a for a in appts if a['status']=='WAITLISTED']; allocated=[a for a in appts if a['status']!='WAITLISTED']
    docks=load_rows(path,'docks'); yards=load_rows(path,'yard_slots'); shifts=load_rows(path,'labor_shifts')
    requests_by_facility=Counter(a['facility_id'] for a in appts)
    request_by_day=Counter(a['requested_start_ts'][:10] for a in appts)
    request_by_hour=Counter(a['requested_start_ts'][11:13] for a in appts)
    req_by_load=Counter(loads[a['appointment_id']] for a in appts)
    wait_by_load=Counter(loads[a['appointment_id']] for a in wait)
    wait_by_direction=Counter(a['appointment_type'] for a in wait)
    demand_peak=max(Counter((a['facility_id'],a['requested_start_ts'][:13]) for a in appts).values())
    requested_minutes=sum(int(a['service_minutes']) for a in appts)
    scheduled_minutes=sum(int(a['service_minutes']) for a in allocated)
    dock_minutes=len(docks)*60*16*60
    labor_minutes=sum(int(s['workers'])*480 for s in shifts)
    return {
        'appointments':len(appts),'allocated':len(allocated),'waitlisted':len(wait),'waitlist_pct':round(100*len(wait)/len(appts),3),
        'waitlist_causes':dict(Counter(a['allocation_reason'] for a in wait)),
        'request_by_facility':dict(requests_by_facility),'request_by_day_min_max':[min(request_by_day.values()),max(request_by_day.values())],
        'request_by_hour':dict(sorted(request_by_hour.items())),'request_by_load':dict(req_by_load),'wait_by_load':dict(wait_by_load),'wait_by_direction':dict(wait_by_direction),'peak_facility_hour_requests':demand_peak,
        'docks_by_type':dict(Counter(d['dock_type'] for d in docks)),'yards_by_type':dict(Counter(y['slot_type'] for y in yards)),'labor_workers_per_shift':sorted(set(int(s['workers']) for s in shifts)),
        'requested_service_minutes':requested_minutes,'scheduled_service_minutes':scheduled_minutes,'dock_capacity_minutes':dock_minutes,'labor_capacity_minutes':labor_minutes,
    }
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('path');a=p.parse_args();print(json.dumps(report(a.path),indent=2))
