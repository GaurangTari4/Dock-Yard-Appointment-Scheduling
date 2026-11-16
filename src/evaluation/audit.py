"""Read-only profile audit used to produce the data-quality report."""
from __future__ import annotations
import json, math
from collections import Counter
from pathlib import Path
from src.generator.core import TABLES, load_rows
from src.validation.core import validate_directory

def profile_stats(path: str | Path) -> dict:
    path=Path(path); rows={t:load_rows(path,t) for t in TABLES}
    waits=sorted(int(r['waiting_minutes']) for r in rows['derived_metrics'] if r['appointment_status']=='COMPLETED')
    events=rows['operational_events']; pairs=[(r['appointment_id'],r['sequence_no']) for r in events]
    ids=[r['event_id'] for r in events]
    by_appointment=Counter(r['appointment_id'] for r in events)
    utilization=[float(r['dock_utilization']) for r in rows['resource_utilization_metrics']]
    ground_truth=load_rows(path,'ground_truth')
    return {
        'row_counts':{k:len(v) for k,v in rows.items()},
        'baseline_validation':validate_directory(path/'baseline',False),
        'injected_validation':validate_directory(path,True),
        'anomaly_detection_counts':Counter(x['issue_type'] for x in validate_directory(path,True)['issues']),
        'average_wait_minutes':round(sum(waits)/len(waits),3) if waits else 0,
        'p95_wait_minutes':waits[math.ceil(.95*len(waits))-1] if waits else 0,
        'dock_utilization_avg':round(sum(utilization)/len(utilization),6),
        'dock_utilization_min':min(utilization), 'dock_utilization_max':max(utilization),
        'no_show_count':sum(1 for r in rows['appointments'] if r['status']=='NO_SHOW'),
        'waitlisted_count':sum(1 for r in rows['appointments'] if r['status']=='WAITLISTED'),
        'requested_day_distribution':dict(sorted(Counter(r['requested_start_ts'][:10] for r in rows['appointments']).items())),
        'event_integrity':{'events':len(events),'unique_event_ids':len(set(ids)),'unique_appointment_sequences':len(set(pairs)),'appointments_with_five_events':sum(v==5 for v in by_appointment.values()),'duplicate_event_ids':len(events)-len(set(ids)),'duplicate_appointment_sequences':len(events)-len(set(pairs))},
        'ground_truth_types':Counter(r['issue_type'] for r in ground_truth),
    }

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(); p.add_argument('path'); args=p.parse_args()
    print(json.dumps(profile_stats(args.path),indent=2,default=dict))
