# Main desktop program

`window.py` provides the shared load editor, simulation controls, result tables, and exports. `selftest.py` verifies those controls. The combined workspace is assembled by `map/window.py` and launched through `Source/main.py`.

From the repository root, run `python main.py`. Put electrical calculations in `simulation/` and geographic rendering in `map/` so the shared interface does not become a second copy of either component.
