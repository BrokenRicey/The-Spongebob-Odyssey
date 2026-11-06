# Houston transmission grid — Python GIS foundation

## Run in PyCharm, Anaconda, or a terminal

1. Extract the whole ZIP into a writable folder.
2. Open `houston_grid.py` in PyCharm and click Run, or run:

```bash
python houston_grid.py
```

Python 3.10 or newer. No pip packages required. The map opens in your browser at http://127.0.0.1:<port>/houston_grid.html.
Keep Python running while viewing it. Stop with Ctrl+C or the PyCharm Stop button.
The server listens only on your computer and serves only the generated map page.
The included cache lets you regenerate the default study area without downloading
line data. The interactive map requires internet access for Leaflet and street tiles;
`houston_grid.svg` is an offline vector view. You can also open `houston_grid.html`
directly without running Python, with the street background disabled.

## Area and reference

Source web map supplied by the user:
https://www.arcgis.com/apps/mapviewer/index.html?webmap=5c72822e6102473f9185fc2a8fe71eb2

The script resolves the actual transmission layer from this map. At creation it was:
https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/US_Electric_Power_Transmission_Lines/FeatureServer/0

Default bounds: longitude -95.85 to -94.85, latitude 29.45 to 30.08.
This is an approximate Houston metropolitan crop chosen from the reference screenshot,
including nearby communities such as Cypress, Sugar Land, Pearland, Humble, and Baytown.
It is NOT Houston's legal city boundary, Harris County, or the complete metro region.
Source polylines are physically clipped to the rectangle, rather than merely hidden
outside the map view. Cross-boundary portions are removed from the GeoJSON and CSV
length calculation. The cache retains original source records for reproducibility.

The reference image's voltage colors are reproduced. Voltage classes are based on
source VOLT_CLASS with numeric VOLTAGE as fallback. Other includes unknown values;
negative voltage codes are not treated as real voltages. Counts describe GIS features,
not independent electrical circuits. Source status is preserved; no operating-status
filter is applied. Layer metadata and acquisition date are recorded in source_cache.json.

## Outputs

- `houston_grid.html`: interactive street map, voltage toggles, clickable attributes.
- `houston_grid.svg`: offline geographic diagram, with approximate local projection.
- `houston_lines.geojson`: clipped WGS84 line geometry and original source attributes.
- `houston_lines.csv`: line attributes and approximate clipped route lengths in km.
- `source_cache.json`: original source records, layer metadata, web-map configuration,
  retrieval time, and query bounds. Reuse to reproduce this snapshot.

Source fields SUB_1 and SUB_2 describe the full original line. They are not necessarily
the endpoints of the clipped geometry. Boundary cuts are artificial study boundaries,
not substations. The added boundary_cut flag identifies source lines extending outside
this rectangle. clipped_route_km is spherical geographic length, not an electrical
parameter or a substitute for surveyed conductor length.

## Change area or update source

```bash
python houston_grid.py --refresh
python houston_grid.py --bbox -95.75 29.50 -95.00 30.00
python houston_grid.py --no-browser
```

Changing bounds downloads a new snapshot. Outputs and the cache in this folder are
replaced when a new build succeeds; copy the folder first if preserving scenarios.
The downloader retrieves all matching object IDs, requests records in batches,
and checks returned IDs so a truncated server response is not silently accepted.
No API key is needed for this currently public source. If source access changes,
the existing cached default view remains available.

## Using this with your simulation

This deliverable supplies grid geography for the mapping portion of senior design.
It does NOT create a validated pandapower network or claim actual Houston power flow.
A geographic crossing does not establish an electrical connection. Source substation
names can support later matching, but are not verified bus IDs, bus arrangements,
switch states, or transformer connections. No substations have been fabricated.

Before AC power flow, create and validate a separate bus/branch model with:
- bus IDs, nominal voltages, and actual electrical connectivity;
- positive-sequence line resistance, reactance, capacitance, and thermal ratings;
- transformers, taps, switching status, and voltage control;
- generator/slack models and P/Q loads;
- equivalents or defined treatment for all lines cut by the study-area boundary.

Join verified branch IDs to these GIS features for visualization. If parameters must
be estimated, label them as assumptions and validate against a benchmark separately.
A GIS map alone is insufficient to establish grid capacity or data-center impacts.

## Street-background fix

The original launcher opened a file:// page, which does not supply the web referrer
required by OpenStreetMap. This version uses a loopback HTTP server, the documented
tile hostname, and normal browser referrer/caching behavior. It does not proxy tiles
or fabricate request headers. See https://operations.osmfoundation.org/policies/tiles/.

If tiles remain blocked by your network or browser settings, uncheck Street background.
City labels and all grid features remain usable. Tile load errors automatically turn
off the background; a provider error image delivered as a successful image may need
the manual toggle. No street tiles are downloaded into the package.

## Data-center overlay added

48 directory listings are shown at 33 approximate address markers. Hover/click a purple
marker or choose a name from Find a data center. 22 out-of-area listings and one
unresolved location are omitted. See DATA_CENTER_LOCATIONS.md and
data_centers_excluded.csv for every exclusion and source address.

Names and addresses: https://www.datacentermap.com/usa/texas/houston/
Coordinates: U.S. Census address geocoder. Locations are approximate, not surveyed.
No electrical values or grid connections are assigned to data centers.
