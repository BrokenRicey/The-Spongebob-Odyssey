import json
from pathlib import Path
from datetime import datetime, timezone
from shapely.geometry import shape, box, mapping

ROOT = Path(__file__).resolve().parents[1]
BBOX = (-96.0, 29.3, -94.8, 30.3)
TODAY = datetime.now(timezone.utc).date().isoformat()

def save(path, value):
    path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')

def collection(features):
    return {'type': 'FeatureCollection', 'features': features}

def clean(features, source, license_name):
    output = []
    for f in features:
        if not f.get('geometry'):
            continue
        g = shape(f['geometry']).intersection(box(*BBOX))
        if g.is_empty:
            continue
        f = dict(f, geometry=mapping(g))
        f['properties'] = dict(f.get('properties') or {}, source_url=(f.get('properties') or {}).get('source_url',source),
                               retrieved_date=TODAY, value_status='reported', attribution=license_name)
        output.append(f)
    return collection(output)
