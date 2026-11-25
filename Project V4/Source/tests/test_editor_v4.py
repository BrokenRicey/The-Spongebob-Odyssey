"""Electrical consequences and snapshot persistence for editable Project V4."""
from copy import deepcopy
import json

import pytest

from simulation.editor import (EditorStudy, add_bus, add_datacenter, add_line,
    move_bus, move_datacenter, nearest_connection, reconnect_line, run_model, toggle_component,
    validate_model)


def model():
    return dict(buses=[dict(id='A', lat=30, lon=-95, vn_kv=138),
                       dict(id='B', lat=30, lon=-94.8, vn_kv=138),
                       dict(id='C', lat=30.1, lon=-95, vn_kv=138)],
                lines=[dict(id='AB', from_bus='A', to_bus='B', length_km=20),
                       dict(id='AC', from_bus='A', to_bus='C', length_km=12)],
                transformers=[], sources=[dict(id='GRID', bus_id='A')],
                loads=[dict(id='DC', bus_id='B', p_mw=20, pf=.95, onsite_gen_mw=3)])


def test_multiple_edits_are_independent_from_baseline_and_undoable(tmp_path):
    study = EditorStudy(model())
    baseline = study.run('baseline')
    assert baseline['converged']
    study.edit('scenario', lambda m: toggle_component(m, 'lines', 'AB', False))
    study.edit('scenario', lambda m: add_datacenter(m, 'NEW', 30.1, -95, 5))
    result = study.run('scenario')
    assert result['converged']
    assert result['loads']['DC']['supplied'] is False
    assert result['loads']['DC']['p_mw'] is None
    assert result['loads']['DC']['onsite_gen_mw'] is None
    assert result['totals']['unserved_load_mw'] == 20
    assert result['loads']['NEW']['net_grid_mw'] == pytest.approx(5)
    assert study.baseline == baseline
    assert 'in_service' not in study.baseline_model['lines'][0]
    path = tmp_path/'saved.gridstudy'
    study.save(path)
    reopened = EditorStudy.load(path)
    assert reopened.baseline_model == study.baseline_model
    assert reopened.scenario_model == study.scenario_model
    assert reopened.baseline is reopened.scenario is None
    assert study.undo('scenario') and len(study.scenario_model['loads']) == 1
    assert study.scenario is None
    assert study.redo('scenario') and len(study.scenario_model['loads']) == 2
    study.reset_scenario()
    assert study.scenario_model == study.baseline_model
    assert study.undo('scenario') and len(study.scenario_model['loads']) == 2


def test_tap_preserves_route_length_impedance_and_existing_power_flow():
    m = model()
    before = run_model(m)
    new = add_datacenter(m, 'TAP', 30.01, -94.9, 0)
    assert len(m['buses']) == 4 and len(m['lines']) == 3
    segments = [l for l in m['lines'] if l.get('parent_id') == 'AB']
    assert len(segments) == 2
    assert sum(l['length_km'] for l in segments) == pytest.approx(20)
    assert new['lat'] == 30.01 and new['lon'] == -94.9
    tap = next(b for b in m['buses'] if b['id'] == new['bus_id'])
    assert tap['lat'] == pytest.approx(30)
    after = run_model(m)
    assert after['converged']
    assert after['buses']['B']['vm_pu'] == pytest.approx(before['buses']['B']['vm_pu'], abs=1e-8)
    assert after['totals']['losses_mw'] == pytest.approx(before['totals']['losses_mw'], abs=1e-7)


def test_tapping_disabled_line_does_not_silently_restore_supply():
    m = model()
    toggle_component(m, 'lines', 'AB', False)
    load = add_datacenter(m, 'TAP', 30.01, -94.9, 12)
    assert all(not l['in_service'] for l in m['lines'] if l.get('parent_id') == 'AB')
    result = run_model(m)
    assert result['converged'] and not result['loads'][load['id']]['supplied']
    assert result['totals']['unserved_load_mw'] == 32


def test_disable_bus_or_load_and_onsite_generation():
    m = model()
    toggle_component(m, 'buses', 'B', False)
    result = run_model(m)
    assert result['converged'] and result['buses']['B']['in_service'] is False
    assert result['loads']['DC']['net_grid_mw'] is None
    toggle_component(m, 'buses', 'B', True)
    toggle_component(m, 'loads', 'DC', False)
    result = run_model(m)
    assert result['loads']['DC']['net_grid_mw'] == 0
    assert result['loads']['DC']['onsite_gen_mw'] == 0
    assert result['totals']['unserved_load_mw'] == 0


def test_added_bus_transformer_move_and_reconnect():
    m = model()
    bus = add_bus(m, 30.2, -95.1, 345, 'HV')
    branch = add_line(m, 'A', bus['id'])
    assert branch['hv_bus'] == 'HV' and branch['vn_hv_kv'] == 345
    assert validate_model(m) is m
    old_length = m['lines'][0]['length_km']
    move_bus(m, 'B', 30, -94.6)
    assert m['lines'][0]['length_km'] == pytest.approx(2*old_length)
    reconnect_line(m, 'AB', 'A', 'C')
    assert m['lines'][0]['to_bus'] == 'C'
    with pytest.raises(ValueError, match='same voltage'):
        reconnect_line(m, 'AB', 'A', 'HV')
    assert run_model(m)['converged']


def test_curved_route_nearest_connection_and_split():
    m = model()
    m['lines'][0]['points'] = [[30, -95], [30.05, -94.9], [30, -94.8]]
    closest = nearest_connection(m, 30.051, -94.9)
    assert closest['kind'] == 'lines' and closest['id'] == 'AB'
    assert closest['fraction'] == pytest.approx(.5)
    add_datacenter(m, 'BEND', 30.051, -94.9, 5)
    assert validate_model(m)
    assert sum(l['length_km'] for l in m['lines'] if l.get('parent_id') == 'AB') == pytest.approx(20)


def test_reject_invalid_changes_atomically_and_invalid_files(tmp_path):
    study = EditorStudy(model())
    original = deepcopy(study.scenario_model)
    with pytest.raises(ValueError, match='Unknown connection bus'):
        study.edit('scenario', lambda m: m['lines'][0].update(to_bus='MISSING'))
    assert study.scenario_model == original
    assert not study.undo('scenario')
    path = tmp_path/'invalid.gridstudy'
    study.save(path)
    obj = json.loads(path.read_text())
    obj['scenario_model']['buses'][0]['lat'] = float('nan')
    path.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match='non-finite'):
        EditorStudy.load(path)


def test_baseline_edits_invalidate_both_results_without_changing_scenario():
    study = EditorStudy(model())
    study.run('baseline')
    study.run('scenario')
    study.edit('baseline', lambda m: m['loads'][0].update(p_mw=40))
    assert study.baseline is study.scenario is None
    assert study.scenario_model['loads'][0]['p_mw'] == 20
    with pytest.raises(ValueError, match='baseline'):
        study.run('scenario')


def test_last_source_disabled_is_an_explicit_failed_run():
    m = model()
    toggle_component(m, 'sources', 'GRID', False)
    result = run_model(m)
    assert not result['converged'] and not result['buses']
    assert 'No enabled source' in result['message']
    toggle_component(m, 'sources', 'GRID', True)
    toggle_component(m, 'buses', 'A', False)
    assert not run_model(m)['converged']


def test_dragging_data_center_reconnects_without_changing_demand():
    m = model()
    load = move_datacenter(m, 'DC', 30.1, -95)
    assert load['bus_id'] == 'C' and load['p_mw'] == 20
    assert load['onsite_gen_mw'] == 3
    result = run_model(m)
    assert result['converged'] and result['loads']['DC']['net_grid_mw'] == pytest.approx(17)


@pytest.mark.parametrize('value', [float('nan'), float('inf'), 10**400])
def test_unknown_metadata_cannot_poison_ui_serialization(value):
    m = model()
    m['provenance'] = {'extra': [value]}
    with pytest.raises(ValueError, match='finite'):
        validate_model(m)


def test_json_overflow_in_unknown_field_rejected_on_open(tmp_path):
    study = EditorStudy(model())
    path = tmp_path/'overflow.gridstudy'
    study.save(path)
    text = path.read_text().replace('"scenario_model": {', '"scenario_model": {"extra": 1e999,')
    path.write_text(text)
    with pytest.raises(ValueError, match='finite'):
        EditorStudy.load(path)


def test_initial_scenario_fork_has_no_prebaseline_undo_history():
    study = EditorStudy(model())
    study.edit('baseline', lambda m: m['loads'][0].update(p_mw=40))
    study.reset_scenario(record_history=False)
    assert study.scenario_model['loads'][0]['p_mw'] == 40
    assert not study.undo('scenario')


def test_all_loads_disabled_and_deleted_have_valid_no_load_solution():
    m = model()
    toggle_component(m, 'loads', 'DC', False)
    result = run_model(m)
    assert result['converged']
    assert result['totals']['grid_supply_mw'] == pytest.approx(0, abs=1e-6)
    assert result['totals']['unserved_load_mw'] == 0
    m['loads'] = []
    result = run_model(m)
    assert result['converged'] and result['loads'] == {}


def test_oversized_save_does_not_overwrite_existing_project(tmp_path, monkeypatch):
    from simulation import editor
    path = tmp_path/'study.gridstudy'
    path.write_text('existing saved project')
    monkeypatch.setattr(editor, 'MAX_PROJECT_BYTES', 10)
    with pytest.raises(ValueError, match='reopen limit'):
        EditorStudy(model()).save(path)
    assert path.read_text() == 'existing saved project'
