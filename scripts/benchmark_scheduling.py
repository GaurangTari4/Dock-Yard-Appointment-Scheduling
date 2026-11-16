"""Persisted HTTP POST benchmark; run only against the isolated acceptance API."""
import concurrent.futures, csv, json, os, statistics, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests
import psycopg

BASE=os.getenv('BENCHMARK_API_URL','http://logistics-api-test:8000').rstrip('/')
OUT=Path(os.getenv('BENCHMARK_RESULTS_DIR','/app/reports'))
JSON_OUT=OUT/'post_benchmark_results.json'; CSV_OUT=OUT/'post_benchmark_results.csv'
VEH,FAC='VEH-00001','FAC-001'; N=int(os.getenv('BENCHMARK_REQUESTS','100'))
def percentile(v,p):
    v=sorted(v); return v[min(len(v)-1,round((len(v)-1)*p))]
def wait_for_health(attempts=30):
    diagnostic='no HTTP response'
    for _ in range(attempts):
        try:
            r=requests.get(BASE+'/health',timeout=1)
            if r.ok and r.json().get('status')=='ok': return
            diagnostic=f'HTTP {r.status_code}: {r.text[:200]}'
        except requests.RequestException as exc: diagnostic=repr(exc)
        time.sleep(.25)
    raise RuntimeError(f'acceptance API not ready at {BASE}: {diagnostic}')
def post(path,payload):
    started=time.perf_counter(); r=requests.post(BASE+path,json=payload,timeout=30); elapsed=(time.perf_counter()-started)*1000
    try: body=r.json()
    except ValueError: body={'raw':r.text[:200]}
    return elapsed,r.status_code,body
def create(start, shipment_id):
    _,status,body=post('/appointments',{'facility_id':FAC,'vehicle_id':VEH,'shipment_id':shipment_id,'appointment_type':'INBOUND','requested_start_ts':start.isoformat()})
    if status!=201: raise RuntimeError(f'fixture creation failed: HTTP {status} {body}')
    return body['appointment_id']
def benchmark_shipments(sequence, count):
    """Provision distinct, valid benchmark loads before timing API operations.

    These rows exist only in logistics_test; operational POST timing never includes
    fixture insert time and each open appointment has a distinct shipment.
    """
    url=os.environ['DATABASE_URL'].replace('postgresql+psycopg://','postgresql://',1)
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT carrier_id FROM carriers ORDER BY carrier_id LIMIT 1')
            carrier=cur.fetchone()[0]
            ids=[]
            for index in range(count):
                shipment_id=f'SHP-BENCH-{sequence:03d}-{index:04d}'
                requirement_id=f'HR-BENCH-{sequence:03d}-{index:04d}'
                cur.execute("""INSERT INTO shipments
                    (shipment_id,carrier_id,direction,load_type,weight_kg,pallet_count,status)
                    VALUES (%s,%s,'INBOUND','STANDARD',1000,10,'PLANNED')
                    ON CONFLICT (shipment_id) DO NOTHING""",(shipment_id,carrier))
                cur.execute("""INSERT INTO handling_requirements
                    (handling_requirement_id,shipment_id,requirement_type,requires_reefer,requires_hazmat_cert,service_minutes)
                    VALUES (%s,%s,'STANDARD',false,false,60)
                    ON CONFLICT (shipment_id) DO NOTHING""",(requirement_id,shipment_id))
                ids.append(shipment_id)
    return ids
def times(base,conflict):
    if conflict: return [base] * N
    result=[]; day=base
    while len(result)<N:
        if day.weekday()<5:
            for hour in (0,4,8):
                result.append(day+timedelta(hours=hour))
                if len(result)==N: break
        day+=timedelta(days=1)
    return result
def persist(results):
    OUT.mkdir(parents=True,exist_ok=True); tmp=JSON_OUT.with_suffix('.tmp'); tmp.write_text(json.dumps(results,indent=2),encoding='utf-8'); tmp.replace(JSON_OUT)
    with CSV_OUT.open('w',newline='',encoding='utf-8') as h:
        w=csv.DictWriter(h,fieldnames=list(results[0])); w.writeheader(); w.writerows(results)
def run(kind,concurrency,sequence):
    base=datetime(2026,10,22,6,tzinfo=timezone.utc)+timedelta(days=sequence)
    starts=times(base,kind=='conflict')
    shipments=benchmark_shipments(sequence,N)
    ids=[create(start,shipment_id) for start,shipment_id in zip(starts,shipments)]
    if kind=='reschedule':
        for appointment_id,start in zip(ids,starts):
            _,status,body=post(f'/appointments/{appointment_id}/schedule',{'start_ts':start.isoformat(),'candidate_intervals':48,'interval_minutes':30})
            if status != 200 or body.get('status') != 'SCHEDULED':
                raise RuntimeError(f'reschedule fixture allocation failed: HTTP {status} {body}')
        # Rescheduling to the current request window measures the endpoint without
        # introducing an out-of-window request as a benchmark artifact.
    suffix='reschedule' if kind=='reschedule' else 'schedule'
    def one(pair):
        a,s=pair; return post(f'/appointments/{a}/{suffix}',{'start_ts':s.isoformat(),'candidate_intervals':1 if kind=='conflict' else 48,'interval_minutes':30})
    wall=time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as p: out=list(p.map(one,zip(ids,starts)))
    elapsed=time.perf_counter()-wall; l=[x[0] for x in out]
    return {'workload':kind,'concurrency':concurrency,'requests':N,'mean_ms':round(statistics.mean(l),3),'p50_ms':round(percentile(l,.5),3),'p95_ms':round(percentile(l,.95),3),'p99_ms':round(percentile(l,.99),3),'max_ms':round(max(l),3),'throughput_rps':round(N/elapsed,3),'successful':sum(x[2].get('status') in ('SCHEDULED','RESCHEDULED') for x in out),'expected_business_conflicts':sum(x[2].get('status')=='WAITLISTED' for x in out),'unexpected_http_errors':sum(x[1]>=400 for x in out)}
if __name__=='__main__':
    wait_for_health(); results=json.loads(JSON_OUT.read_text()) if JSON_OUT.exists() else []; sequence=len(results)
    selected=os.getenv('BENCHMARK_WORKLOADS','schedule,reschedule,concurrent,conflict').split(',')
    for kind in selected:
        for c in (1,5,10,20):
            row=run('schedule' if kind=='concurrent' else kind,c,sequence); row['workload']=kind; results.append(row); persist(results); sequence+=1
    print(json.dumps(results,indent=2))
