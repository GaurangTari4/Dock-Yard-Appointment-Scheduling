import os
from datetime import date, datetime, time, timedelta
import streamlit as st
from dashboard.api_client import APIClient, APIError
st.set_page_config(page_title='Dock & Yard Operations',layout='wide')
api=APIClient()
def call(fn):
    try: return fn()
    except APIError as e: st.error(f'API error: {e}'); return None
facilities=call(lambda:api.get('/facilities')) or []
facility=st.sidebar.selectbox('Facility',[x['facility_id'] for x in facilities]) if facilities else None
selected_date=st.sidebar.date_input('Date',date.today())
page=st.sidebar.radio('Operations',['Overview','Dock calendar','Appointments','Gate operations','Yard & labor','Exceptions'])
def overview():
    data=call(lambda:api.get('/analytics/overview',{'facility_id':facility,'start_date':str(selected_date),'end_date':str(selected_date)}))
    if not data:return
    cols=st.columns(5)
    for col,key,label in zip(cols,['total','scheduled','waitlisted','completed','no_show'],['Appointments','Scheduled','Waitlisted','Completed','No show']): col.metric(label,data.get(key,0))
    resources=st.columns(4)
    resources[0].metric('Active facilities',data.get('active_facilities',0))
    resources[1].metric('Active docks',data.get('active_docks',0))
    resources[2].metric('Dock utilization',f"{data.get('dock_utilization_percent',0) or 0}%")
    resources[3].metric('Open exceptions',data.get('open_exceptions',0))
    st.metric('Average / P95 wait (minutes)',f"{data.get('average_wait_minutes',0)} / {data.get('p95_wait_minutes',0)}")
    st.caption('Appointment metrics use the selected day. Dock utilization is a persisted facility reporting-period value, not live date-filtered utilization.')
def calendar():
    data=call(lambda:api.get('/calendar/docks',{'facility_id':facility,'date':str(selected_date)}))
    if not data:return
    st.subheader('Dock schedule')
    booked=[]
    for item in data['docks']:
        label=f"{item['dock_id']} · {item['dock_type']}"
        if not item['appointment_id']: st.write(label+' — available')
        else:
            marker={'RESERVED':'🟦','ACTIVE':'🟩','COMPLETED':'✅','SUPERSEDED':'↪️'}.get(item['status'],'•')
            st.write(f"{marker} {label} | {item['start_ts']} → {item['end_ts']} | {item['appointment_id']} | **{item['status']}**")
            booked.append(item['appointment_id'])
    if booked:
        aid=st.selectbox('Inspect reservation',sorted(set(booked)))
        detail=call(lambda:api.get('/appointments/'+aid))
        if detail: st.json(detail)
def appointments():
    st.subheader('Appointment management')
    status=st.selectbox('Status filter',['']+['REQUESTED','SCHEDULED','WAITLISTED','COMPLETED','DEPARTED'])
    offset=st.number_input('Result offset',min_value=0,step=100,value=0)
    data=call(lambda:api.get('/appointments',{'facility_id':facility,'status':status or None,'start_date':str(selected_date),'end_date':str(selected_date),'limit':100,'offset':int(offset)})) or []
    st.dataframe(data,use_container_width=True)
    with st.expander('Create appointment'):
        with st.form('create'):
            vehicle=st.text_input('Vehicle ID'); shipment=st.text_input('Shipment ID'); typ=st.selectbox('Direction',['INBOUND','OUTBOUND']); ts=st.text_input('Requested start (UTC ISO)','2026-10-22T06:00:00Z')
            if st.form_submit_button('Create'):
                result=call(lambda:api.post('/appointments',{'facility_id':facility,'vehicle_id':vehicle,'shipment_id':shipment,'appointment_type':typ,'requested_start_ts':ts}))
                if result: st.success(result['appointment_id'])
    if data:
        aid=st.selectbox('Schedule or reschedule appointment',[x['appointment_id'] for x in data],key='schedule_aid')
        selected=next(x for x in data if x['appointment_id']==aid)
        policy=call(lambda:api.get('/scheduling/policy')) or {'deviation_minutes':0}
        requested=selected['requested_start_ts']; scheduled=selected.get('scheduled_start_ts') or 'Not scheduled'
        st.caption(f"Requested: {requested} | Scheduled: {scheduled} | Permitted window: ±{policy['deviation_minutes']} minutes")
        start=st.text_input('Candidate start (UTC ISO)',requested,key=f'schedule_start_{aid}')
        intervals=st.number_input('Candidate intervals',min_value=1,max_value=200,value=48,key='schedule_intervals')
        override=st.checkbox('Approved scheduling-window override',key=f'override_{aid}')
        reason=st.text_input('Override reason',key=f'override_reason_{aid}') if override else None
        schedule_col,reschedule_col=st.columns(2)
        payload={'start_ts':start,'candidate_intervals':int(intervals),'interval_minutes':30,'approved_override':override,'override_reason':reason}
        can_schedule=selected['status'] in ('REQUESTED','WAITLISTED','RESCHEDULED')
        can_reschedule=selected['status'] in ('SCHEDULED','RESCHEDULED')
        if schedule_col.button('Schedule selected',disabled=not can_schedule):
            result=call(lambda:api.post(f'/appointments/{aid}/schedule',payload))
            if result: st.success(result)
        if reschedule_col.button('Reschedule selected',disabled=not can_reschedule):
            result=call(lambda:api.post(f'/appointments/{aid}/reschedule',payload))
            if result: st.success(result)
def gate():
    aid=st.text_input('Appointment ID')
    if not aid:return
    item=call(lambda:api.get('/appointments/'+aid))
    if not item:return
    timeline=call(lambda:api.get(f'/appointments/{aid}/timeline')) or []
    st.json(item); allowed={'SCHEDULED':('arrive','Arrive'),'RESCHEDULED':('arrive','Arrive'),'ARRIVED':('check-in','Check in'),'CHECKED_IN':('service-start','Start service'),'IN_SERVICE':('service-complete','Complete service'),'COMPLETED':('depart','Depart')}
    if item['status'] in allowed:
        path,label=allowed[item['status']]
        simulation=os.getenv('SIMULATION_MODE','').lower() in ('1','true','yes')
        default_ts=timeline[-1]['event_ts'] if timeline else item['scheduled_start_ts']
        if simulation and timeline:
            latest=datetime.fromisoformat(default_ts.replace('Z','+00:00'))
            if path=='service-start': latest += timedelta(minutes=1)
            elif path=='service-complete': latest += timedelta(minutes=item['service_minutes'])
            elif path=='depart': latest += timedelta(minutes=1)
            default_ts=latest.isoformat().replace('+00:00','Z')
        event_ts=st.text_input('Simulation event timestamp (UTC ISO)',default_ts,key=f'event_ts_{aid}') if simulation else datetime.utcnow().isoformat()+'Z'
        if simulation: st.caption('Isolated simulation mode: timestamp must not precede the latest lifecycle event.')
        if st.button(label):
            result=call(lambda:api.post(f'/appointments/{aid}/{path}',{'event_ts':event_ts,'source':'DASHBOARD','actor':'operator'}))
            if result: st.success(result['status'])
    else: st.info('No permitted operation for current status.')
    st.subheader('Immutable timeline'); st.dataframe(timeline,use_container_width=True)
def resources():
    start=datetime.combine(selected_date,time(8)); end=datetime.combine(selected_date,time(10))
    st.subheader('Availability at selected window')
    st.dataframe(call(lambda:api.get('/availability/yard',{'facility_id':facility,'start_ts':start.isoformat()+'Z','end_ts':end.isoformat()+'Z'})) or [])
    st.dataframe(call(lambda:api.get('/availability/labor',{'facility_id':facility,'start_ts':start.isoformat()+'Z','end_ts':end.isoformat()+'Z'})) or [])
def exceptions():
    st.subheader('Exceptions')
    severity=st.selectbox('Severity',['','HIGH','MEDIUM','LOW']); status=st.selectbox('State',['','OPEN','CLOSED'])
    st.dataframe(call(lambda:api.get('/exceptions',{'severity':severity or None,'status':status or None})) or [],use_container_width=True)
{'Overview':overview,'Dock calendar':calendar,'Appointments':appointments,'Gate operations':gate,'Yard & labor':resources,'Exceptions':exceptions}[page]()
