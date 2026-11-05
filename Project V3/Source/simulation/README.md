# Simulation

Thanh's original simulation scripts keep their version names: `TL_Senior_Simulation_V1.py` and `TL_Senior_Simulation_V4.py`. V4 is the active power-flow solver. No V2 engine is included in this snapshot.

- `gridsim/`: converts the shared model to a network, applies scenarios, and returns solver results.
- `study.py`: validates study inputs, runs baseline/scenarios, saves and opens projects, and exports results.

Add future simulation versions here and explicitly update the imports when the team adopts a new solver. The shared model data remains in `Source/data/`; map rendering belongs in `Source/map/`.
