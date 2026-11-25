"""Project V4 editable network and independent baseline/scenario snapshots.

All added equipment is hypothetical. A data center is a load referred to the
connection bus voltage, assuming an ideal, adequately rated site interface.
This does not model the site's internal transformer losses or limitations.
"""
import json
import math
from copy import deepcopy
from pathlib import Path

from simulation.gridsim.config import LINE_PARAMETERS, TRANSFORMER_PARAMETERS
from simulation.gridsim.network import build_network
from simulation.gridsim.results import solve

SECTIONS = ('buses', 'lines', 'transformers', 'loads', 'sources')
INTERFACE_ASSUMPTION = ('Hypothetical data center; ideal, adequately rated site '
                        'transformers and interface equipment assumed. Demand is '
                        'referred to the connection bus; internal losses are omitted.')
MAX_PROJECT_BYTES = 30_000_000


def _number(value, label, low=None, high=None, positive=False):
    try:
        finite = math.isfinite(value)
    except (TypeError, OverflowError):
        finite = False
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not finite:
        raise ValueError(f'{label} must be a finite number.')
    if positive and value <= 0 or low is not None and value < low or high is not None and value > high:
        raise ValueError(f'{label} is outside its supported range.')
    return float(value)


def _validate_json_tree(model):
    """Also validate retained provenance/metadata before it reaches the UI or disk."""
    pending = [(model, 0)]
    count = 0
    while pending:
        value, depth = pending.pop()
        count += 1
        if depth > 64 or count > 2_000_000:
            raise ValueError('Project data is too large or too deeply nested.')
        if value is None or isinstance(value, (str, bool)):
            continue
        if isinstance(value, (int, float)):
            _number(value, 'Project numeric value')
        elif isinstance(value, dict):
            if any(not isinstance(key, str) for key in value):
                raise ValueError('Project object keys must be strings.')
            pending.extend((item, depth+1) for item in value.values())
        elif isinstance(value, (list, tuple)):
            pending.extend((item, depth+1) for item in value)
        else:
            raise ValueError('Project contains a value that cannot be saved as JSON.')


def _position(lat, lon):
    return (_number(lat, 'Latitude', -85, 85), _number(lon, 'Longitude', -180, 180))


def _row(model, section, key):
    for row in model.get(section, []):
        if row['id'] == key:
            return row
    raise ValueError(f'Unknown {section} component: {key}')


def _id(model, section, prefix, requested=None):
    used = {r['id'] for r in model.get(section, [])}
    if requested is not None:
        if not isinstance(requested, str) or not requested.strip() or len(requested) > 128:
            raise ValueError('A name of 1–128 characters is required.')
        if requested.strip() in used:
            raise ValueError(f'Duplicate {section} ID: {requested.strip()}')
        return requested.strip()
    index = 1
    while f'{prefix}_{index:03d}' in used:
        index += 1
    return f'{prefix}_{index:03d}'


def validate_model(model):
    """Validate arbitrary topology; connectivity/islanding is a solver outcome."""
    if not isinstance(model, dict):
        raise ValueError('The network must be an object.')
    _validate_json_tree(model)
    for section in SECTIONS:
        rows = model.get(section, [])
        if not isinstance(rows, list) or len(rows) > 10000:
            raise ValueError(f'{section} must contain no more than 10,000 components.')
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(f'Invalid {section} component.')
            key = row.get('id')
            if not isinstance(key, str) or not key.strip() or len(key) > 128 or key in seen:
                raise ValueError(f'Missing or duplicate {section} ID.')
            seen.add(key)
            if not isinstance(row.get('in_service', True), bool):
                raise ValueError('Equipment state must be true or false.')
    buses = {b['id']: b for b in model.get('buses', [])}
    if not buses:
        raise ValueError('The network needs at least one bus.')

    def bus(key):
        if key not in buses:
            raise ValueError(f'Unknown connection bus: {key}')
        return buses[key]

    for b in buses.values():
        _number(b.get('vn_kv'), 'Bus voltage', high=1200, positive=True)
        _position(b.get('lat'), b.get('lon'))
    for line in model.get('lines', []):
        a, b = bus(line.get('from_bus')), bus(line.get('to_bus'))
        if a['id'] == b['id']:
            raise ValueError('A transmission line needs two different buses.')
        if a['vn_kv'] != b['vn_kv']:
            raise ValueError('Different bus voltages require a transformer.')
        _number(line.get('length_km'), 'Line length', positive=True)
        for key, default in LINE_PARAMETERS.items():
            _number(line.get(key, default), key, low=0, positive=key == 'max_i_ka')
        if line.get('r_ohm_per_km', LINE_PARAMETERS['r_ohm_per_km']) == 0 and line.get('x_ohm_per_km', LINE_PARAMETERS['x_ohm_per_km']) == 0:
            raise ValueError('A transmission line must have nonzero impedance.')
        if 'points' in line:
            if not isinstance(line['points'], list) or not 2 <= len(line['points']) <= 10000:
                raise ValueError('A line route needs at least two coordinate pairs.')
            for point in line['points']:
                if not isinstance(point, (list, tuple)) or len(point) != 2:
                    raise ValueError('Line coordinates use [latitude, longitude].')
                _position(*point)
    for t in model.get('transformers', []):
        a, b = bus(t.get('hv_bus')), bus(t.get('lv_bus'))
        if a['id'] == b['id'] or a['vn_kv'] < b['vn_kv']:
            raise ValueError('Transformer buses must have descending voltage levels.')
        for key in ('sn_mva', 'vn_hv_kv', 'vn_lv_kv', 'vk_percent'):
            _number(t.get(key), key, positive=True)
        for key in ('vkr_percent', 'pfe_kw', 'i0_percent'):
            _number(t.get(key), key, low=0)
        _number(t.get('shift_degree', 0), 'Transformer phase shift')
        if t['vkr_percent'] > t['vk_percent']:
            raise ValueError('Transformer resistance cannot exceed its impedance.')
        if t['vn_hv_kv'] != a['vn_kv'] or t['vn_lv_kv'] != b['vn_kv']:
            raise ValueError('Transformer voltages must match the connected buses.')
    for load in model.get('loads', []):
        bus(load.get('bus_id'))
        _number(load.get('p_mw'), 'Demand', 0, 10000)
        _number(load.get('pf'), 'Power factor', .01, 1)
        _number(load.get('onsite_gen_mw', 0), 'Onsite generation', 0, 10000)
        if 'lat' in load or 'lon' in load:
            _position(load.get('lat'), load.get('lon'))
    for source in model.get('sources', []):
        bus(source.get('bus_id'))
        _number(source.get('vm_pu', 1), 'Source voltage', .5, 1.5)
    return model


def run_model(model):
    validate_model(model)
    return solve(build_network(model))


def distance_km(a, b):
    """Local geographic distance used for assumed routes, not surveyed lengths."""
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    return 6371.0088 * math.hypot(lat2-lat1, (lon2-lon1)*math.cos((lat1+lat2)/2))


def line_points(model, line):
    a, b = _row(model, 'buses', line['from_bus']), _row(model, 'buses', line['to_bus'])
    points = deepcopy(line.get('points', [[a['lat'], a['lon']], [b['lat'], b['lon']]]))
    points[0], points[-1] = [a['lat'], a['lon']], [b['lat'], b['lon']]
    return points


def nearest_connection(model, lat, lon):
    """Find nearest bus or line, including disabled equipment; never reroute silently."""
    lat, lon = _position(lat, lon)
    best = None
    for bus in model['buses']:
        d = distance_km((lat, lon), (bus['lat'], bus['lon']))
        if best is None or d < best['distance_km']:
            best = dict(kind='buses', id=bus['id'], point={'lat': bus['lat'], 'lon': bus['lon']}, distance_km=d, fraction=0)
    scale = max(.01, math.cos(math.radians(lat)))
    for line in model.get('lines', []):
        points = line_points(model, line)
        lengths = [distance_km(a, b) for a, b in zip(points, points[1:])]
        total, walked = sum(lengths), 0
        for index, (a, b, length) in enumerate(zip(points, points[1:], lengths)):
            dx, dy = (b[1]-a[1])*scale, b[0]-a[0]
            den = dx*dx+dy*dy
            t = max(0, min(1, ((lon-a[1])*scale*dx+(lat-a[0])*dy)/den)) if den else 0
            point = {'lat': a[0]+t*(b[0]-a[0]), 'lon': a[1]+t*(b[1]-a[1])}
            fraction = (walked+t*length)/total if total else 0
            d = distance_km((lat, lon), (point['lat'], point['lon']))
            if 1e-6 < fraction < 1-1e-6 and (best is None or d < best['distance_km']-1e-9):
                best = dict(kind='lines', id=line['id'], point=point, distance_km=d, fraction=fraction, segment=index)
            walked += length
    if best is None:
        raise ValueError('Create a bus before placing a data center.')
    return best


def add_bus(model, lat, lon, vn_kv=138, name=None):
    lat, lon = _position(lat, lon)
    _number(vn_kv, 'Bus voltage', high=1200, positive=True)
    row = dict(id=_id(model, 'buses', 'BUS', name), lat=lat, lon=lon, vn_kv=vn_kv, in_service=True, value_status='assumed')
    model.setdefault('buses', []).append(row)
    return row


def add_line(model, from_bus, to_bus, name=None):
    a, b = _row(model, 'buses', from_bus), _row(model, 'buses', to_bus)
    if from_bus == to_bus:
        raise ValueError('Choose two different buses.')
    if a['vn_kv'] != b['vn_kv']:
        high, low = sorted((a, b), key=lambda bus: bus['vn_kv'], reverse=True)
        row = dict(TRANSFORMER_PARAMETERS, id=_id(model, 'transformers', 'T', name), hv_bus=high['id'], lv_bus=low['id'],
                   vn_hv_kv=high['vn_kv'], vn_lv_kv=low['vn_kv'], in_service=True, value_status='assumed')
        model.setdefault('transformers', []).append(row)
    else:
        row = dict(LINE_PARAMETERS, id=_id(model, 'lines', 'L', name), from_bus=from_bus, to_bus=to_bus,
                   length_km=max(.001, distance_km((a['lat'], a['lon']), (b['lat'], b['lon']))), in_service=True, value_status='assumed')
        model.setdefault('lines', []).append(row)
    return row


def add_datacenter(model, name, lat, lon, p_mw, pf=.95, onsite_gen_mw=0):
    lat, lon = _position(lat, lon)
    key = _id(model, 'loads', 'DC', name)
    _number(p_mw, 'Demand', 0, 10000)
    _number(pf, 'Power factor', .01, 1)
    _number(onsite_gen_mw, 'Onsite generation', 0, 10000)
    connection = nearest_connection(model, lat, lon)
    bus_id = connection['id']
    if connection['kind'] == 'lines':
        line = _row(model, 'lines', connection['id'])
        points = line_points(model, line)
        original_to, length = line['to_bus'], line['length_km']
        a = _row(model, 'buses', line['from_bus'])
        tap = add_bus(model, connection['point']['lat'], connection['point']['lon'], a['vn_kv'])
        tap['connection_assumption'] = 'Hypothetical tap on a modeled transmission line.'
        tap['parent_line_id'] = line.get('parent_id', line['id'])
        bus_id = tap['id']
        second = deepcopy(line)
        second['id'] = _id(model, 'lines', 'L')
        second.update(from_bus=bus_id, to_bus=original_to, length_km=length*(1-connection['fraction']), parent_id=tap['parent_line_id'])
        cut = [tap['lat'], tap['lon']]
        line.update(to_bus=bus_id, length_km=length*connection['fraction'], parent_id=tap['parent_line_id'])
        line['points'] = points[:connection['segment']+1]+[cut]
        second['points'] = [cut]+points[connection['segment']+1:]
        model['lines'].append(second)
    row = dict(id=key, bus_id=bus_id, lat=lat, lon=lon, p_mw=p_mw, pf=pf, onsite_gen_mw=onsite_gen_mw,
               in_service=True, connection_assumption=INTERFACE_ASSUMPTION)
    model.setdefault('loads', []).append(row)
    return row


def move_bus(model, key, lat, lon):
    lat, lon = _position(lat, lon)
    bus = _row(model, 'buses', key)
    connected = [(line, line_points(model, line)) for line in model.get('lines', []) if key in (line['from_bus'], line['to_bus'])]
    bus.update(lat=lat, lon=lon)
    for line, points in connected:
        previous = sum(distance_km(a, b) for a, b in zip(points, points[1:]))
        line['points'] = line_points(model, line)
        current = sum(distance_km(a, b) for a, b in zip(line['points'], line['points'][1:]))
        line['length_km'] = max(.001, line['length_km']*current/previous if previous else current)
    return bus


def move_datacenter(model, key, lat, lon):
    """Move and reconnect a site; prior tap buses remain harmless route junctions."""
    candidate = deepcopy(model)
    old = _row(candidate, 'loads', key)
    candidate['loads'].remove(old)
    row = add_datacenter(candidate, key, lat, lon, old['p_mw'], old['pf'], old.get('onsite_gen_mw', 0))
    row['in_service'] = old.get('in_service', True)
    validate_model(candidate)
    model.clear()
    model.update(candidate)
    return row


def reconnect_line(model, key, from_bus, to_bus):
    line = _row(model, 'lines', key)
    a, b = _row(model, 'buses', from_bus), _row(model, 'buses', to_bus)
    if from_bus == to_bus or a['vn_kv'] != b['vn_kv']:
        raise ValueError('Connect two different buses at the same voltage, or add a transformer.')
    line.update(from_bus=from_bus, to_bus=to_bus, length_km=max(.001, distance_km((a['lat'], a['lon']), (b['lat'], b['lon']))))
    line.pop('points', None)
    return line


def toggle_component(model, section, key, in_service=None):
    if section not in SECTIONS:
        raise ValueError('Unsupported component type.')
    row = _row(model, section, key)
    if in_service is not None and not isinstance(in_service, bool):
        raise ValueError('Equipment state must be true or false.')
    row['in_service'] = not row.get('in_service', True) if in_service is None else in_service
    return row


class EditorStudy:
    """Independent editable cases; history records atomic validated model changes."""
    def __init__(self, model):
        validate_model(model)
        self.baseline_model = deepcopy(model)
        self.scenario_model = deepcopy(model)
        self.baseline = self.scenario = None
        self._undo = {'baseline': [], 'scenario': []}
        self._redo = {'baseline': [], 'scenario': []}

    def model(self, case):
        if case not in ('baseline', 'scenario'):
            raise ValueError('Choose baseline or scenario.')
        return getattr(self, case+'_model')

    def _invalidate(self, case):
        setattr(self, case, None)
        if case == 'baseline':
            self.scenario = None

    def edit(self, case, callback):
        old = self.model(case)
        candidate = deepcopy(old)
        result = callback(candidate)
        validate_model(candidate)
        if candidate != old:
            self._undo[case].append(deepcopy(old))
            self._undo[case] = self._undo[case][-100:]
            self._redo[case].clear()
            setattr(self, case+'_model', candidate)
            self._invalidate(case)
        return result

    def run(self, case):
        model = self.model(case)
        if case == 'scenario' and not (self.baseline and self.baseline['converged']):
            raise ValueError('Run a converged baseline before running the comparison scenario.')
        result = run_model(model)
        setattr(self, case, result)
        return result

    def undo(self, case):
        self.model(case)
        if not self._undo[case]:
            return False
        self._redo[case].append(deepcopy(self.model(case)))
        setattr(self, case+'_model', self._undo[case].pop())
        self._invalidate(case)
        return True

    def redo(self, case):
        self.model(case)
        if not self._redo[case]:
            return False
        self._undo[case].append(deepcopy(self.model(case)))
        setattr(self, case+'_model', self._redo[case].pop())
        self._invalidate(case)
        return True

    def reset_scenario(self, record_history=True):
        if record_history:
            self._undo['scenario'].append(deepcopy(self.scenario_model))
            self._undo['scenario'] = self._undo['scenario'][-100:]
        else:
            self._undo['scenario'].clear()
        self._redo['scenario'].clear()
        self.scenario_model = deepcopy(self.baseline_model)
        self.scenario = None

    def save(self, path):
        validate_model(self.baseline_model)
        validate_model(self.scenario_model)
        payload = dict(format='texas-grid-editor', version=4,
                       baseline_model=self.baseline_model, scenario_model=self.scenario_model,
                       baseline_results=self.baseline, scenario_results=self.scenario,
                       assumptions=INTERFACE_ASSUMPTION)
        text = json.dumps(payload, indent=2, allow_nan=False)
        if len(text.encode('utf-8')) > MAX_PROJECT_BYTES:
            raise ValueError('Project file would exceed the 30 MB reopen limit.')
        Path(path).write_text(text, encoding='utf-8')

    @classmethod
    def load(cls, path):
        if Path(path).stat().st_size > MAX_PROJECT_BYTES:
            raise ValueError('Project file exceeds 30 MB.')
        def invalid_number(value):
            raise ValueError('Project file contains a non-finite number: '+value)
        payload = json.loads(Path(path).read_text(encoding='utf-8-sig'), parse_constant=invalid_number)
        if not isinstance(payload, dict) or payload.get('format') != 'texas-grid-editor' or payload.get('version') != 4:
            raise ValueError('This is not a Project V4 editable study.')
        study = cls(payload.get('baseline_model'))
        validate_model(payload.get('scenario_model'))
        study.scenario_model = deepcopy(payload['scenario_model'])
        # Archived numerical results are never presented as freshly computed.
        return study
