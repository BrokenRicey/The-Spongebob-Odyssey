import math
import pandapower as pp
from simulation import TL_Senior_Simulation_V4 as v4
from simulation.gridsim.config import LINE_PARAMETERS

def calculate_q_mvar(p_mw, pf):
    if not math.isfinite(p_mw) or p_mw<0 or not math.isfinite(pf) or not 0<pf<=1:
        raise ValueError('Demand must be nonnegative and power factor in (0, 1]')
    return float(v4.calculate_q_mvar(p_mw, pf))

def build_network(model):
    net=pp.create_empty_network()
    ids={}
    for kind in ['buses','lines','loads','transformers','sources']:
        rows=model.get(kind,[])
        names=[r['id'] for r in rows]
        if len(set(names))!=len(names): raise ValueError(f'Duplicate {kind} IDs')
    for b in model['buses']:
        if b['vn_kv']<=0: raise ValueError('Bus voltage must be positive')
        ids[b['id']]=pp.create_bus(net,vn_kv=b['vn_kv'],name=b['id'])
    for s in model['sources']:
        pp.create_ext_grid(net,bus=ids[s['bus_id']],vm_pu=s.get('vm_pu',1),name=s['id'])
    for line in model['lines']:
        params={k:line.get(k,v) for k,v in LINE_PARAMETERS.items()}
        if line['length_km']<=0 or params['max_i_ka']<=0 or min(params.values())<0: raise ValueError('Invalid line parameters')
        a,b=ids[line['from_bus']],ids[line['to_bus']]
        if net.bus.at[a,'vn_kv']!=net.bus.at[b,'vn_kv']: raise ValueError('Different voltage levels require a transformer')
        pp.create_line_from_parameters(net,a,b,length_km=line['length_km'],name=line['id'],**params)
    for t in model.get('transformers',[]):
        params={k:v for k,v in t.items() if k in ['sn_mva','vn_hv_kv','vn_lv_kv','vk_percent','vkr_percent','pfe_kw','i0_percent','shift_degree']}
        pp.create_transformer_from_parameters(net,ids[t['hv_bus']],ids[t['lv_bus']],name=t['id'],**params)
    for load in model['loads']:
        p,pf,gen=load['p_mw'],load['pf'],load.get('onsite_gen_mw',0)
        if gen<0 or not math.isfinite(gen): raise ValueError('Invalid onsite generation')
        pp.create_load(net,ids[load['bus_id']],p_mw=p,q_mvar=calculate_q_mvar(p,pf),name=load['id'])
        pp.create_sgen(net,ids[load['bus_id']],p_mw=gen,q_mvar=0,name=load['id'])
    return net
