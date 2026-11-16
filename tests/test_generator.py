import copy, csv, json, re
from src.generator.core import generate, anomaly_rows, export
from src.validation.core import validate

def test_tiny_baseline_is_valid():
    assert validate(generate('tiny', 20261022)) == []

def test_injected_has_exact_required_types():
    injected, truth = anomaly_rows(generate('tiny', 20261022))
    types={x['issue_type'] for x in validate(injected)}
    assert types == {x['issue_type'] for x in truth}

def test_same_seed_same_content(tmp_path):
    a=generate('tiny',20261022); b=generate('tiny',20261022)
    export(a,tmp_path/'a','tiny',20261022); export(b,tmp_path/'b','tiny',20261022)
    assert (tmp_path/'a'/'manifest.json').read_bytes()==(tmp_path/'b'/'manifest.json').read_bytes()

def test_all_baseline_profiles_enforce_constraints():
    for profile in ('tiny', 'starter', 'full'):
        assert validate(generate(profile, 20261022)) == []

def test_resource_boundaries_and_event_order_are_detected():
    data=generate('tiny', 20261022)
    broken=copy.deepcopy(data)
    # Same yard/time creates a capacity breach independently of dock allocation.
    broken['yard_reservations'][1]['yard_slot_id']=broken['yard_reservations'][0]['yard_slot_id']
    broken['yard_reservations'][1]['start_ts']=broken['yard_reservations'][0]['start_ts']
    broken['yard_reservations'][1]['end_ts']=broken['yard_reservations'][0]['end_ts']
    # Reverse a lifecycle timestamp; it must not be silently accepted.
    events=[e for e in broken['operational_events'] if e['appointment_id']==broken['dock_reservations'][0]['appointment_id']]
    events[-1]['event_ts']='2026-10-01T00:00:00Z'
    kinds={x['issue_type'] for x in validate(broken)}
    assert {'YARD_CAPACITY_EXCEEDED','TEMPORAL_ORDER'} <= kinds

def test_missing_event_and_metric_reconciliation_are_detected():
    data=generate('tiny', 20261022)
    broken=copy.deepcopy(data)
    no_show=next(a for a in broken['appointments'] if a['status']=='NO_SHOW')
    broken['operational_events'][:]=[e for e in broken['operational_events'] if not (e['appointment_id']==no_show['appointment_id'] and e['event_type']=='NO_SHOW')]
    complete=next(a for a in broken['appointments'] if a['status']=='COMPLETED')
    next(m for m in broken['derived_metrics'] if m['appointment_id']==complete['appointment_id'])['waiting_minutes']='999'
    kinds={x['issue_type'] for x in validate(broken)}
    assert {'MISSING_NO_SHOW_EVENT','METRIC_RECONCILIATION'} <= kinds

def test_csv_json_and_sql_export_equivalence(tmp_path):
    data=generate('tiny',20261022); export(data,tmp_path,'tiny',20261022)
    for table, rows in data.items():
        assert json.loads((tmp_path/f'{table}.json').read_text()) == rows
        with (tmp_path/f'{table}.csv').open(newline='',encoding='utf-8') as f:
            assert list(csv.DictReader(f)) == [{k:str(v) for k,v in row.items()} for row in rows]
    sql=(tmp_path/'seed_data.sql').read_text()
    assert len(re.findall(r'^INSERT INTO ',sql,re.M)) == sum(map(len,data.values()))
    assert "''" not in sql  # nullable records must serialize to PostgreSQL NULL, not empty strings

def test_facilities_have_all_dock_capabilities_and_balanced_timestamp_spread():
    data=generate('full', 20261022)
    for facility in data['facilities']:
        types={d['dock_type'] for d in data['docks'] if d['facility_id']==facility['facility_id']}
        assert types == {'STANDARD','REFRIGERATED','HAZMAT'}
    requests=[a for a in data['appointments'] if a['facility_id']=='FAC-001']
    assert len({a['requested_start_ts'][:10] for a in requests}) > 50
    assert len({a['requested_start_ts'][11:13] for a in requests}) == 8

def test_allocation_reasons_match_terminal_scheduling_decision():
    data=generate('tiny',20261022)
    for appointment in data['appointments']:
        if appointment['status']=='WAITLISTED':
            assert appointment['allocation_reason'] != 'ALLOCATED'
        else:
            assert appointment['allocation_reason'] == 'ALLOCATED'
