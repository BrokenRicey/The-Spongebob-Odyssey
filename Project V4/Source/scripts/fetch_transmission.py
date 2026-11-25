"""Download every intersecting ArcGIS record, preserving raw pages."""
import requests
from scripts.common import BBOX, save, clean

URL = 'https://services.arcgis.com/XG15cJAlne2vxtgt/ArcGIS/rest/services/FEMA_Region_6_Electric_Power_Transmission_Lines/FeatureServer/0'

def main():
    meta = requests.get(URL, params={'f': 'json'}, timeout=45).json()
    if 'error' in meta:
        raise RuntimeError(meta['error'])
    save('data/raw/transmission_metadata.json', meta)
    fields = {f['name'] for f in meta['fields']}
    wanted = ['ID','OWNER','VOLTAGE','VOLT_CLASS','STATUS','SUB_1','SUB_2','SOURCEDATE']
    oid = meta['objectIdField']
    params = dict(where='1=1', geometry=','.join(map(str, BBOX)), geometryType='esriGeometryEnvelope',
                  inSR=4326, outSR=4326, spatialRel='esriSpatialRelIntersects', f='geojson',
                  outFields=','.join([oid] + [f for f in wanted if f in fields]),
                  orderByFields=oid, resultRecordCount=min(2000, meta.get('maxRecordCount', 2000)))
    features, offset = [], 0
    while True:
        response = requests.get(URL+'/query', params=dict(params, resultOffset=offset), timeout=90)
        response.raise_for_status()
        page = response.json()
        if 'error' in page:
            raise RuntimeError(page['error'])
        save(f'data/raw/transmission_page_{offset}.json', page)
        batch = page['features']
        features.extend(batch)
        if not batch or (len(batch) < params['resultRecordCount'] and not page.get('exceededTransferLimit')):
            break
        offset += len(batch)
    save('data/processed/transmission_lines.geojson', clean(features, URL, 'HIFLD / FEMA Region 6 public layer; see source metadata'))
    names = sorted({f['properties'][key] for f in features for key in ('SUB_1','SUB_2') if f['properties'].get(key)})
    save('data/processed/substation_candidates.json', names)
    print(f'ArcGIS transmission: {len(features)} features, {len(names)} candidate substation names')

if __name__ == '__main__':
    main()
