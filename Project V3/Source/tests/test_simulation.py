import importlib.util
import json
from pathlib import Path
import numpy as np
import pandapower as pp
import pandapower.networks as pn
import pytest
from simulation.gridsim.network import build_network,calculate_q_mvar
from simulation.gridsim.scenarios import load_change,line_outage,load_disconnect,load_sweep
from simulation.gridsim.results import solve

ROOT=Path(__file__).resolve().parents[1]

def small_model():
    return {'buses':[{'id':n,'vn_kv':138} for n in ['SOURCE','DC1_BUS','DC2_BUS']],
        'sources':[{'id':'GRID','bus_id':'SOURCE'}],
        'lines':[{'id':f'L{i}','from_bus':'SOURCE','to_bus':f'DC{i}_BUS','length_km':10} for i in [1,2]],
        'loads':[{'id':f'DC{i}','bus_id':f'DC{i}_BUS','p_mw':p,'pf':.95,'onsite_gen_mw':0} for i,p in [(1,100),(2,150)]]}

def test_v4_regression():
    spec=importlib.util.spec_from_file_location('legacy',ROOT/'simulation/TL_Senior_Simulation_V4.py')
    v4=importlib.util.module_from_spec(spec);spec.loader.exec_module(v4)
    old=v4.build_and_run_network(138,100,v4.calculate_q_mvar(100,.95),150,v4.calculate_q_mvar(150,.95),10,.05,.4,1)
    new=build_network(small_model());result=solve(new)
    assert result['converged']
    np.testing.assert_allclose(new.res_bus.vm_pu,old.res_bus.vm_pu,atol=1e-9)
    np.testing.assert_allclose(new.res_line.loading_percent,old.res_line.loading_percent,atol=1e-7)
    assert result['totals']['losses_mw']==pytest.approx(float(old.res_line.pl_mw.sum()),abs=1e-9)

def test_ieee14_published_reference():
    # Solve the original MATPOWER-format case with standalone PYPOWER. Stored case
    # voltages are an initial guess, not an exact solved reference. Use matched pi
    # transformer models. Shared solver ancestry means this is NOT an independent
    # algorithm validation; a separately run MATPOWER check remains desirable.
    from pypower.api import case14,runpf,ppoption
    reference,ok=runpf(case14(),ppoption(VERBOSE=0,OUT_ALL=0,PF_TOL=1e-10))
    assert ok
    net=pn.case14();pp.runpp(net,numba=False,trafo_model='pi',tolerance_mva=1e-10)
    np.testing.assert_allclose(net.res_bus.vm_pu,reference['bus'][:,7],atol=.001,rtol=0)
    np.testing.assert_allclose(net.res_bus.va_degree-net.res_bus.va_degree.at[0],reference['bus'][:,8]-reference['bus'][0,8],atol=.1,rtol=0)

def test_scenarios_preserve_baseline_and_report_island():
    baseline=build_network(small_model());before=solve(baseline)
    out=line_outage(baseline,'L1');result=solve(out)
    assert result['converged'] and result['buses']['DC1_BUS']['vm_pu'] is None
    assert result['totals']['unsupplied_buses']==1
    assert baseline.line.in_service.all()
    disconnected=solve(load_disconnect(baseline,'DC1'))
    assert disconnected['loads']['DC1']['p_mw']==0
    assert solve(baseline)['totals']==before['totals']

def test_generation_and_connection_change():
    baseline=build_network(small_model())
    net=load_change(baseline,'DC1',120,.95,20,'DC2_BUS');r=solve(net)
    assert r['loads']['DC1']['net_grid_mw']==pytest.approx(100)
    assert r['loads']['DC1']['q_mvar']==pytest.approx(calculate_q_mvar(120,.95))
    assert r['loads']['DC1']['bus_id']=='DC2_BUS'
    assert solve(load_disconnect(net,'DC1'))['loads']['DC1']['net_grid_mw']==0

def test_nonconvergence_clears_results():
    net=build_network(small_model());net.load.p_mw=1e8
    r=solve(net)
    assert not r['converged'] and r['buses']=={} and r['totals']=={}

def test_houston_model_and_sweep():
    model=json.loads((ROOT/'data/model/houston_model.json').read_text())
    net=build_network(model);r=solve(net)
    assert r['converged'] and len(r['loads'])>=10
    assert r['totals']['unsupplied_buses']==0
    sweep=load_sweep(net,[0,.5,1,1.5])
    assert all(p['result']['converged'] for p in sweep)
    assert sweep[0]['result']['totals']['grid_supply_mw']<sweep[-1]['result']['totals']['grid_supply_mw']

@pytest.mark.parametrize('p,pf',[(-1,.95),(100,0),(100,1.1),(float('nan'),.95)])
def test_invalid_loads(p,pf):
    with pytest.raises(ValueError): calculate_q_mvar(p,pf)
