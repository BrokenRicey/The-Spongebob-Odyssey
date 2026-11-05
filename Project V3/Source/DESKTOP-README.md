# Texas Grid Analysis — Windows desktop

A native Qt application for Team 11's Houston grid-impact study. Runs locally with
bundled Python, pandapower, and geographic data. It does not start a web server,
open a browser, require an API key, or download map tiles.

## Run the portable application

1. Extract **Texas-Grid-Analysis-Windows-x64.zip** to a folder.
2. Open the extracted **Texas Grid Analysis** folder.
3. Double-click **Texas Grid Analysis.exe**. Keep the `_internal` folder beside it.

Windows x64. Tested on Windows 11; Windows 10 compatibility is not verified.
The first launch may take several seconds to load the numerical libraries.
This is an unsigned project build, not a signed commercial installer.

## Study workflow

- Run **baseline** to solve the bundled study: 18 buses, 25 lines, 3 transformers,
  and 10 synthetic facility loads. The initial gross demand is 30 MW per load.
- To edit the baseline, choose a facility, change its bus, MW, generation or power
  factor, then click **Apply to baseline inputs** and rerun baseline. **Add study
  load** creates an additional assumed load using the current form values.
- For a **load change**, edit the facility form and click **Run scenario**. It is
  applied to the saved baseline without changing that baseline.
- For a **line outage**, choose a line. For **disconnect load**, choose a facility.
  Both use saved baseline demand values; unapplied demand fields do not affect them.
- **AI training sweep** calculates 16 steady-state points at 0–150% of all baseline
  gross real and reactive demand, holding onsite generation fixed. The comparison
  displays the final 150% point; the chart and exports contain the sweep.
- Select map symbols or table rows to inspect components. Branches are selectable
  at their midpoint. Drag to pan, scroll to zoom, or click Fit. Search accepts
  modeled IDs, substation names, and directory-location names.
- Baseline / Scenario / Change controls the map. In Change, orange indicates
  increased branch loading and cyan indicates unchanged or reduced loading.
  Bus violation colors reflect the scenario. Change values appear in the bus table.
- **Save study** stores baseline inputs, last-run scenario inputs, current editor
  inputs, and raw results in a `.gridstudy` JSON file. **Open study** restores inputs;
  rerun the baseline before running scenarios. Stored results are not silently
  treated as verified results for a new session.
- **Export results** saves a long-form CSV or full JSON study. Units are in metric
  names (`p_mw`, `q_mvar`, `vm_pu`, `loading_percent`, `va_degree`). CSV includes
  baseline, scenario, buses, lines, transformers, loads, totals, and sweep points.
- Light/dark mode is remembered locally. Ctrl+S saves; Ctrl+O opens.

For a ready-made example, open `Example studies/High demand at Bus 12.gridstudy`,
run baseline, then run scenario. It moves DC_01 to BUS_12 and increases its assumed
gross demand to 600 MW, demonstrating both voltage and line-loading violations.
It is a synthetic stress test, not a claim about any actual Houston facility.

## Meaning of the map and results

The electrical model is **representative and synthetic**, not a verified ERCOT
network. Public Houston transmission geometry and approximate directory locations
are included from [the team repository](https://github.com/BrokenRicey/The-Spongebob-Odyssey),
revision recorded in `data/github_houston/REVISION.txt`. Thin GIS routes and purple
directory markers are geographic context only. Modeled branches are cyan/teal;
orange building symbols are synthetic study loads beside their assumed bus.
Proximity never establishes an electrical connection. The bay is schematic;
this package does not include a detailed street basemap.

The visual references guide the two color themes and panel arrangement. Their
illustrative numerical values are not hard-coded into this application. All
displayed study results come from the local solver.

Voltage limits are 0.95–1.05 pu, inclusive. Line and transformer loading above 100%
is a violation. Unsupplied buses are flagged even if the supplied network converges.
An unsuccessful simulation has no valid current numerical results. Onsite generation
is modeled at unity power factor; facility reactive demand uses gross demand and
the entered lagging power factor.

Fault currents, SSO, protection, transient response, weather models, live telemetry,
and a validated reconstruction of the Houston/ ERCOT grid are **not implemented**.
The fault-study button explains the required additional data. Consult **Sources &
assumptions** for provenance and the model assumptions retained from the local project.

## Build from source

Use 64-bit Python 3.12 on Windows, in this repository:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
.\.venv\Scripts\python.exe desktop_launcher.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm TexasGrid.spec
```

The build is `dist/Texas Grid Analysis/`. Archive the entire folder for distribution.
Qt is dynamically bundled; third-party license texts and installed package metadata
remain under `_internal`. The development environment is not shipped.

## Verification

The existing simulation tests cover V4 regression, IEEE 14-bus voltage and angle
comparison with PYPOWER, islands, nonconvergence, generation and demand sweeps.
PYPOWER shares solver ancestry with pandapower, so this does not replace a separate
MATPOWER/reference-software validation. Real-grid accuracy and the documents' full
statistical acceptance targets remain unestablished.

Desktop tests cover saved study validation, connection changes, added loads and
exports. The packaged executable supports `--self-test`, which exercises the Qt
window, asynchronous solver, scenarios, numerical display, exports and failure
clearing, and writes screenshots and `report.json` to `artifacts/desktop-qa` in the
working folder. Set `GRID_SELFTEST_DIR` to choose another output folder.
