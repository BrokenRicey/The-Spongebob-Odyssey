# Texas Grid Analysis V3 — one-screen workspace

Open **Start Texas Grid Analysis**. The Houston transmission map is now inside the results workspace. There are no separate map/simulation workspace tabs.

## Layout
- Left: the shared load editor, route attachment controls, scenario selector, and Run baseline / Run scenario.
- Center: the Houston street map and all 701 transmission features, with interactive calculated bus and load overlays.
- Right: baseline/scenario comparison and selected-component details.
- Below the map: a results selector for affected components, bus voltages, branch loading, power usage, load sweep, and run log. Changing this selector keeps the map visible.

Click a load marker to select it in the editor. Click a bus, branch, or load result row to select it on the map. Use Baseline / Scenario / Change above the map to inspect each result state. Hover over markers for voltage and demand values. The map displays disconnected loads and out-of-range bus voltages differently.

## Add, edit, and move loads
1. Click a colored GIS route. Its ID appears in the left panel.
2. Click **Add load** and enter demand, generation, power factor, and the assumed electrical bus. The new load attaches to the clicked GIS route automatically.
3. To move an existing load, select it, click a different route, then click **Attach to line**.
4. **Clear attachment** removes its geographic route attachment while retaining the electrical load. It is then shown beside its assumed bus.
5. **Remove load** and **Undo last removal** work on the same shared list used by the solver. The current study format requires at least one load; use Disconnect load to study its removal from service.

For baseline input edits, click **Apply to baseline inputs**, then **Run baseline**. For a comparison against the current baseline, choose Load change, edit demand or generation, and click **Run scenario**. Line outage, load disconnection, and load sweep remain available in the scenario selector.

## Save and open
**Save project** stores all loads, route attachments, scenario inputs, and result snapshots together in one .gridstudy file. **Open project** restores inputs; rerun calculations to refresh results. Older .gridstudy files remain supported. Earlier V3 route JSON files can be imported when their loads have valid simulation-bus assignments.

**Export results** exports CSV or JSON using the existing simulation export controls. It is separate from project saving.

## Map controls and interpretation
**Map layers** opens the voltage legend and street-background controls inside the map. Public GIS routes and directory locations can also be toggled directly below the map. Zoom buttons and Fit remain available. Panel widths and the map/table height can be adjusted using the splitters. Smaller windows allow the side panels to scroll.

Colored transmission routes are geographic source features. Circular bus markers and load results come from the representative electrical network and V4 solver. A selected modeled branch is drawn as a dashed line to distinguish its assumed connectivity from GIS routes. Clicking a geographic line does not silently change a load's electrical bus. Choose the connection bus explicitly in the load editor.

Street tiles require internet access. The bundled geometry, load editing, and calculations run locally. Fault/transient studies remain unavailable.

## Verification and source
Source contains the editable Python/JavaScript and TexasGrid.spec. Verification/single-screen-packaged contains the final runtime report and screenshots. Previous two-workspace files are retained under Verification for rollback.
