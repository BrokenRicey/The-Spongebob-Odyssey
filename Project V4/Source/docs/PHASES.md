# Initial implementation delivery

## Phase 1: geographic data and catalog

Added `scripts/common.py`, `fetch_transmission.py`, `fetch_osm.py`, `fetch_substations.py`, raw source snapshots, cleaned GeoJSON, `data/facilities.csv`, and `gridsim/catalog.py`.

Working sources: 802 ArcGIS FEMA Region 6 transmission features; 522 ArcGIS Electric_Substations features. Overpass returned 406/429 from three endpoints, so substation coordinates came from the public ArcGIS fallback and all ten facility records are synthetic placeholders. Source/retrieval/status fields and missing-data flags are retained. Catalog tests reject invalid coordinates, demands, power factors, missing provenance, and duplicate IDs.

## Phase 2: representative model and simulation

Added `gridsim/config.py`, `network.py`, `scenarios.py`, `results.py`, `scripts/build_model.py`, `data/model/houston_model.json`, simulation tests, and the timing script/report.

The model contains 18 buses, 25 lines, three transformers, and ten loads. It supports baseline, load/connection change, line outage, facility disconnection, and 0–150% sweep. Fault studies return not implemented. Baseline copies are preserved, results are keyed by IDs, and unsupplied islands are explicit.

V4 regression and IEEE 14-bus comparison pass. The latter uses a solved standalone PYPOWER reference with matched pi transformers, not initial case-file voltages. Independent MATPOWER validation remains outstanding. Complete estimates, their origin, and study limits are in [ASSUMPTIONS.md](ASSUMPTIONS.md).

## Phase 3: local API

Added `app/server.py`, `app/__main__.py`, API tests, and catalog tests. Implemented session-scoped baselines, Pydantic validation, geographic/model endpoints, study runs, provenance, and CSV/JSON exports. Failed studies clear their current result, stale baseline IDs are rejected, and different browser sessions cannot retrieve one another's studies.

## Phase 4: light/dark floating-card UI

Added `app/static/index.html`, `styles.css`, and `app.js`, plus README setup and workflow instructions. Implemented a full-window map, floating setup/results/layer cards, a results drawer, theme preference, map selection/search, baseline/scenario/change overlays, loading labels, outage symbols, source dialog, scenario storage, and export selection. The original V1/V4 scripts are unchanged.

Verified: 25 Python tests pass, JavaScript syntax check passes, Git whitespace check passes. Measured ten-load model build/run median 0.157 s, maximum 0.195 s across ten runs; 16-point sweep 0.445 s on the recorded machine. These are measurements, not 95%-confidence acceptance results.

Browser access to localhost was denied by the browser permission system. Visual testing of both themes, narrow windows, CDN/tile loading, and the complete click workflow is pending. No browser verification or screenshot of the running app is claimed.

Run `.\.venv\Scripts\python.exe -m app` from the repository root, then visit http://127.0.0.1:8000. Local commits use the transparent `Codex <codex@localhost>` author identity because no Git identity was configured. Changes have not been pushed to GitHub.
