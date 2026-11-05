"""ArcGIS public substation fallback when Overpass is unavailable."""
import requests
from scripts.common import BBOX, save, clean

URL='https://services.arcgis.com/XG15cJAlne2vxtgt/ArcGIS/rest/services/Electric_Substations/FeatureServer/0'

def main():
    meta=requests.get(URL,params={'f':'json'},timeout=30).json()
    if 'error' in meta: raise RuntimeError(meta['error'])
    save('data/raw/substation_metadata.json',meta)
    offset=0;features=[]
    while True:
        r=requests.get(URL+'/query',params=dict(where='1=1',geometry=','.join(map(str,BBOX)),
             geometryType='esriGeometryEnvelope',inSR=4326,outSR=4326,f='geojson',outFields='*',
             orderByFields=meta['objectIdField'],resultRecordCount=1000,resultOffset=offset),timeout=60)
        r.raise_for_status();page=r.json()
        if 'error' in page: raise RuntimeError(page['error'])
        save(f'data/raw/substation_page_{offset}.json',page)
        features.extend(page['features'])
        if len(page['features'])<1000: break
        offset+=1000
    for f in features:
        f['properties']['name']=f['properties'].get('NAME','Unnamed substation')
    save('data/processed/substations.geojson',clean(features,URL,'Public ArcGIS Electric_Substations layer; see metadata'))
    print(f'ArcGIS substations: {len(features)}')

if __name__=='__main__': main()
