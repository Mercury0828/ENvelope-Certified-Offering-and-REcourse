# PARKING_LOT.md — scope-creep quarantine

Per guide.md Section 7: any feature idea not IN-scope goes here with one line of
rationale, and stays out of the code.

- **Facility-loop condensation constraint (T_f ≥ T_dew + margin).** Guide constrains
  T_in only; cold facility piping below dew point is physically possible during deep
  pre-cool in dry weather — consider as an added state constraint in Phase 2 geometry.
- **COP coupling to weather (T_wb) across scenarios.** Held fixed in Phase 1 (D-007) to
  isolate the condensation-floor effect; belongs in the Phase-3 uncertainty/context model.
- **PWA power map in (q̇_rej, T_in) inside optimizations.** Phase 1 uses a conservative
  affine surrogate (D-006); a tighter piecewise-affine certification could widen the
  envelope in Phase 2+.
- **Pump-throttling credit during events.** Holding pump at nominal forfeits ~24 kW of
  cheap flexibility (D-006); could be added as a second (small) flexibility tranche later.
- **Pre-cooling energy cost accounting.** Phase 1 reports the frontier shift only; the
  $ cost of holding the ready state belongs to the Phase-4 settlement layer.
- **Vendor-data-based ramp limits for chillers/CDU.** Phase 1 uses 200 kW/min [est]
  (D-011); calibrate if vendor curves become available.
- **Chiller minimum-load / cycling constraints.** Real chillers have minimum stable load
  and anti-short-cycle timers; ignored in V1 plant model (would add integer variables).
- **Buffer-tank sizing optimization (S3).** S3 is sensitivity-only per guide Line-C
  caution; do not let tank sizing become a design variable.
- **Intra-step constraint margin (D-024).** ≤ +0.4 K T_j excursion between 5-min marks;
  absorb as a 0.5 K margin in Phase-3 tube tightening (do not densify the control grid).
- **Pre-cool holding cost in the offering objective.** α ≈ 55 kW per K of pre-cool at
  the nominal point (affine-COP slope); first-order for Phase-4 economics.
- **Readiness at deep commitments / short recovery.** 2-iteration convergence observed
  at q ∈ {50, 65} kW, d=30; stress at higher q and consecutive activations in Phase 3.
- **Exact 3-state (x, q) projection.** Unneeded for D-1 (lifted embedding, D-018); only
  revisit if a 3-state *certificate artifact* (printable H-rep) is ever required.
