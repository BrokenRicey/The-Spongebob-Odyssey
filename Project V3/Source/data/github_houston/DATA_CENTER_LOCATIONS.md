# Data-center locations and exclusions

Source: https://www.datacentermap.com/usa/texas/houston/ (accessed October 12, 2026).
Coordinates: U.S. Census geocoder, Public_AR_Current benchmark, address-range matches.

The directory page contains 71 listings. This version maps 48 listings at 33 distinct
address coordinates. Campus listings, shared buildings, and possible overlapping
operator listings are preserved by name and grouped at matching coordinates. These
counts do not represent 48 unique buildings or 48 verified operating data centers.

The unchanged bounds are longitude -95.85 to -94.85, latitude 29.45 to 30.08.
22 listings are outside the default study area; 1 lacks a precise location.
Geocoded points are tested against the bounds inclusively. Some distant sites are
excluded by their listed locality because their exact street address did not geocode;
those exclusions are explicitly distinguished below. No guessed coordinates are used.

## How to use

Purple circles mark approximate street-address locations. Hover or click for the
listing names. Use Find a data center to zoom to a listing; a shared marker shows all
names at that coordinate. Show locations toggles all markers. Not mapped lists exclusions.
No loads, capacities, or electrical connections are assigned to these markers.

## Excluded listings

| Listing | Reason | Source address |
|---|---|---|
| Stream DC Houston I - The Woodlands | Geocoded address outside study boundary | 4001 Technology Forest Blvd, The Woodlands, TX 77381 |
| Serverfarm Houston Data Center HTX2 | Geocoded address outside study boundary | 28401 Betka Rd, Hockley, TX 77447 |
| Serverfarm Houston Data Center HTX1 | Geocoded address outside study boundary | 28401 Betka Rd, Hockley, TX 77447 |
| Dataprana La Marque | Outside default boundary by listed locality: La Marque; exact address not geocoded | 4995 Farm to Market Rd 1764, La Marque, TX 77568 |
| ECL TerraSite-TX1 | Directory provides only a broad area; no precise street address | within east of Houston, Texas 77028 |
| Comcast Willis | Geocoded address outside study boundary | 606 Texas State Highway 75, Willis, TX 77378 |
| Serverfarm Houston HTX Campus | Geocoded address outside study boundary | 28401 Betka Rd, Hockley, TX 77447 |
| Crusoe Port of Victoria Campus | Outside default boundary by listed locality: Victoria; exact address not geocoded | within Port of Victoria, Victoria, TX 77905 |
| Project Aggie | Outside default boundary by listed locality: College Station; exact address not geocoded | Midtown Dr & Corporate Pkwy, College Station, TX 77845 |
| JMG Data Center | Outside default boundary by listed locality: Conroe; exact address not geocoded | 100 Plantation Dr, Conroe, TX 77303 |
| Amazon AWS - Project Eagle Campus | Outside default boundary by listed locality: Boling; exact address not geocoded | 240-258 Eaglewood Rd, Boling, TX 77420 |
| Amazon AWS - Project Eagle (Bldg C) | Outside default boundary by listed locality: Boling; exact address not geocoded | 240 Eaglewood Rd, Boling, TX 77420 |
| Amazon AWS - Project Eagle (Bldg A) | Outside default boundary by listed locality: Boling; exact address not geocoded | 244 Eaglewood Rd, Boling, TX 77420 |
| Amazon AWS - Project Eagle (Bldg D) | Outside default boundary by listed locality: Boling; exact address not geocoded | 244 Eaglewood Rd, Boling, TX 77420 |
| Amazon AWS - Project Eagle (Bldg F) | Outside default boundary by listed locality: Boling; exact address not geocoded | 270 Eaglewood Dr, Boling, TX 77420 |
| Amazon AWS - Project Eagle (Bldg E) | Outside default boundary by listed locality: Boling; exact address not geocoded | 266 Eaglewood Dr, Boling, TX 77420 |
| Amazon AWS - Project Eagle (Bldg H) | Outside default boundary by listed locality: Boling; exact address not geocoded | 234 Eaglewood Dr, Boling, TX 77420 |
| Amazon AWS - Project Eagle (Bldg K) | Outside default boundary by listed locality: Boling; exact address not geocoded | 233 Eaglewood Dr, Boling, TX 77420 |
| Amazon AWS - Project Eagle (Bldg J) | Outside default boundary by listed locality: Boling; exact address not geocoded | 237 Eaglewood Dr, Boling, TX 77420 |
| Amazon AWS - Project Eagle (Bldg G) | Outside default boundary by listed locality: Boling; exact address not geocoded | 230 Eaglewood Dr, Boling, TX 77420 |
| Amazon AWS - Project Eagle (Bldg B) | Outside default boundary by listed locality: Boling; exact address not geocoded | 258 Eaglewood Rd, Boling, TX 77420 |
| Project Aggie - Building 1 | Outside default boundary by listed locality: College Station; exact address not geocoded | Midtown Dr & Corporate Pkwy, College Station, TX 77845 |
| Project Aggie - Building 2 | Outside default boundary by listed locality: College Station; exact address not geocoded | Midtown Dr & Corporate Pkwy, College Station, TX 77845 |

## Location qualifications

These are address-range geocodes, not the directory's original pin coordinates and
not surveyed facility footprints. Direct site access returned a free page-view limit;
no attempt was made to bypass it. Names and addresses were available from the public
page text. Geocoding used the separate Census service.

ECL TerraSite-TX1 is not asserted to be outside the rectangle; its directory entry is
too broad to place accurately. It is omitted as unresolved.

For campus address ranges/multiple addresses, the first street number represents the
campus listing. All such entries are flagged. Source addresses are retained alongside
normalized queries and matched addresses. Lumen Houston 1 has a ZIP inconsistency;
its normalized street matches 12001 North Fwy, ZIP 77060. Hostrunway's listing contains
a suite/mailbox number, so its marker only establishes the address location, not that
a data-center building is present. These qualifications are visible in popups.

## Files

- data_centers.json: editable master list, names, coordinates, sources, and qualifications.
- data_centers_all.csv: all listings with inclusion status.
- data_centers_excluded.csv: each excluded or unresolved listing and reason.
- data_centers.geojson: included named points for future integration.

Changing the script's bounding box rechecks all geocoded coordinates. Listings that
only have a locality-based exclusion become unresolved for a non-default boundary.
Updating the grid with --refresh does not refresh the data-center directory snapshot.
