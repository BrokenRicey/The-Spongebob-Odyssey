# Houston map

This folder holds the editable Houston HTML map and its desktop integration.

- `generator.py`: HTML template, transmission feature processing, and standalone map generation.
- `assets/`: Houston source cache and directory data, `load_editor.js`, `unified_map.js`, CSS, and Leaflet assets.
- `window.py`: embedded map, map-to-editor bridge, route attachments, and combined workspace layout.
- `diagram.py`: calculated electrical diagram and sweep chart.
- `selftest.py`: end-to-end checks for the combined map workspace.

From `Source/`, run `python -m map.generator`. This uses the bundled cache and writes the generated map and exports to `map/output/`. Add `--no-browser` to generate files without starting the viewer. Use `--refresh` only when intentionally updating the cached geographic source.

Run the combined application from the repository root with `python main.py`. Its electrical calculations come from `simulation/`; GIS route geometry does not establish an electrical connection.
