# Data and provenance

## Transmission routes

Source ArcGIS map: https://www.arcgis.com/home/item.html?id=5c72822e6102473f9185fc2a8fe71eb2
Layer: https://www.arcgis.com/home/item.html?id=d4090758322c4d32a4cd002ffaa0aa12
The layer is archived; its stated last data update is September 30, 2024. The cached crop contains 701 source features. The rectangle is a study boundary, not a municipal boundary. Line crossings are not assumed connected. See the source publisher's redistribution terms before publishing its data.

## Data centers

Directory: https://www.datacentermap.com/usa/texas/houston/
The source records include shared addresses, campus records and possible overlapping listings. They must not be counted automatically as separate physical loads. Supplied annotations and mapped building footprints were used for position corrections; each record retains its method and uncertainty. Purple is a display color, not a verification status. Detailed correction evidence is in LOCATION_AUDIT.json and data/processed/data_centers.json.
Building positions derived from OpenStreetMap: © OpenStreetMap contributors, ODbL, https://www.openstreetmap.org/copyright

## ERCOT buses

The supplied files are dated October 21, 2026 by filename. The statewide list contains 19,677 bus names. The Houston reference supports 337 candidate placements at 17 station references; 19,340 remain unplaced. The 138 Houston-hub entries are not a complete geographic inventory of Houston buses.
Positions come from an OSM-derived ArcGIS substation snapshot, whose currency has not been established:
https://services1.arcgis.com/lDFzr3JyGEn5Eymu/arcgis/rest/services/Open_Infrastructure_Map_Substations_Polygon/FeatureServer/40

Name/code rules are in scripts/import_ercot_buses.py. Every bus assignment is inferred and needs independent verification. Hub membership alone never assigns coordinates. Co-located buses share a substation centroid, not individual busbar coordinates. Nominal voltage is either supplied, explicitly inferred from a name, or unknown. All source IDs and evidence are preserved in processed records. No ACTIVSg2000 synthetic buses are included.

## Outputs

output/houston_grid.html is the interactive map, served by the main script on localhost. The SVG is a simplified transmission/data-center overview; it does not include the ERCOT candidate-bus overlay. CSV/GeoJSON files are regenerated when the map runs.
