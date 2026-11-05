import json
from copy import deepcopy
import pytest
from simulation.study import default_model, validate_load, run_baseline, run_scenario, save_study, load_study, export_csv


def spec(model,kind='Load change'):
    return {'kind':kind,'line':model['lines'][0]['id'],'load':deepcopy(model['loads'][0])}


def test_study_roundtrip_and_generation(tmp_path):
    model=default_model();s=spec(model);s['load'].update(p_mw=100,onsite_gen_mw=20)
    base=run_baseline(model);case=run_scenario(model,s)
    assert base['converged'] and case['converged']
    assert case['loads']['DC_01']['net_grid_mw']==pytest.approx(80)
    assert model['loads'][0]['p_mw']==30
    path=tmp_path/'study.gridstudy';save_study(path,model,s,base,case)
    assert load_study(path)==(model,s)
    export_csv(tmp_path/'out.csv',base,case)
    assert 'scenario,True,loads,DC_01,net_grid_mw,80' in (tmp_path/'out.csv').read_text(encoding='utf-8-sig')


@pytest.mark.parametrize('field,value',[('p_mw',-1),('p_mw',float('nan')),('onsite_gen_mw',float('inf')),('pf',0),('pf',True),('bus_id','missing')])
def test_invalid_loads(field,value):
    model=default_model();load=deepcopy(model['loads'][0]);load[field]=value
    with pytest.raises(ValueError):validate_load(load,model)


def test_reject_tampered_topology_and_duplicate_ids(tmp_path):
    m=default_model();path=tmp_path/'bad.gridstudy';s=spec(m);save_study(path,m,s)
    obj=json.loads(path.read_text());obj['model']['lines'][0]['to_bus']='INVALID';path.write_text(json.dumps(obj))
    with pytest.raises(ValueError,match='network revision'):load_study(path)
    m['loads'].append(deepcopy(m['loads'][0]));save_study(path,m,s)
    with pytest.raises(ValueError,match='Duplicate'):load_study(path)


def test_added_load_and_changed_connection():
    m=default_model();load=deepcopy(m['loads'][0]);load.update(id='NEW_LOAD',bus_id='BUS_12');m['loads'].append(load)
    assert len(run_baseline(m)['loads'])==11
    s=spec(m);s['load']['bus_id']='BUS_03'
    assert run_scenario(m,s)['loads']['DC_01']['bus_id']=='BUS_03'
