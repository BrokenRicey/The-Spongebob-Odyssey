"""Build a synthetic meshed network using public substation coordinates as anchors."""
import csv
import json
import math
from scripts.common import ROOT, TODAY, save
from simulation.gridsim.config import LINE_PARAMETERS, TRANSFORMER_PARAMETERS, ROUTING_FACTOR
from simulation.gridsim.catalog import load_facilities

def distance(a,b):
    lat1,lat2=map(math.radians,[a['lat'],b['lat']]);dlat=lat2-lat1;dlon=math.radians(b['lon']-a['lon'])
    return 6371*2*math.asin(min(1,math.sqrt(math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2)))

def main():
    subs=json.loads((ROOT/'data/processed/substations.geojson').read_text(encoding='utf-8'))['features']
    if len(subs)<15: raise ValueError('At least 15 public substation coordinate anchors required')
    candidates=[dict(lon=f['geometry']['coordinates'][0],lat=f['geometry']['coordinates'][1],properties=f['properties']) for f in subs]
    # Spread the coordinate anchors across Houston; proximity is only a layout choice.
    targets=[(29.76,-95.37),(29.85,-95.55),(29.96,-95.45),(30.10,-95.46),(29.92,-95.27),
             (29.79,-95.13),(29.66,-95.20),(29.58,-95.32),(29.66,-95.53),(29.80,-95.72),
             (29.89,-95.67),(30.03,-95.30),(29.72,-95.05),(29.52,-95.48),(29.70,-95.65)]
    chosen=[]
    for lat,lon in targets:
        candidate=min(candidates,key=lambda p:distance(p,{'lat':lat,'lon':lon}));candidates.remove(candidate);chosen.append(candidate)
    meta={'value_status':'estimated','source_url':'docs/ASSUMPTIONS.md','retrieved_date':TODAY}
    buses=[dict(id=f'BUS_{i+1:02}',vn_kv=138,lat=p['lat'],lon=p['lon'],substation_name=p['properties'].get('name','OSM substation'),
                coordinate_source=p['properties']['source_url'],**meta) for i,p in enumerate(chosen)]
    for n,index in enumerate([0,4,9]):
        b=buses[index];buses.append(dict(b,id=f'HV_{n+1:02}',vn_kv=345))
    lines=[]
    # 138 kV ring + selected chords, deliberately representative, not HIFLD connectivity.
    ring=sorted(range(15),key=lambda i:math.atan2(buses[i]['lat']-29.8,buses[i]['lon']+95.4))
    pairs=[(ring[i],ring[(i+1)%15]) for i in range(15)]+[(0,i) for i in [1,3,5,7,9,11,13]]+[(15,16),(16,17),(17,15)]
    for i,(a,b) in enumerate(pairs):
        lines.append(dict(id=f'L{i+1:02}',from_bus=buses[a]['id'],to_bus=buses[b]['id'],
             length_km=max(.1,distance(buses[a],buses[b])*ROUTING_FACTOR),geometry_source_id=None,
             connection_status='representative',**LINE_PARAMETERS,**meta))
    transformers=[dict(id=f'T{i+1:02}',hv_bus=f'HV_{i+1:02}',lv_bus=buses[index]['id'],**TRANSFORMER_PARAMETERS,**meta) for i,index in enumerate([0,4,9])]
    facilities=load_facilities()
    for f in facilities:
        f['connection_bus_id']=min(buses[:15],key=lambda b:distance(f,b))['id']
    # Write only persisted catalog fields; flags are computed on load.
    fields=[k for k in facilities[0] if k!='missing_data_flags']
    with (ROOT/'data/facilities.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(facilities)
    loads=[dict(id=f['id'],bus_id=f['connection_bus_id'],p_mw=f['est_demand_mw'],pf=f['power_factor'],onsite_gen_mw=f['onsite_gen_mw'],**meta) for f in facilities]
    model=dict(name='Houston representative v0.1',buses=buses,lines=lines,transformers=transformers,
        sources=[dict(id='GRID_01',bus_id='HV_01',vm_pu=1.02,**meta)],loads=loads,
        assumptions=['Public substation coordinates only; voltage levels and connectivity are assumed.',
          'No modeled branch is asserted to match a HIFLD route.', 'Facility connections selected for study coverage, not verified utility connections.',
          'Constant PQ loads; onsite generation at unity power factor; no dynamic/fault model.'])
    save('data/model/houston_model.json',model)
    print(f'Model: {len(buses)} buses, {len(lines)} lines, {len(transformers)} transformers, {len(loads)} loads')

if __name__=='__main__': main()
