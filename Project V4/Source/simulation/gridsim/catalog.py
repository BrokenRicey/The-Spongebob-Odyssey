import csv
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def load_facilities(path=None):
    with Path(path or ROOT/'data/facilities.csv').open(encoding='utf-8') as f:
        rows=list(csv.DictReader(f))
    seen=set()
    for row in rows:
        if not row['id'] or row['id'] in seen:
            raise ValueError('Missing or duplicate facility ID')
        seen.add(row['id'])
        for field in ['lat','lon','est_demand_mw','onsite_gen_mw','power_factor']:
            try: row[field]=float(row[field])
            except (ValueError,TypeError): raise ValueError(f'{row["id"]}: missing/invalid {field}')
            if not math.isfinite(row[field]): raise ValueError(f'Nonfinite {field}')
        if not -90<=row['lat']<=90 or not -180<=row['lon']<=180: raise ValueError('Invalid coordinates')
        if min(row['est_demand_mw'],row['onsite_gen_mw'])<0: raise ValueError('Negative MW')
        if not 0<row['power_factor']<=1: raise ValueError('Power factor outside (0, 1]')
        if not row['source_url'] or not row['retrieved_date']: raise ValueError('Missing provenance')
        if row['demand_status'] not in ('reported','estimated') or row['connection_status'] not in ('assumed','confirmed'):
            raise ValueError('Invalid provenance status')
        row['placeholder']=str(row.get('placeholder','')).lower()=='true'
        row['missing_data_flags']=['Demand not measured','Connection unverified','Onsite generation availability unknown']
        if row['placeholder']: row['missing_data_flags'].append('Synthetic facility/location')
    return rows
