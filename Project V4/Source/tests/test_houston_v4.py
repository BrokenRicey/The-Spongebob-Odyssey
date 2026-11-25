"""Geographic topology, fixed supplies and full-network solver acceptance."""
from copy import deepcopy

from simulation.houston import build_houston_model, import_features
from simulation.editor import add_datacenter, run_model, toggle_component, validate_model


def feature(key, coordinates, voltage=138):
    return dict(type='Feature', properties=dict(OBJECTID=key, ID=str(key), VOLTAGE=voltage),
                geometry=dict(type='LineString', coordinates=coordinates))


def test_import_joins_endpoints_but_not_crossings_or_voltage_groups():
    features = [feature(1, [[-95.8, 29.7], [-95.7, 29.7]]),
                feature(2, [[-95.7, 29.7], [-95.6, 29.7]]),
                feature(3, [[-95.75, 29.65], [-95.75, 29.75]]),
                feature(4, [[-95.7, 29.7], [-95.6, 29.7]], 345)]
    model = import_features(features)
    assert len(model['buses']) == 7
    assert len(model['sources']) == 3
    assert model['lines'][0]['to_bus'] == model['lines'][1]['from_bus']
    assert model['lines'][3]['from_bus'] != model['lines'][1]['from_bus']
    assert import_features(list(reversed(features))) == model
    validate_model(model)


def test_outage_creates_unsupplied_load_without_replacement_source():
    # Boundary supplies are fixed when imported, not recomputed for the island.
    model = import_features([feature(1, [[-95.85, 29.7], [-95.80, 29.7]]),
                             feature(2, [[-95.80, 29.7], [-95.75, 29.7]])])
    add_datacenter(model, 'ISLAND_LOAD', 29.7, -95.75, 10)
    original_sources = deepcopy(model['sources'])
    baseline = run_model(model)
    assert baseline['converged'] and baseline['loads']['ISLAND_LOAD']['supplied']
    toggle_component(model, 'lines', 'GIS_1_1', False)
    result = run_model(model)
    assert result['converged']
    assert not result['loads']['ISLAND_LOAD']['supplied']
    assert result['totals']['unserved_load_mw'] == 10
    assert model['sources'] == original_sources
    toggle_component(model, 'lines', 'GIS_1_1', True)
    restored = run_model(model)
    assert restored['converged'] and restored['loads']['ISLAND_LOAD']['supplied']


def test_full_cached_houston_network_preserves_routes_and_solves():
    raw = build_houston_model(seed_loads=False)
    assert raw['provenance']['source_feature_count'] == 701
    assert len(raw['lines']) == raw['provenance']['source_part_count'] == 702
    assert len({line['source_route_key'] for line in raw['lines']}) == 701
    assert len(raw['buses']) > 500
    assert len(raw['sources']) == raw['provenance']['initial_component_count']
    assert all(line['from_bus'] != line['to_bus'] for line in raw['lines'])
    model = build_houston_model()
    validate_model(model)
    assert model['sources'] == raw['sources']
    assert len(model['loads']) == 10
    # Seed taps subdivide source routes, without introducing/removing geography.
    lengths = {}
    for line in model['lines']:
        key = line['source_route_key'], line['source_part']
        lengths[key] = lengths.get(key, 0)+line['length_km']
    for line in raw['lines']:
        assert abs(lengths[line['source_route_key'], line['source_part']]-line['length_km']) < 1e-9
    result = run_model(model)
    assert result['converged'], result['message']
    assert len(result['lines']) == len(model['lines'])
    assert result['totals']['unsupplied_buses'] == 0
    assert sum(load['p_mw'] for load in result['loads'].values()) == 100
