# Phase 0 — SELF AUDIT (2026-06-10)

## What was built

- **Repo scaffold** per guide §12: `src/encore/{plant,envelope,tighten,control,market,data}`,
  `config/`, `experiments/`, `tests/`, `results/`, `notes/PARKING_LOT.md`,
  `DESIGN_DECISIONS.md`, `PROGRESS.md`. Environment: user-local venv `encore`
  (Python 3.12.10); numpy/scipy/pandas/cvxpy/gurobipy/matplotlib/pyyaml/pytest/
  polytope/pypoman all installed and importable. Gurobi solves a trivial LP
  (academic WLS license; `GRB_LICENSE_FILE` unset — see D-003).
- **Plant dynamics** (`src/encore/plant/dynamics.py`): 2-state (T_j, T_w) and 3-state
  (T_j, T_w, T_f) LTI models in the virtual-input form, assembled from
  `config/plant.yaml` (all parameters source-tagged), exact ZOH discretization at 30 s
  and 5 min, plus the closed-loop *physical* form (fixed ṁ/T_in, passive CDU,
  proportional chiller law) used for step-response characterization. The 3-state
  topology is the energy-consistent series arrangement (D-004).
- **Virtual input** (`virtual_input.py`): affine-in-x box bounds for q̇_ext encoding
  ṁ-range, T_in-range, the condensation floor T_in ≥ T_dew + δ_cond, and the passive
  CDU bound (3-state, D-005); minimum-pump-power map back to (ṁ, T_in) with round-trip
  consistency. No bilinear term enters any optimization-facing code.
- **Power map** (`power.py`): 3-segment convex PWA pump curve (chords of a_p·ṁ³,
  conservative upper bound, exact at breakpoints) + chiller q̇_rej/COP with COP affine
  in (T_supply − T_wb), clamped to [2, 12]. The two free COP coefficients are fitted to
  the [Gheni26] anchor (D-014) and test-guarded against the config values.
- **Simulation harness** (`simulate.py`): exact ZOH simulation with energy-balance
  bookkeeping; `simulate_affine` integrates the closed-loop form with exact state
  integrals (augmented matrix exponential), so energy books close to machine precision.
- **Experiments**: `experiments/phase0_step_response.py`,
  `experiments/phase0_supply_sweep.py`, writing plots (PDF+PNG, shared mplstyle),
  CSV tables, the source-tagged parameter table, and provenance JSONs to this directory.

## Acceptance checklist (guide §11, Phase 0)

| Criterion | Status | Evidence |
|---|---|---|
| pytest fully green | **PASS** | 33/33 tests pass (`tests/`) |
| Energy balance closes < 1% | **PASS** | closure ~1e-16 (machine precision), `energy_closure.csv`; steady-state and transient tests in `tests/test_energy_balance.py` |
| Loop time constant 5–20 min | **PASS** | 7.95 min (2-state), 5.25 min (3-state), `time_constants.csv` |
| Facility loop 20–60 min | **PASS** | 50.5 min (3-state) |
| T_j lump fast relative to loop | **PASS** | 0.40 min ≈ 24 s, < 8% of loop constant |
| 17→25 °C sweep cuts cooling power by tens of % (40–75% band) | **PASS** | 63.3% achieved (fit targets the [Gheni26] 63.3% anchor); fitted c0 = 1.4027577, c1 = 0.7986212 /K |
| Plots + parameter table with source tags in results/phase0/ | **PASS** | `step_responses.{pdf,png}`, `supply_sweep.{pdf,png}`, `parameter_table.{csv,md}` |

## Deviations / decisions logged (see DESIGN_DECISIONS.md)

- D-001 declined unvetted third-party skill download (security).
- D-002 Python 3.12 installed via py launcher (machine had 3.11 only).
- D-003 Gurobi license found via default WLS path, not `GRB_LICENSE_FILE`.
- D-004 3-state topology made energy-consistent; guide's literal h_wf sign anti-physical;
  closed-loop physical form recovers the guide's h_wf structure with h_wf = ṁc_p.
- D-013 2-state model confirmed as the envelope default (guide 6.1 "decide in Phase 0").
- D-014 COP fit anchored at COP(17 °C) = 3.0 [est]; reproduces the Gheni trend exactly by
  construction — the *fit* is calibration, the acceptance band 40–75% is the sanity check.
- D-015 SI units internally; D-016 ṁ_nom = 14 kg/s so all step-response modes land inside
  the guide's bands (C_w already at the top of its allowed range).

## Open risks / honest notes

- **Calibration circularity:** the supply-sweep "experiment" reproduces 63.3% because the
  COP coefficients are fitted to that target; the genuine content is that a *plausible*
  COP line (3.0 → 9.4 over 2–10 K of lift) and a ~25 kW pump achieve it. Real validation
  needs the actual Gheni curve shape (Phase 7 citation check) or plant data.
- **Effective-COP model is crude** at small (T_supply − T_wb): clamped at 2.0; humid-day
  COP realism is parked (PARKING_LOT) and matters for Phase 3.
- **Time constants are flow-dependent;** bands verified at nominal flow. At ṁ_min the
  loop slows to ~26 min (acceptable physically, outside the nominal band — not asserted).
- A few config entries whose values come straight from guide §6.1 ranges are tagged with
  the guide reference in comments rather than [est]; the tag convention covers numeric
  estimates, which are all tagged.
- The zero eigenvalue of the *virtual-input-form* A matrix (energy conservation mode) is
  inherent; stability statements refer to the closed-loop physical form.
