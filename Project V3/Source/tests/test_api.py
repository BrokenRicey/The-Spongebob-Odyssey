import json
from fastapi.testclient import TestClient
from app.server import app

client=TestClient(app)

def session():
    return {'X-Study-ID':client.post('/api/session').json()['study_id']}

def baseline(headers):
    response=client.post('/api/run',headers=headers,json={'type':'baseline','facility_id':'DC_01','p_mw':30,'pf':.95,'onsite_gen_mw':0})
    assert response.status_code==200
    assert response.json()['result']['converged']
    return response.json()

def test_baseline_scenario_export_and_session_isolation():
    h=session();b=baseline(h)
    response=client.post('/api/run',headers=h,json={'type':'line_outage','line_id':'L08','baseline_id':b['baseline_id']})
    assert response.status_code==200
    d=response.json();assert not d['result']['lines']['L08']['in_service']
    assert d['baseline']['lines']['L08']['in_service']
    export=client.get('/api/export',headers=h).json()
    assert export['baseline_id']==b['baseline_id']
    assert 'case,element_type,id,metric,value' in client.get('/api/export?format=csv',headers=h).text
    assert client.get('/api/export',headers=session()).status_code==409

def test_invalid_inputs_and_stale_baseline_id():
    h=session();b=baseline(h)
    for payload in [{'type':'load_change','facility_id':'DC_01','pf':0},
                    {'type':'line_outage','line_id':'does-not-exist'},
                    {'type':'baseline','p_mw':-1}, {'type':'baseline','unexpected':'code'}]:
        assert client.post('/api/run',headers=h,json=payload).status_code==422
    assert client.post('/api/run',headers=h,json={'type':'load_disconnect','facility_id':'DC_01','baseline_id':'stale'}).status_code==409
    fault=client.post('/api/run',headers=h,json={'type':'fault','bus_id':'BUS_01','baseline_id':b['baseline_id']}).json()
    assert fault['result']['status']=='not_implemented'
    assert fault['comparison'] is None

def test_failed_baseline_replaces_previous_results():
    h=session();baseline(h)
    response=client.post('/api/run',headers=h,json={'type':'baseline','facility_id':'DC_01','p_mw':10000,'pf':.001})
    assert response.status_code==200
    assert not response.json()['result']['converged']
    d=client.get('/api/export',headers=h).json()
    assert not d['baseline']['converged'] and d['scenario'] is None
    assert d['baseline']['totals']=={}

def test_layers_and_catalog():
    assert len(client.get('/api/facilities').json())>=10
    assert len(client.get('/api/layers/transmission').json()['features'])==802
    assert client.get('/api/layers/substations').json()['features']
    assert client.get('/api/model').json()['limits']['voltage_min_pu']==.95

def test_sweep_export():
    h=session();b=baseline(h)
    d=client.post('/api/run',headers=h,json={'type':'load_sweep','baseline_id':b['baseline_id'],'scale_levels':[0,1,1.5]}).json()
    assert len(d['result']['points'])==3
    assert ',sweep,' in client.get('/api/export?format=csv',headers=h).text
