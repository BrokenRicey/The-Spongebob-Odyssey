import math
import time
from datetime import datetime,timezone
from simulation import TL_Senior_Simulation_V4 as v4
from pandapower.auxiliary import LoadflowNotConverged
from simulation.gridsim.config import LIMITS

def number(value):
    return float(value) if math.isfinite(float(value)) else None

def extract_results(net):
    buses={}
    violations=[]
    for i,b in net.bus.iterrows():
        row=net.res_bus.loc[i];v=number(row.vm_pu)
        buses[b['name']]={'vm_pu':v,'va_degree':number(row.va_degree),'kv':None if v is None else v*b.vn_kv,'supplied':v is not None}
        if v is None: violations.append({'id':b['name'],'type':'bus','metric':'vm_pu','value':None,'message':'Unsupplied bus'})
        elif not LIMITS['voltage_min_pu']<=v<=LIMITS['voltage_max_pu']:
            violations.append({'id':b['name'],'type':'bus','metric':'vm_pu','value':v,'message':'Low voltage' if v<LIMITS['voltage_min_pu'] else 'High voltage'})
    lines={}
    for i,l in net.line.iterrows():
        row=net.res_line.loc[i]
        values={k:number(row[k]) for k in ['loading_percent','i_ka','p_from_mw','q_from_mvar','pl_mw']}
        values['in_service']=bool(l.in_service)
        lines[l['name']]=values
        if l.in_service and values['loading_percent'] is not None and values['loading_percent']>LIMITS['loading_percent']:
            violations.append({'id':l['name'],'type':'line','metric':'loading_percent','value':values['loading_percent'],'message':'Overload'})
    transformers={}
    for i,t in net.trafo.iterrows():
        row=net.res_trafo.loc[i]
        transformers[t['name']]={k:number(row[k]) for k in ['loading_percent','pl_mw','p_hv_mw','q_hv_mvar']}
        if row.loading_percent>LIMITS['loading_percent']:
            violations.append({'id':t['name'],'type':'transformer','metric':'loading_percent','value':number(row.loading_percent),'message':'Overload'})
    loads={}
    for i,l in net.load.iterrows():
        gi=net.sgen.index[net.sgen.name==l['name']]
        generation=float(net.res_sgen.loc[gi,'p_mw'].sum())
        p=number(net.res_load.at[i,'p_mw'])
        loads[l['name']]={'p_mw':p,'q_mvar':number(net.res_load.at[i,'q_mvar']),'onsite_gen_mw':generation,
            'net_grid_mw':None if p is None else p-generation,'in_service':bool(l.in_service),
            'bus_id':str(net.bus.at[l.bus,'name'])}
    supply=float(net.res_ext_grid.p_mw.sum());loss=float(net.res_line.pl_mw.sum()+net.res_trafo.pl_mw.sum())
    validv=[r['vm_pu'] for r in buses.values() if r['vm_pu'] is not None]
    validl=[r['loading_percent'] for r in lines.values() if r['in_service'] and r['loading_percent'] is not None]
    totals={'grid_supply_mw':supply,'grid_supply_mvar':float(net.res_ext_grid.q_mvar.sum()),'losses_mw':loss,
            'losses_percent':loss/supply*100 if supply>0 else None,'min_voltage_pu':min(validv,default=None),
            'max_loading_percent':max(validl,default=None),'unsupplied_buses':sum(not b['supplied'] for b in buses.values())}
    return {'converged':True,'status':'converged','buses':buses,'lines':lines,'transformers':transformers,'loads':loads,
            'totals':totals,'violations':violations,'limits':LIMITS,'message':'Power flow converged'+(' • unsupplied buses detected' if totals['unsupplied_buses'] else '')}

def solve(net):
    start=time.perf_counter()
    try:
        v4.run_power_flow(net)
        result=extract_results(net)
    except (LoadflowNotConverged,ValueError,FloatingPointError) as exc:
        result={'converged':False,'status':'failed','message':f'Power flow failed: {exc}','buses':{},'lines':{},'loads':{},'transformers':{},'totals':{},'violations':[],'limits':LIMITS}
    result['engine'] = 'TL_Senior_Simulation_V4.run_power_flow'
    result.update(runtime_seconds=time.perf_counter()-start, timestamp=datetime.now(timezone.utc).isoformat())
    return result
