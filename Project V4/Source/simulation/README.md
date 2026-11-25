# Simulation

Project V4 uses `houston.py` to import the full cached route network and
`editor.py` for editable independent baseline/scenario models. The desktop
shell calls the shared power-flow solver on those complete snapshots. The
older `study.py` scenario interface is retained for regression coverage.

Thanh's original simulation scripts keep their version names: `TL_Senior_Simulation_V1.py` and `TL_Senior_Simulation_V4.py`. V4 is the active power-flow solver. No V2 engine is included in this snapshot.

- `gridsim/`: converts the shared model to a network, applies scenarios, and returns solver results.
- `study.py`: validates study inputs, runs baseline/scenarios, saves and opens projects, and exports results.

Add future simulation versions here and explicitly update the imports when the team adopts a new solver. The shared model data remains in `Source/data/`; map rendering belongs in `Source/map/`.
