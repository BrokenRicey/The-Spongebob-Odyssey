"""Fetch mapped infrastructure only; no connectivity inferred from geometry."""
import csv
import argparse
import requests
from scripts.common import ROOT, BBOX, TODAY, save, clean

ENDPOINTS = ['https://overpass.private.coffee/api/interpreter', 'https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter']

def main(placeholders_only=False):
    west,south,east,north=BBOX
    area=f'({south},{west},{north},{east})'
    query='[out:json][timeout:90];('+''.join(f'nwr[{tag}]{area};' for tag in
          ['power=line','power=substation','telecom=data_center','building=data_center'])+');out center geom;'
    errors=[]
    for endpoint in ([] if placeholders_only else ENDPOINTS):
        try:
            response=requests.get(endpoint,params={'data':query},timeout=110)
            response.raise_for_status()
            raw=response.json()
            if raw.get('remark'):
                raise RuntimeError(raw['remark'])
            break
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            errors.append(str(exc))
    else:
        if not placeholders_only:
            raise RuntimeError('Overpass unavailable: '+'; '.join(errors))
        raw={'elements':[]};endpoint='docs/ASSUMPTIONS.md'
    if not placeholders_only: save('data/raw/osm.json',raw)
    layers={'substations':[], 'osm_transmission':[], 'osm_facilities':[]}
    facilities=[]
    for e in raw['elements']:
        tags=e.get('tags',{})
        source=f"https://www.openstreetmap.org/{e['type']}/{e['id']}"
        pos=e.get('center',e)
        if 'lat' not in pos:
            continue
        properties=dict(tags,id=f"osm_{e['type']}_{e['id']}",source_url=source)
        geom={'type':'Point','coordinates':[pos['lon'],pos['lat']]}
        key=None
        if tags.get('power')=='line' and e.get('geometry'):
            coords=[[p['lon'],p['lat']] for p in e['geometry'] if 'lon' in p]
            if len(coords)<2: continue
            geom={'type':'LineString','coordinates':coords}; key='osm_transmission'
        elif tags.get('power')=='substation': key='substations'
        elif tags.get('telecom')=='data_center' or tags.get('building')=='data_center':
            key='osm_facilities'
            facilities.append(dict(id=f'DC_{len(facilities)+1:02}',name=tags.get('name',f'OSM data center {e["id"]}'),
                operator=tags.get('operator','Unknown'),lat=pos['lat'],lon=pos['lon'],est_demand_mw=30,
                demand_status='estimated',onsite_gen_mw=0,power_factor=.95,connection_bus_id='',connection_status='assumed',
                source_url=source,retrieved_date=TODAY,notes='OSM location; demand 30 MW and PF 0.95 are study assumptions; onsite generation unknown, assumed inactive.',placeholder=False))
        if key: layers[key].append({'type':'Feature','geometry':geom,'properties':properties})
    for key,features in layers.items():
        if placeholders_only and key=='substations': continue
        output=clean(features,endpoint,'© OpenStreetMap contributors, ODbL 1.0')
        save(f'data/processed/{key}.geojson',output)
    if not (ROOT/'data/processed/transmission_lines.geojson').exists():
        save('data/processed/transmission_lines.geojson',clean(layers['osm_transmission'],endpoint,'© OpenStreetMap contributors, ODbL 1.0'))
    # Placeholder positions and operating points are explicitly synthetic, never real facilities.
    points=[(29.76,-95.37),(29.85,-95.55),(29.96,-95.45),(30.10,-95.46),(29.92,-95.27),
            (29.79,-95.13),(29.66,-95.20),(29.58,-95.32),(29.66,-95.53),(29.80,-95.72)]
    while len(facilities)<10:
        i=len(facilities); lat,lon=points[i]
        facilities.append(dict(id=f'DC_{i+1:02}',name=f'Placeholder facility {i+1:02}',operator='Not a verified site',
            lat=lat,lon=lon,est_demand_mw=30,demand_status='estimated',onsite_gen_mw=0,power_factor=.95,
            connection_bus_id='',connection_status='assumed',source_url='docs/ASSUMPTIONS.md',retrieved_date=TODAY,
            notes='Synthetic facility and location for study coverage. 30 MW, PF .95, onsite generation 0 are assumptions.',placeholder=True))
    path=ROOT/'data/facilities.csv'
    with path.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(facilities[0]));writer.writeheader();writer.writerows(facilities)
    print({key:len(value) for key,value in layers.items()})
    print(f'Catalog: {len(facilities)} facilities; {sum(f["placeholder"] for f in facilities)} placeholders')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--placeholders-only',action='store_true')
    main(parser.parse_args().placeholders_only)
