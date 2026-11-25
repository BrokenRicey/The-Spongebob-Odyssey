# Project V4 — editable Houston grid

Start with [START-HERE.txt](START-HERE.txt) for simple installation steps.
Download the portable Windows app from the [V4 release](https://github.com/BrokenRicey/The-Spongebob-Odyssey/releases/tag/project-v4).

Start with [START-HERE.txt](START-HERE.txt) for simple installation steps.
Download the portable Windows app from the [V4 release](https://github.com/BrokenRicey/The-Spongebob-Odyssey/releases/tag/project-v4).

The combined Windows desktop application now uses the Houston transmission-route
dataset as its active electrical study network. Selecting and disabling a line
changes the same model used by the solver. The earlier 25-line demonstration
network is no longer the default simulation.

Run `Texas Grid Analysis V4.exe` in the portable application folder. Keep its
`_internal` folder beside it. Street-background tiles need internet access; the
bundled network, editor, saved studies, and simulation run locally.

## Baseline and comparison workflow

1. In **Baseline**, edit the network and hypothetical data centers as needed.
2. Press **Run simulation** to calculate the initial case.
3. Select **Scenario** to start from a copy of that baseline.
4. Disable multiple lines or buses, add loads, or edit the network. Edits accumulate.
5. Press **Run simulation** again. Inspect changed loading, voltage, unserved demand,
   and the results comparison. **Map colors → Change from baseline** shows differences.
6. **Save project** preserves both networks and their available results. Reopening
   restores editable inputs; run both cases again to refresh numerical results.

An edit clears affected results until the next manual run. Baseline edits also
invalidate the comparison but preserve existing scenario inputs. Use **Start
scenario from baseline** to replace the scenario with a fresh baseline copy.
**Undo** and **Redo** operate on the selected case. Resetting a scenario is undoable.

## Editing the map

- Click a transmission line anywhere along its route to inspect it. **Disable**
  opens it electrically; **Enable** restores it. Disabling a bus disconnects its
  attached equipment. A disconnected area may lose supply.
- **+ Data center**: click a map position and enter a name and MW demand. Power
  factor and onsite generation are optional advanced inputs. The site attaches
  to the nearest line or bus. A mid-line attachment creates a tap bus and two
  line segments while preserving the original aggregate length and impedance.
- **+ Bus**: click to place a bus and choose its nominal voltage.
- **Draw line**: select two buses. Different voltage levels create an assumed
  transformer; equal voltage levels create a transmission line.
- **Move**: drag a bus or data center. Moving a data center reconnects it to the
  nearest line or bus. Select a line to move its route handles. A line's endpoints
  can also be changed in its inspector. Moving route geometry updates line length.
- Delete a load or branch from the inspector. To delete a bus, first remove or
  reconnect its attached equipment; disabling the bus is the quicker outage action.
- **Export results** creates a CSV comparison or a JSON study snapshot.

## Model meaning and limits

The initial model includes all **701 geographic features**, represented as **702
continuous route sections**. One initial hypothetical load tap produces **703
solver line segments and 586 buses**. Ten synthetic data centers start at **10 MW
each**. These are editable examples, not measured Houston demand.

Same-voltage endpoints within one meter are assumed connected. Geographic
crossings are not automatically connected. One route with missing voltage is
assumed to be 138 kV. No unverified transformer connections are inferred between
the voltage groups. Users can add those connections explicitly.

The imported graph has **32 separate connected sections**. Each receives one
fixed, visible equivalent supply point, preferring a clipped study-boundary
endpoint. These are study assumptions, not verified power-plant or utility
substation assignments. The supply points do not regenerate when a line is
disabled; an outage can therefore create an unsupplied island.

Line resistance, reactance, capacitance, and current limits use the existing V4
demonstration assumptions: 0.05 ohm/km, 0.40 ohm/km, zero nF/km, and 1 kA. Route
length follows the cached geographic geometry. Hypothetical data centers assume
ideal, adequately rated site transformers and interface equipment; demand is
referred to the connected bus voltage, with site losses omitted.

The AC power-flow calculation follows the connected network. There is no
artificial distance cutoff for an outage. Redistribution, voltage changes, and
islanding depend on network topology and these assumptions. A failed calculation
is reported explicitly and does not retain old numerical results as current.

This is an exploratory steady-state model based on Houston geography, not a
validated reconstruction of ERCOT operations. It does not predict cascading
protection trips, transient behavior, or actual weather damage. A weather scenario
is represented by the outages the user selects. No AI results assistant is included.

## Source and checks

In the repository's `Project V4` source folder, launch with `python main.py`
using the dependencies in `Source/requirements-desktop.txt`. Source code is
separate from the portable application folder. Build from `Source/` with:

```powershell
python -m pytest -q
node --check map/assets/editor.js
python main.py --self-test
python -m PyInstaller --noconfirm TexasGrid.spec
```

New code is organized as follows:

- `Source/simulation/houston.py`: geographic topology import and fixed supply assumptions.
- `Source/simulation/editor.py`: arbitrary network edits, snapshots, validation, and persistence.
- `Source/map/editor_window.py`: desktop shell and background solver.
- `Source/map/assets/editor.*`: embedded map interface.
- `Source/map/editor_selftest.py`: integrated desktop verification.

Thanh's `TL_Senior_Simulation_V4.py` remains the AC solver. Project V4 is the
application version; it does not rename the historical solver versions. Project
V3 remains available in its existing folder.
