"""Repeatable timing report; results are observations, not acceptance guarantees."""
import json
import platform
import statistics
import time
import importlib.metadata
from scripts.common import ROOT,save
from simulation.gridsim.network import build_network
from simulation.gridsim.results import solve
from simulation.gridsim.scenarios import load_sweep

def main():
    model=json.loads((ROOT/'data/model/houston_model.json').read_text(encoding='utf-8'))
    durations=[]
    for _ in range(10):
        start=time.perf_counter();net=build_network(model);r=solve(net)
        if not r['converged']:raise RuntimeError(r['message'])
        durations.append(time.perf_counter()-start)
    start=time.perf_counter();points=load_sweep(net,[i/10 for i in range(16)]);sweep=time.perf_counter()-start
    report={'platform':platform.platform(),'processor':platform.processor(),'python':platform.python_version(),
            'pandapower':importlib.metadata.version('pandapower'),'buses':len(model['buses']),'loads':len(model['loads']),
            'ten_build_and_run_seconds':durations,'median_seconds':statistics.median(durations),'maximum_seconds':max(durations),
            'sweep_seconds':sweep,'sweep_converged':all(p['result']['converged'] for p in points),
            'baseline_totals':r['totals'],'note':'Measured local timings, no browser-render timing or 95% confidence claim.'}
    save('docs/benchmark.json',report);print(json.dumps(report,indent=2))

if __name__=='__main__':main()
