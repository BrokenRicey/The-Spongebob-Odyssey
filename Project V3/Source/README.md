# Developer folder guide

Start with [../README.md](../README.md#team-folder-layout) for the current simulation, map, and program folders. The browser-app instructions below describe the earlier FastAPI application.

# The-Spongebob-Odyssey
Senior Design Project

## Houston map application (initial version)

A local FastAPI + pandapower application with a full-window Leaflet map and floating cards. Light mode uses copper/teal and dark mode uses navy/cyan/gold. The original `simulation/TL_Senior_Simulation_V1.py` and `simulation/TL_Senior_Simulation_V4.py` are unchanged.

### Run on Windows (Python 3.12 recommended)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app
```

Open http://127.0.0.1:8000. The API documentation is at http://127.0.0.1:8000/docs. Alternatively run `.\.venv\Scripts\python.exe -m uvicorn app.server:app --host 127.0.0.1 --port 8000`. One worker only: study sessions are held in memory. Restarting the server clears runs; saved scenario inputs remain in browser local storage. Keep this development app bound to localhost.

Internet is needed for Leaflet's CDN, CARTO tiles, and optional Google Fonts. Bundled geographic data and power-flow calculations run locally. A missing basemap is reported; model overlays remain usable if Leaflet has loaded. No Node build is required.

### Configure the CARTO basemap key

CARTO now requires a basemap key, including for Positron and Dark Matter. An HTTP 200 response can contain an “API key required” image rather than usable geographic tiles. The app does not request unauthenticated CARTO tiles.

1. Visit [CARTO's Basemaps key page](https://www.carto.com/basemaps/apikey/index.html).
2. Use its request form, provide your email address, and review/accept CARTO's terms yourself.
3. Retrieve the key from the email or dashboard.
4. Open the local app and click **Map key** in its header.
5. Paste the key and click **Save key & reload map**.
6. Toggle the theme to confirm both basemaps load. If old watermark tiles remain, force-refresh with Ctrl+F5.

The key is saved only in this browser's local storage, never in the repository. It is sent to CARTO in browser tile requests and is therefore a browser-visible basemap credential. Use the CARTO dashboard to manage restrictions and usage. Each browser/origin needs its own configuration. No OpenAI API key is required for the application or solver.

### First study

1. Choose a placeholder facility, connection bus, demand, power factor, and onsite generation.
2. Run **baseline**. This snapshots the entered facility settings and the other catalog loads.
3. Select load change, line outage, disconnect load, or load sweep. Load-change scenarios use the edited facility inputs. Outage/disconnection scenarios use the saved baseline loads and selected target.
4. Run **scenario**. Inspect numerical comparisons, affected elements, and map views. Changing inputs labels existing results outdated and disables export until another run.
5. Use **Save scenario** to store inputs locally; **Scenarios** restores them. **Export results** offers JSON (including model/provenance) and CSV.

Every study has an isolated server session and a baseline ID. A stale ID is rejected. Failed runs replace the current failed case with an explicit failure object; prior scenario values are not presented as current. A converged islanded case can still contain unsupplied buses, which are flagged separately. Fault analysis is visibly unavailable.

### Data that actually worked (2026-10-12)

- **802 transmission features:** [FEMA Region 6 ArcGIS layer](https://services.arcgis.com/XG15cJAlne2vxtgt/ArcGIS/rest/services/FEMA_Region_6_Electric_Power_Transmission_Lines/FeatureServer/0). Envelope query, pagination, WGS84 output, clipped to the study area.
- **522 substations:** [public ArcGIS Electric_Substations fallback](https://services.arcgis.com/XG15cJAlne2vxtgt/ArcGIS/rest/services/Electric_Substations/FeatureServer/0). This was used because Overpass endpoints returned HTTP 406/429.
- **10 synthetic facilities:** all marked `placeholder=True`; no verified data-center locations or demand values are claimed in this initial dataset.
- Raw source responses are under `data/raw`; normalized geographic layers are under `data/processed`. Raw metadata contains source limitations. Public geographic records are not proof of current equipment status.

The electrical model is **18 buses, 25 lines, three transformers, one ideal source, and ten loads**. Geographic context and modeled connectivity are separate toggleable layers. All electrical parameters, bus voltage assignments, facility connections, and operating points are assumptions. Read [every assumption](docs/ASSUMPTIONS.md) before interpreting results. None of the modeled branches is asserted to be a matched public line route.

### Refresh data / regenerate model

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m scripts.fetch_transmission
.\.venv\Scripts\python.exe -m scripts.fetch_osm
.\.venv\Scripts\python.exe -m scripts.build_model
```

If Overpass is unavailable, use the explicit fallback:

```powershell
.\.venv\Scripts\python.exe -m scripts.fetch_substations
.\.venv\Scripts\python.exe -m scripts.fetch_osm --placeholders-only
.\.venv\Scripts\python.exe -m scripts.build_model
```

The catalog regeneration command replaces `data/facilities.csv`; preserve team-verified rows before refreshing. `build_model` assigns nearest coordinate anchors **as a documented study assumption**, never as verified connectivity. It updates catalog bus IDs. Do not run regeneration concurrently with the server; restart after changing data. No datacentermap.com scraping is used.

### Verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m scripts.benchmark
node --check app/static/app.js
```

Tests cover V4 regression, the IEEE 14-bus case, preserved baseline state, onsite-generation accounting, disconnects, outage islands, non-convergence, invalid catalogs and requests, isolated sessions, stale baseline IDs, and export content. The IEEE comparison solves standalone PYPOWER's MATPOWER-format `case14`, using matched pi transformer models and tolerances of 0.001 pu / 0.1°. PYPOWER and pandapower share solver ancestry; this does not replace independent MATPOWER validation. Historical voltages stored inside `case14` are initialization values and are not used as exact solved reference results.

`docs/benchmark.json` records local build/run and sweep timings plus machine information. Performance acceptance at 95% confidence and browser-render response times are not established by this initial test.

Browser automation was denied local-page access in this development session. Both themes, narrow layouts, tile loading, and end-to-end mouse/keyboard interactions still require a visual smoke test. The frontend syntax and backend API have been checked; no visual verification is claimed.

### Source layout

- `gridsim/`: constants, catalog validation, network construction, scenarios, results.
- `app/`: typed FastAPI routes and static HTML/CSS/JavaScript.
- `scripts/`: source downloads, model generation, benchmark.
- `tests/`: simulation, API, and catalog tests.
- `docs/`: assumptions and measured benchmark results.

Reference documentation: [pandapower AC power flow](https://pandapower.readthedocs.io/en/stable/powerflow/ac.html), [Leaflet](https://leafletjs.com/reference.html). Map attribution: © OpenStreetMap contributors © CARTO. OSM-derived downloads, when available, require ODbL attribution.
