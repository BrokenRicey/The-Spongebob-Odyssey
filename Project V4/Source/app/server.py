import csv
import io
import json
import threading
import time
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Literal
from fastapi import FastAPI,Header,HTTPException
from fastapi.responses import FileResponse,Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field,ConfigDict,model_validator
from simulation.gridsim.catalog import load_facilities
from simulation.gridsim.network import build_network
from simulation.gridsim.config import LIMITS
from simulation.gridsim import scenarios
from simulation.gridsim.results import solve

ROOT=Path(__file__).resolve().parents[1]
MODEL=json.loads((ROOT/'data/model/houston_model.json').read_text(encoding='utf-8'))
FACILITIES=load_facilities()
app=FastAPI(title='Houston Grid Study',version='0.1.0')
sessions={}
lock=threading.RLock()

class RunRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    type:Literal['baseline','load_change','line_outage','load_disconnect','load_sweep','fault']
    baseline_id:str|None=None
    facility_id:str|None=None
    bus_id:str|None=None
    line_id:str|None=None
    p_mw:float=Field(default=30,ge=0,le=10000)
    pf:float=Field(default=.95,gt=0,le=1)
    onsite_gen_mw:float=Field(default=0,ge=0,le=10000)
    scale_levels:list[float]=Field(default_factory=lambda:[i/10 for i in range(16)],min_length=1,max_length=16)

    @model_validator(mode='after')
    def validate_ids(self):
        for field,items in [('facility_id',MODEL['loads']),('bus_id',MODEL['buses']),('line_id',MODEL['lines'])]:
            value=getattr(self,field)
            if value is not None and value not in {r['id'] for r in items}: raise ValueError(f'Unknown {field}: {value}')
        if self.type in ('load_change','load_disconnect') and not self.facility_id: raise ValueError('Select a facility')
        if self.type=='line_outage' and not self.line_id: raise ValueError('Select a line')
        if self.type=='fault' and not self.bus_id: raise ValueError('Select a bus')
        if any(not 0<=s<=1.5 for s in self.scale_levels): raise ValueError('Sweep factors must be in [0, 1.5]')
        return self

def session(token):
    if not token or token not in sessions: raise HTTPException(409,'Study session expired. Reload the page.')
    s=sessions[token];s['access']=time.monotonic();return s

@app.post('/api/session')
def create_session():
    with lock:
        for key in list(sessions):
            if time.monotonic()-sessions[key]['access']>7200: del sessions[key]
        if len(sessions)>=128: raise HTTPException(503,'Too many active study sessions')
        token=str(uuid.uuid4());sessions[token]={'access':time.monotonic(),'baseline':None,'scenario':None,'baseline_id':None,'net':None}
        return {'study_id':token}

@app.get('/api/facilities')
def facilities(): return FACILITIES

@app.get('/api/model')
def model(): return dict(MODEL,limits=LIMITS)

@app.get('/api/layers/{name}')
def layer(name:Literal['transmission','substations']):
    file='transmission_lines' if name=='transmission' else name
    return FileResponse(ROOT/f'data/processed/{file}.geojson',media_type='application/geo+json')

@app.get('/api/assumptions')
def assumptions():
    return {'text':(ROOT/'docs/ASSUMPTIONS.md').read_text(encoding='utf-8'),'facilities':FACILITIES}

@app.post('/api/run')
def run(request:RunRequest,x_study_id:str|None=Header(default=None)):
    with lock:
        s=session(x_study_id)
        if request.type!='baseline' and (not s['baseline'] or not s['baseline']['converged'] or request.baseline_id!=s['baseline_id']):
            raise HTTPException(409,'Run a valid baseline first; the baseline ID must match this session.')
        if request.type=='baseline':
            s.update(baseline=None,scenario=None,baseline_id=None,net=None)
            net=build_network(MODEL)
            if request.facility_id:
                net=scenarios.load_change(net,request.facility_id,request.p_mw,request.pf,request.onsite_gen_mw,request.bus_id)
        else:
            s['scenario']=None
            if request.type=='fault':
                result=scenarios.fault(request.bus_id);s['scenario']=dict(result,inputs=request.model_dump())
                return {'result':s['scenario'],'baseline':s['baseline'],'baseline_id':s['baseline_id'],'comparison':None}
            if request.type=='load_sweep':
                start=time.perf_counter();points=scenarios.load_sweep(s['net'],request.scale_levels)
                result={'status':'sweep_complete','converged':all(p['result']['converged'] for p in points),'points':points,
                        'runtime_seconds':time.perf_counter()-start,'inputs':request.model_dump()}
                s['scenario']=result
                return {'result':result,'baseline':s['baseline'],'baseline_id':s['baseline_id'],'comparison':None}
            if request.type=='load_change': net=scenarios.load_change(s['net'],request.facility_id,request.p_mw,request.pf,request.onsite_gen_mw,request.bus_id)
            elif request.type=='line_outage': net=scenarios.line_outage(s['net'],request.line_id)
            else: net=scenarios.load_disconnect(s['net'],request.facility_id)
        result=solve(net);result['inputs']=request.model_dump();result['model_name']=MODEL['name']
        if request.type=='baseline':
            s['baseline']=result
            if result['converged']: s['net']=deepcopy(net);s['baseline_id']=str(uuid.uuid4())
        else: s['scenario']=result
        comparison=None
        if request.type!='baseline' and result['converged']:
            comparison={key:{'baseline':value,'scenario':result['totals'].get(key),
                'delta':result['totals'][key]-value if isinstance(value,(int,float)) and isinstance(result['totals'].get(key),(int,float)) else None}
                for key,value in s['baseline']['totals'].items()}
        return {'result':result,'baseline':s['baseline'],'baseline_id':s['baseline_id'],'comparison':comparison}

@app.get('/api/export')
def export(format:Literal['csv','json']='json',x_study_id:str|None=Header(default=None)):
    with lock:
        s=session(x_study_id)
        if not s['baseline']: raise HTTPException(409,'No study to export')
        data={'model':MODEL,'facilities':FACILITIES,'baseline_id':s['baseline_id'],'baseline':s['baseline'],'scenario':s['scenario']}
        if format=='json':
            content=json.dumps(data,indent=2,allow_nan=False);mime='application/json'
        else:
            buf=io.StringIO();writer=csv.writer(buf);writer.writerow(['case','element_type','id','metric','value'])
            for case in ['baseline','scenario']:
                result=s[case]
                if not result: continue
                writer.writerow([case,'status','', 'status',result['status']])
                writer.writerow([case,'inputs','','json',json.dumps(result.get('inputs',{}))])
                for kind in ['buses','lines','loads','transformers']:
                    for eid,values in result.get(kind,{}).items():
                        for key,value in values.items(): writer.writerow([case,kind,eid,key,value])
                for key,value in result.get('totals',{}).items(): writer.writerow([case,'totals','',key,value])
                for point in result.get('points',[]):
                    for key,value in point['result'].get('totals',{}).items(): writer.writerow([case,'sweep',point['scale'],key,value])
            content=buf.getvalue();mime='text/csv'
        return Response(content,media_type=mime,headers={'Content-Disposition':f'attachment; filename="houston-study.{format}"'})

app.mount('/',StaticFiles(directory=ROOT/'app/static',html=True,check_dir=False),name='frontend')
