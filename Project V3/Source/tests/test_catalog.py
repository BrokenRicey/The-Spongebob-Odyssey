import csv
from pathlib import Path
import pytest
from simulation.gridsim.catalog import load_facilities

ROOT=Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('field,value',[('lat','95'),('lon','-190'),('est_demand_mw','-1'),('onsite_gen_mw','-1'),('power_factor','0'),('power_factor','1.1'),('source_url',''),('retrieved_date',''),('est_demand_mw','nan')])
def test_catalog_rejects_invalid_records(tmp_path,field,value):
    with (ROOT/'data/facilities.csv').open(encoding='utf-8') as f: rows=list(csv.DictReader(f))
    rows[0][field]=value
    path=tmp_path/'facilities.csv'
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    with pytest.raises(ValueError):load_facilities(path)

def test_duplicate_id(tmp_path):
    with (ROOT/'data/facilities.csv').open(encoding='utf-8') as f: rows=list(csv.DictReader(f))
    rows[1]['id']=rows[0]['id']
    path=tmp_path/'facilities.csv'
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    with pytest.raises(ValueError):load_facilities(path)
