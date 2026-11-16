import pytest
from dashboard.api_client import APIClient, APIError
from dashboard.workflows import next_action, valid_create
def test_client_error_handling(monkeypatch):
    def fail(*a,**k): raise __import__('requests').RequestException('offline')
    monkeypatch.setattr('dashboard.api_client.requests.request',fail)
    with pytest.raises(APIError): APIClient('http://example').get('/health')
def test_filters_and_forms():
    assert valid_create({'facility_id':'FAC-001','vehicle_id':'VEH-1','shipment_id':'SHP-1','appointment_type':'INBOUND','requested_start_ts':'2026-01-01T00:00:00Z'})
    assert not valid_create({'facility_id':'FAC-001'})
def test_lifecycle_action_and_empty_state():
    assert next_action('SCHEDULED')=='arrive'
    assert next_action('RESCHEDULED')=='arrive'
    assert next_action('DEPARTED') is None
