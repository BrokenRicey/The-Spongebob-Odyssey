# Houston Grid Map

Run `python houston_grid.py` in this folder (or run houston_grid.py in PyCharm). The map opens in your browser. Keep Python running; stop it with Ctrl+C or PyCharm Stop. Python 3.10 or later is required. No pip packages are needed. Street tiles and Leaflet require internet access.

## Files

| Location | Contents |
|---|---|
| houston_grid.py | Main map program — run this file |
| data/source/ | ERCOT source CSVs, substation reference polygons, cached transmission data |
| data/processed/ | Data-center positions and inferred ERCOT bus-location records |
| scripts/ | Script to rebuild the ERCOT bus-name matches |
| docs/ | Source notes and data-center correction history |
| output/ | Generated interactive map, SVG, CSV and GeoJSON exports |

Purple dots show data-center listings. Teal dots show approximate locations for ERCOT bus-name candidates. Nearby data-center dots group at distant zoom. Search a data center or placed bus using the sidebar dropdowns.

To rebuild the bus matching, run `python scripts/import_ercot_buses.py`, then run the map again. The included processed data is ready to use; rebuilding is optional.

The map is a geographic visualization. Bus-to-substation assignments remain inferred; the transmission-line routes do not establish verified electrical connectivity. Read docs/DATA_NOTES.md before using the data in engineering calculations.

All power-simulation code, pages, API routes, test results and package requirements have been removed from this map-only package.
