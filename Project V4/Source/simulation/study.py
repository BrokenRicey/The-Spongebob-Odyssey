"""Validated, serializable studies. No servers or network access."""
import csv
import json
import math
from copy import deepcopy
from pathlib import Path

from simulation.gridsim.network import build_network
from simulation.gridsim.results import solve
from simulation.gridsim.scenarios import load_change, line_outage, load_disconnect, load_sweep

ROOT = Path(__file__).resolve().parents[1]
KINDS = ('Load change', 'Line outage', 'Disconnect load', 'AI training sweep')


def default_model():
    return json.loads((ROOT / 'data/model/houston_model.json').read_text(encoding='utf-8'))


def validate_load(load, model):
    if not isinstance(load.get('id'), str) or not load['id'].strip():
        raise ValueError('A facility ID is required.')
    if load.get('bus_id') not in {b['id'] for b in model['buses'] if b['vn_kv'] == 138}:
        raise ValueError('Choose a modeled 138 kV connection bus.')
    for key, low, high in [('p_mw', 0, 10000), ('onsite_gen_mw', 0, 10000), ('pf', .01, 1)]:
        v = load.get(key)
        if isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) or not low <= v <= high:
            raise ValueError(f'{key} must be a finite number between {low} and {high}.')


def validate_spec(spec, model):
    if spec.get('kind') not in KINDS:
        raise ValueError('Unsupported study type.')
    validate_load(spec['load'], model)
    if spec['load']['id'] not in {x['id'] for x in model['loads']}:
        raise ValueError('Unknown modeled facility.')
    if spec.get('line') not in {x['id'] for x in model['lines']}:
        raise ValueError('Unknown transmission line.')


def run_baseline(model):
    for load in model['loads']:
        validate_load(load, model)
    return solve(build_network(model))


def run_scenario(model, spec):
    validate_spec(spec, model)
    net = build_network(model)
    load = spec['load']
    kind = spec['kind']
    if kind == 'Load change':
        net = load_change(net, load['id'], load['p_mw'], load['pf'], load['onsite_gen_mw'], load['bus_id'])
    elif kind == 'Line outage':
        net = line_outage(net, spec['line'])
    elif kind == 'Disconnect load':
        net = load_disconnect(net, load['id'])
    else:
        # A sequence of steady-state points, not a transient AI workload model.
        points = load_sweep(net, [i / 10 for i in range(16)])
        result = deepcopy(points[-1]['result'])
        result['sweep'] = points
        result['message'] += ' · displayed point: 150% of baseline gross P/Q'
        return result
    return solve(net)


def save_study(path, model, spec, baseline=None, scenario=None):
    validate_spec(spec, model)
    payload = {'format': 'texas-grid-desktop', 'version': 1, 'model': model, 'scenario_inputs': spec,
               'baseline_results': baseline, 'scenario_results': scenario,
               'assumptions': 'Representative synthetic electrical topology; no live telemetry. Geographic layers do not establish electrical connectivity.'}
    Path(path).write_text(json.dumps(payload, indent=2, allow_nan=False), encoding='utf-8')


def load_study(path):
    if Path(path).stat().st_size > 20_000_000:
        raise ValueError('Study file exceeds 20 MB.')
    obj = json.loads(Path(path).read_text(encoding='utf-8'))
    if obj.get('format') != 'texas-grid-desktop' or obj.get('version') != 1:
        raise ValueError('This is not a supported desktop study file.')
    # Only documented load changes may enter through a saved study. Never execute code.
    model = default_model()
    incoming = obj['model']
    for key in ['buses', 'lines', 'sources', 'transformers']:
        if incoming.get(key) != model.get(key):
            raise ValueError('This file uses a different network revision. Open it with its matching application version.')
    loads = incoming['loads']
    if not isinstance(loads, list) or not 1 <= len(loads) <= 200:
        raise ValueError('A study must contain 1 to 200 loads.')
    for load in loads:
        validate_load(load, model)
    if len({x['id'] for x in loads}) != len(loads):
        raise ValueError('Duplicate facility IDs.')
    model['loads'] = deepcopy(loads)
    validate_spec(obj['scenario_inputs'], model)
    editor = obj.get('editor_inputs', obj['scenario_inputs'])
    validate_spec(editor, model)
    return model, editor


def export_csv(path, baseline, scenario):
    with Path(path).open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['case', 'converged', 'section', 'component', 'metric', 'value'])
        for name, result in [('baseline', baseline), ('scenario', scenario)]:
            if not result:
                continue
            writer.writerow([name, result['converged'], 'run', '', 'message', result['message']])
            for key, value in result.get('totals', {}).items():
                writer.writerow([name, result['converged'], 'totals', '', key, value])
            for section in ['buses', 'lines', 'transformers', 'loads']:
                for element, row in result.get(section, {}).items():
                    for key, value in row.items():
                        writer.writerow([name, result['converged'], section, element, key, value])
            for point in result.get('sweep', []):
                for key, value in point['result'].get('totals', {}).items():
                    writer.writerow([name, point['result']['converged'], 'sweep', point['scale'], key, value])
