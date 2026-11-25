# Project V4 model assumptions

Project V4 uses the cached Houston transmission routes as its active solver
network. Geographic geometry is sourced; electrical connectivity, supply points,
equipment ratings, and operating demand remain explicit study assumptions.

- All 701 source features are retained as 702 continuous route sections. An
  initial hypothetical load tap yields 703 solver segments and 586 buses.
- Same-voltage endpoints within one meter are assumed connected. Route crossings
  and nearby endpoints at different voltages are not automatically joined. One
  route with missing voltage is assumed to be 138 kV and flagged in provenance.
- The initial graph contains 32 disconnected sections. Each has one fixed
  equivalent 1.02 pu supply, selected deterministically with a preference for a
  clipped boundary endpoint. These are not verified utility source locations.
  Sources remain saved equipment; outages never create replacement supplies.
- Line length follows the geographic path. Resistance is 0.05 ohm/km, reactance
  0.40 ohm/km, capacitance zero, and current rating 1 kA. These are demonstration
  parameters, editable in the inspector, rather than utility equipment data.
- Newly drawn connections across voltage levels use an assumed 600 MVA
  transformer: 12% short-circuit impedance, 0.3% resistance, no no-load loss or
  current, and no phase shift. Its rated voltages match its selected buses.
- Ten synthetic data centers begin at 10 MW each using previous study coordinates.
  Neither their positions nor their demand represent verified operating sites.
- New data centers connect to the nearest bus or line. A line attachment creates
  a hypothetical tap while preserving total line length and impedance. Site
  transformers and associated equipment are ideal and adequately rated; load is
  referred to the connected bus voltage and site losses are omitted.
- Data-center reactive demand uses gross MW and the entered lagging power factor.
  Onsite generation supplies real power at unity power factor. A disconnected
  site loses both load and generator service; islanded generation cannot become
  a new grid-forming source automatically.
- Runs are AC steady-state snapshots using TL_Senior_Simulation_V4.run_power_flow.
  Voltage limits are 0.95–1.05 pu; line/transformer loading above 100% is flagged.
  No geographic radius limits effects. Connected-path physics determines flow,
  redistribution, and supply. Unsupplied active loads are reported separately
  from deliberate load disconnections and from solver non-convergence.
- Baseline and scenario are independent saved input snapshots. Editing clears
  relevant current results; reopening requires recalculation. Failed runs never
  display old numerical results as if current.

This model supports exploratory comparisons. It is not a validated ERCOT/Houston
operational model and cannot establish real grid capacity or weather outcomes.
Fault studies, cascading protection trips, transients, and real-time telemetry
are outside this implementation. No AI results assistant is included.

The source URL, retrieval time, route identifiers, component counts, and unknown
voltage identifiers are retained in the model's provenance and source fields.
The previous 18-bus/25-line synthetic model remains only as a regression fixture;
its old geographic-context-only behavior does not describe Project V4.
