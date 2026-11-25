from copy import deepcopy
from simulation.gridsim.network import calculate_q_mvar

def index_by_id(table, element_id):
    matches=table.index[table.name==element_id]
    if len(matches)!=1: raise ValueError(f'Unknown or ambiguous element: {element_id}')
    return matches[0]

def load_change(baseline, facility_id, p_mw, pf, onsite_gen_mw, bus_id=None):
    net=deepcopy(baseline)
    i=index_by_id(net.load,facility_id); g=index_by_id(net.sgen,facility_id)
    if onsite_gen_mw<0: raise ValueError('Onsite generation must be nonnegative')
    net.load.loc[i,['p_mw','q_mvar']]=[p_mw,calculate_q_mvar(p_mw,pf)]
    net.sgen.at[g,'p_mw']=onsite_gen_mw
    if bus_id:
        b=index_by_id(net.bus,bus_id)
        net.load.at[i,'bus']=b; net.sgen.at[g,'bus']=b
    return net

def line_outage(baseline,line_id):
    net=deepcopy(baseline);net.line.at[index_by_id(net.line,line_id),'in_service']=False
    return net

def load_disconnect(baseline,facility_id):
    net=deepcopy(baseline)
    net.load.at[index_by_id(net.load,facility_id),'in_service']=False
    net.sgen.at[index_by_id(net.sgen,facility_id),'in_service']=False
    return net

def load_sweep(baseline,scale_levels):
    from simulation.gridsim.results import solve
    rows=[]
    for scale in scale_levels:
        if not 0<=scale<=1.5: raise ValueError('Sweep factors must lie between 0 and 1.5')
        net=deepcopy(baseline);net.load[['p_mw','q_mvar']]*=scale
        rows.append({'scale':scale,'result':solve(net)})
    return rows

def fault(bus_id):
    return {'status':'not_implemented','converged':False,'message':'Fault analysis requires validated short-circuit parameters.'}
