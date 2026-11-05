# Model and data assumptions

This local desktop-browser prototype is a representative steady-state study, not a reconstruction of ERCOT or real-time monitoring.

- HIFLD/FEMA Region 6 transmission shapes are geographic context only. Raw ArcGIS responses and metadata are retained under `data/raw`. Substation names from line endpoints are candidates, not verified electrical connections.
- Public substation coordinates anchor model bus positions. The bundled snapshot uses the ArcGIS Electric_Substations fallback because three Overpass services returned HTTP 406/429 on 2026-10-12. Actual substation equipment, bus voltages, ratings, and connectivity are not established by those coordinates. Future OSM data must be attributed to OpenStreetMap contributors under ODbL 1.0.
- The generated model uses 15 assumed 138 kV buses, three 345 kV buses, a synthetic ring with chords, three transformers, and one ideal 1.02 pu source. No HIFLD route has been validated as a model branch: `geometry_source_id` is null.
- Line resistance 0.05 ohm/km, reactance 0.40 ohm/km, zero capacitance, and 1 kA rating are inherited from V4's illustrative assumptions at both voltage levels. Length is great-circle distance times an assumed 1.2 routing factor, minimum 0.1 km.
- Transformer assumptions: 600 MVA, 345/138 kV, 12% short-circuit impedance, 0.3% resistive impedance, zero no-load loss/current and phase shift. These are synthetic study parameters, not equipment data.
- Every seeded facility has assumed 30 MW gross demand and 0.95 lagging power factor. OSM records establish mapped locations only. Synthetic placeholder facilities are labeled explicitly when needed to reach ten facilities.
- All ten facilities in the bundled snapshot are explicitly synthetic placeholders because OSM facility retrieval was unavailable. No real data-center identification is claimed.
- Onsite generation is unknown and assumed inactive (0 MW). When enabled, it supplies real power at unity power factor: Q remains gross facility MW × tan(acos(PF)). Net real demand equals gross demand minus onsite generation; export is possible when generation exceeds demand.
- Disconnecting a facility disconnects its load and its onsite generator. A load sweep scales gross P and Q from 0 to 150%; onsite generation is held fixed.
- Limits: bus voltage 0.95–1.05 pu inclusive, line/transformer loading up to 100% inclusive. A line at exactly 100% is at its limit, not above it.
- A converged solution may contain unsupplied islands; these buses have null voltage and are explicitly flagged. Solver failures have no valid current numerical results.
- Fault analysis is not implemented; transient response, protection, and SSO are outside this prototype.

Geographic sources retain source URLs and retrieval dates. Refresh with the scripts documented in README; do not manually modify raw downloads. Model records reference this assumptions document. UI edits are user study assumptions and remain attached to exported run inputs.
