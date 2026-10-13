"""Houston transmission map from the user's ArcGIS web map. Python 3.10+, no pip installs.
Run: python houston_grid.py
Refresh source data: python houston_grid.py --refresh
Change crop: python houston_grid.py --bbox -95.85 29.45 -94.85 30.08
This is GIS geography, NOT a validated electrical / pandapower network.
"""
import argparse
import csv
import datetime as dt
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import sys
import urllib.parse
import urllib.request
import webbrowser

WEBMAP_ID = '5c72822e6102473f9185fc2a8fe71eb2'
ITEM_URL = f'https://www.arcgis.com/sharing/rest/content/items/{WEBMAP_ID}'
DEFAULT_BBOX = (-95.85, 29.45, -94.85, 30.08)  # west, south, east, north; metro crop, not city limits
COLORS = {'Under 100': '#169ac0', '100-161': '#ff4f60', '220-287': '#a64ab5',
          '345': '#ff9017', '500': '#edce19', '735 and above': '#fa73cf', 'Other': '#999999'}
ROOT = Path(__file__).resolve().parent


def get_json(url, **params):
    query = urllib.parse.urlencode({'f': 'json', **params})
    request = urllib.request.Request(url + '?' + query, headers={'User-Agent': 'HoustonSeniorDesignGIS/1.0'})
    with urllib.request.urlopen(request, timeout=90) as response:
        data = json.load(response)
    if 'error' in data:
        raise RuntimeError(f'ArcGIS error from {url}: {data["error"]}')
    return data


def walk_layers(layers):
    for layer in layers:
        yield layer
        yield from walk_layers(layer.get('layers', []))


def download(bbox):
    webmap = get_json(ITEM_URL + '/data')
    candidates = [x for x in walk_layers(webmap.get('operationalLayers', []))
                  if x.get('url') and 'transmission' in x.get('title', '').lower()]
    if len(candidates) != 1:
        raise RuntimeError('Expected one transmission layer in the supplied map; inspect operationalLayers.')
    url = candidates[0]['url'].rstrip('/')
    metadata = get_json(url)
    if metadata.get('geometryType') != 'esriGeometryPolyline':
        raise RuntimeError('Source is not a polyline layer.')
    envelope = dict(zip(('xmin', 'ymin', 'xmax', 'ymax'), bbox))
    envelope['spatialReference'] = {'wkid': 4326}
    ids = get_json(url + '/query', where='1=1', geometry=json.dumps(envelope),
                   geometryType='esriGeometryEnvelope', inSR=4326,
                   spatialRel='esriSpatialRelIntersects', returnIdsOnly='true').get('objectIds')
    if not ids:
        raise RuntimeError('No lines returned for the requested area.')
    ids = sorted(set(ids))
    records = []
    batch_size = min(200, metadata.get('maxRecordCount', 200))
    for start in range(0, len(ids), batch_size):
        batch = ids[start:start + batch_size]
        print(f'Downloading lines {start + 1}–{start + len(batch)} of {len(ids)} ...', flush=True)
        result = get_json(url + '/query', objectIds=','.join(map(str, batch)), outFields='*',
                          returnGeometry='true', outSR=4326)
        if result.get('exceededTransferLimit') or len(result.get('features', [])) != len(batch):
            raise RuntimeError('Incomplete source response. No partial dataset will be saved; retry refresh.')
        records.extend(result['features'])
    oid = metadata.get('objectIdField') or next(f['name'] for f in metadata['fields'] if f['type'] == 'esriFieldTypeOID')
    if {x['attributes'][oid] for x in records} != set(ids):
        raise RuntimeError('Source IDs do not match requested IDs.')
    return {'bbox': list(bbox), 'retrieved_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
            'webmap_url': f'https://www.arcgis.com/apps/mapviewer/index.html?webmap={WEBMAP_ID}',
            'layer_url': url, 'layer_metadata': metadata, 'webmap': webmap, 'records': records}


def clip_segment(a, b, bbox):
    """Liang–Barsky line clipping in WGS84 coordinates; preserve actual path vertices."""
    x, y = a[:2]
    dx, dy = b[0] - x, b[1] - y
    w, s, e, n = bbox
    lo, hi = 0.0, 1.0
    for p, q in ((-dx, x-w), (dx, e-x), (-dy, y-s), (dy, n-y)):
        if p == 0:
            if q < 0:
                return None
        else:
            r = q / p
            if p < 0:
                lo = max(lo, r)
            else:
                hi = min(hi, r)
            if lo > hi:
                return None
    if lo == hi:
        return None
    return [[x + lo*dx, y + lo*dy], [x + hi*dx, y + hi*dy]]


def clip_path(path, bbox):
    parts, current = [], []
    for a, b in zip(path, path[1:]):
        segment = clip_segment(a, b, bbox)
        if segment:
            if current and all(abs(current[-1][i] - segment[0][i]) < 1e-10 for i in (0, 1)):
                current.append(segment[1])
            else:
                if current:
                    parts.append(current)
                current = segment
        elif current:
            parts.append(current)
            current = []
    if current:
        parts.append(current)
    return parts


def voltage_class(attributes):
    raw = str(attributes.get('VOLT_CLASS') or '').upper().replace(' ', '')
    if 'UNDER100' in raw:
        return 'Under 100'
    for label in ('100-161', '220-287', '345', '500'):
        if raw == label:
            return label
    if '735' in raw:
        return '735 and above'
    try:
        v = float(attributes.get('VOLTAGE'))
    except (ValueError, TypeError):
        return 'Other'
    if 0 < v < 100: return 'Under 100'
    if 100 <= v <= 161: return '100-161'
    if 220 <= v <= 287: return '220-287'
    if v == 345: return '345'
    if v == 500: return '500'
    if v >= 735: return '735 and above'
    return 'Other'


def length_km(parts):
    total = 0.0
    for part in parts:
        for a, b in zip(part, part[1:]):
            lon1, lat1, lon2, lat2 = map(math.radians, [*a, *b])
            h = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
            total += 6371.0088 * 2 * math.asin(min(1, math.sqrt(h)))
    return total


def build_features(cache, bbox):
    features = []
    for record in cache['records']:
        parts = [part for path in (record.get('geometry') or {}).get('paths', []) for part in clip_path(path, bbox)]
        if not parts:
            continue
        props = dict(record['attributes'])
        props['display_class'] = voltage_class(props)
        props['clipped_route_km'] = round(length_km(parts), 4)
        props['boundary_cut'] = any(not (bbox[0] <= p[0] <= bbox[2] and bbox[1] <= p[1] <= bbox[3])
                                    for path in record['geometry']['paths'] for p in path)
        features.append({'type': 'Feature', 'properties': props,
                         'geometry': {'type': 'MultiLineString', 'coordinates': parts}})
    return {'type': 'FeatureCollection', 'features': features}


PAGE = '''<!doctype html><html><head><meta charset="utf-8"><meta name="referrer" content="strict-origin-when-cross-origin"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Houston | Transmission Grid</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>body{margin:0;font:14px system-ui;color:#172a3b}#map{height:100vh;background:#eef3f6}.panel{position:absolute;left:18px;top:18px;width:260px;z-index:1000;background:#fff;max-height:calc(100vh - 80px);overflow:auto;padding:22px;border-radius:14px;box-shadow:0 4px 25px #1233}h1{font-size:25px;margin:7px 0}small{color:#587080}.tag{letter-spacing:2px;font-size:10px;color:#008c87;font-weight:800}.row{margin:12px 0;display:flex;align-items:center;gap:8px}.line{width:28px;height:3px;display:inline-block}p{line-height:1.5}button{padding:8px 12px;cursor:pointer;background:#123747;color:white;border:0;border-radius:6px}hr{border:0;border-top:1px solid #dde5ea;margin:18px 0}#error{color:#a32}.leaflet-popup-content{max-height:300px;overflow:auto}td{padding:4px;border-bottom:1px solid #eee}@media(max-width:650px){.panel{width:190px;padding:12px;font-size:12px}h1{font-size:20px}}</style></head><body>
<div id="map"></div><aside class="panel"><div class="tag">SENIOR DESIGN · GIS FOUNDATION</div><h1>Houston grid</h1><small>Transmission routes • study-area crop</small><p><b>__COUNT__</b> source features within the boundary.</p><label class="row"><input type="checkbox" id="streets"> Street background</label><div id="legend"></div><button onclick="map.fitBounds(bounds)">Reset view</button><hr><small>Click a line for voltage, owner and source substation names. Toggle voltage classes above.<p>Rectangle approximates the Houston area in the reference image; it is not the municipal boundary.</p><b>Geographic map only.</b> Crossings are not assumed connected. No power-flow results are represented.<p>Source: supplied ArcGIS map / EIA transmission layer.<br>Retrieved: __DATE__</p><div id="error"></div></small></aside>
<script>
const data=__DATA__,colors=__COLORS__,bbox=__BBOX__;
const bounds=[[bbox[1],bbox[0]],[bbox[3],bbox[2]]];
if(typeof L==='undefined'){document.getElementById('error').textContent='Map library could not load. Connect to the internet or open houston_grid.svg for an offline view.';throw Error('Leaflet unavailable');}
const map=L.map('map',{zoomControl:false,preferCanvas:true}).fitBounds(bounds);
L.control.zoom({position:'bottomright'}).addTo(map);
const streets=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{
 maxZoom:19,referrerPolicy:'strict-origin-when-cross-origin',
 attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a> | Transmission data: EIA / ArcGIS'});
const streetToggle=document.getElementById('streets');
streetToggle.checked=location.protocol==='http:'||location.protocol==='https:';
if(streetToggle.checked) streets.addTo(map);
else document.getElementById('error').textContent='Street background is off for local-file viewing. Run houston_grid.py to open the local web address.';
streetToggle.onchange=()=>{
 if(streetToggle.checked && location.protocol==='file:'){
  streetToggle.checked=false;document.getElementById('error').textContent='Run houston_grid.py first; street tiles require a web address.';return;
 }
 if(streetToggle.checked){document.getElementById('error').textContent='';streets.addTo(map);}
 else map.removeLayer(streets);
};
streets.on('tileerror',()=>{
 map.removeLayer(streets);streetToggle.checked=false;
 document.getElementById('error').textContent='Street tiles unavailable. Grid lines and city labels remain usable. You can retry with Street background.';
});
for(const [name,lat,lon] of [['Houston',29.7604,-95.3698],['Sugar Land',29.6197,-95.6349],['Baytown',29.7355,-94.9774],['Pearland',29.5636,-95.286],['Cypress',29.9691,-95.6972],['Humble',29.9988,-95.2622]]){
 if(lon>=bbox[0]&&lon<=bbox[2]&&lat>=bbox[1]&&lat<=bbox[3])
 L.circleMarker([lat,lon],{radius:3,color:'#173648',fillOpacity:1}).addTo(map).bindTooltip(name,{permanent:true,direction:'top'});
}

L.rectangle(bounds,{color:'#234758',weight:1,dashArray:'6 6',fill:false,interactive:false}).addTo(map);
function esc(x){return String(x??'Not provided').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
for(const [label,color] of Object.entries(colors)){
 const features=data.features.filter(f=>f.properties.display_class===label);
 const layer=L.geoJSON(features,{style:()=>({color,weight:label==='345'?3:2,opacity:.9}),onEachFeature:(f,l)=>{
 const p=f.properties;let rows=['ID','OWNER','VOLTAGE','VOLT_CLASS','STATUS','TYPE','SUB_1','SUB_2','clipped_route_km','boundary_cut'].map(k=>'<tr><td>'+esc(k)+'</td><td>'+esc(p[k])+'</td></tr>').join('');
 l.bindPopup('<b>Transmission line</b><table>'+rows+'</table><p>SUB_1 / SUB_2 refer to the full source line, including parts outside this crop. Cut endpoints are not substations.</p>');
 l.on('mouseover',()=>l.setStyle({weight:5}));l.on('mouseout',()=>layer.resetStyle(l));}}).addTo(map);
 const row=document.createElement('label');row.className='row';const input=document.createElement('input');input.type='checkbox';input.checked=true;input.onchange=()=>input.checked?layer.addTo(map):map.removeLayer(layer);row.appendChild(input);
 const swatch=document.createElement('span');swatch.className='line';swatch.style.background=color;row.appendChild(swatch);row.appendChild(document.createTextNode(label+(label==='Other'?'':' kV')+' ('+features.length+')'));document.getElementById('legend').appendChild(row);
}
</script></body></html>'''


def write_svg(data, bbox, destination):
    """Offline vector preview; approximate local longitude/latitude projection."""
    w, s, e, n = bbox
    width, height = 1400, 1000
    scale = min(1280/((e-w)*math.cos(math.radians((s+n)/2))), 750/(n-s))
    def xy(point):
        return (60+(point[0]-w)*math.cos(math.radians((s+n)/2))*scale, 160+(n-point[1])*scale)
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
           '<rect width="100%" height="100%" fill="#f4f7fa"/>',
           '<g font-family="Arial" fill="#173648"><text x="60" y="60" font-size="32" font-weight="bold">Houston transmission grid</text>',
           f'<text x="60" y="90" font-size="16">{len(data["features"])} source features · Houston-area rectangle · Geographic routes only</text></g>']
    x = 60
    for label, color in COLORS.items():
        svg.append(f'<path d="M{x} 120 h22" stroke="{color}" stroke-width="4"/><text x="{x+28}" y="125" font-family="Arial" font-size="13">{html.escape(label)}</text>')
        x += 177
    for f in data['features']:
        for part in f['geometry']['coordinates']:
            points = ' '.join(f'{x:.2f},{y:.2f}' for x,y in map(xy, part))
            svg.append(f'<polyline points="{points}" fill="none" stroke="{COLORS[f["properties"]["display_class"]]}" stroke-width="1.6"/>')
    for name, lon, lat in [('Houston',-95.3698,29.7604),('Sugar Land',-95.6349,29.6197),('Baytown',-94.9774,29.7355),('Pearland',-95.286,29.5636),('Cypress',-95.6972,29.9691),('Humble',-95.2622,29.9988)]:
        if w<=lon<=e and s<=lat<=n:
            x,y=xy([lon,lat]);svg.append(f'<circle cx="{x}" cy="{y}" r="3" fill="#153547"/><text x="{x+6}" y="{y-6}" font-family="Arial" font-size="14" fill="#173648" stroke="#f4f7fa" stroke-width="3" paint-order="stroke">{name}</text>')
    svg.append('<text x="60" y="970" font-family="Arial" font-size="14" fill="#587080">Source: supplied ArcGIS web map / EIA layer. Line crossings do not establish electrical connectivity.</text></svg>')
    destination.write_text('\n'.join(svg), encoding='utf-8')



def serve_map(output, open_browser=True):
    """Serve only the generated HTML on loopback, so the browser sends a real referrer."""
    payload = output.read_bytes()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if urllib.parse.urlsplit(self.path).path not in ('/', '/houston_grid.html'):
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
            self.end_headers()
            self.wfile.write(payload)
        def log_message(self, *args):
            pass
    with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
        address = f'http://127.0.0.1:{server.server_port}/houston_grid.html'
        print(f'Open this address: {address}\nKeep Python running while using the map. Ctrl+C or PyCharm Stop closes the server.', flush=True)
        if open_browser:
            webbrowser.open(address)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bbox', type=float, nargs=4, default=DEFAULT_BBOX, metavar=('WEST','SOUTH','EAST','NORTH'))
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    bbox = args.bbox
    w,s,e,n = bbox
    if not all(math.isfinite(v) for v in bbox) or not (-180<=w<e<=180 and -90<s<n<90):
        parser.error('Invalid longitude/latitude bounding box.')
    cache_file = ROOT / 'source_cache.json'
    cache = json.loads(cache_file.read_text(encoding='utf-8')) if cache_file.exists() and not args.refresh else None
    if cache is None or cache.get('bbox') != list(bbox):
        cache = download(bbox)
        temp = cache_file.with_suffix('.tmp')
        temp.write_text(json.dumps(cache), encoding='utf-8')
        temp.replace(cache_file)
    data = build_features(cache, bbox)
    if not data['features']:
        raise RuntimeError('No line geometry remains after clipping.')
    (ROOT / 'houston_lines.geojson').write_text(json.dumps(data), encoding='utf-8')
    fields = list(dict.fromkeys(k for f in data['features'] for k in f['properties']))
    with (ROOT / 'houston_lines.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fields);writer.writeheader()
        for f in data['features']:
            writer.writerow(f['properties'])
    page = PAGE.replace('__COUNT__',str(len(data['features']))).replace('__DATE__',html.escape(cache['retrieved_utc'][:10]))
    page = page.replace('__DATA__',json.dumps(data).replace('<','\\u003c')).replace('__COLORS__',json.dumps(COLORS)).replace('__BBOX__',json.dumps(bbox))
    output = ROOT / 'houston_grid.html'
    output.write_text(page, encoding='utf-8')
    write_svg(data, bbox, ROOT / 'houston_grid.svg')
    print(f'Saved {len(data["features"])} clipped features.\nMap: {output}\nOffline view: {ROOT / "houston_grid.svg"}')
    if not args.no_browser:
        serve_map(output)

if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'Could not build map: {exc}\nKeep any existing cache. Check internet access or retry with --refresh.', file=sys.stderr)
        sys.exit(1)
