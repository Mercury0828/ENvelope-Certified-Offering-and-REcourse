# Phase 2 — SELF AUDIT (2026-06-10)

## What was built

- `src/encore/envelope/reachability.py` — the lifted deliverability polyhedron
  Gz ≤ h in z = (x₀, q, u₀…u₁₁): one-hour horizon, activation window r = d/60,
  cumulative delivery (D-019), U(x) at both endpoints, terminal-set hook, operating
  box (D-021). Generic in n_states ∈ {2, 3}.
- `src/encore/envelope/geometry.py` — F(x,c) by direct LP; brute-force membership;
  trajectory extraction; exact Bretl–Lall fixed-q slices (D-022); `TabulatedEnvelope`
  runtime lookup with conservative off-grid snapping (guide 6.3).
- `src/encore/envelope/readiness.py` — readiness fixed-point iteration (2-state exact).
- `src/encore/envelope/virtual_battery.py` — closed-form E_cap/P_max/P_chg/α + frontier
  predictor.
- Experiments `phase2_envelope_xval.py` (3-layer cross-validation) and
  `phase2_envelope_geometry.py` (slices, dew sweep, readiness, VB consistency).
- 8 new tests (`tests/test_envelope_geometry.py`); suite now 41 green.
- `ENVELOPE_MEMO.md` (gate verdict **GO** on the geometric route) + `WALKTHROUGH.md`
  (showable-artifact milestone).

## Acceptance checklist (guide §11, Phase 2)

| Criterion | Status | Evidence |
|---|---|---|
| Cross-validation vs brute force, ≥2,000 (x,q,c) points, ≥98% agreement | **PASS** | 2,400 points: layer A 100.00%, layer B 99.00% (0 anti-conservative), overall 99.5% — `xval_summary.json`; mismatches analyzed in memo §2 |
| Mismatches analyzed in memo | **PASS** | all 12 are conservative grid-snapping; `xval_mismatches.csv` |
| Monotonicity of F in q verified numerically | **PASS** | single-threshold membership scans (test + experiment), 0 violations |
| VB closed-form vs polytope consistency | **PASS** | median 0.9%, worst 2.7% (d ≥ 15) across 48 cells; `vb_consistency.csv`, overlay figure |
| Envelope shrinks monotonically as T_dew rises (plot) | **PASS** | `envelope_vs_dewpoint.*`, asserted at 15 dew points × 3 d × 2 starts; nominal-start F is *flat* (floor inactive when discharging from nominal) — weakly monotone, discussed in memo §3 |
| ENVELOPE_MEMO.md with GO/NO-GO on geometric route (R1) | **PASS** | verdict **GO** |
| STOP after the memo | **PASS** | Phase 3 not started |
| Showable artifact (tag + zip + WALKTHROUGH) | **PREPARED** | WALKTHROUGH.md + zip built; final `phase2-done` tag awaits owner GO at this gate |

## Deviations / decisions logged

D-018 (geometric-route division: 2-state exact projections + tabulation; 3-state via
lifted-LP embedding), D-019 (cumulative delivery over the activation window), D-020
(activation = first r·N steps, r = d/60 default), D-021 (operating box, first input
ramp-free), D-022 (pypoman Bretl–Lall + dummy-equality; pycddlib as backup — the §12
"pick the polytope library" decision), D-023 (three-layer cross-validation design,
knife-edge exclusion), D-024 (intra-step excursion finding → 0.5 K margin for Phase 3).

## Honest notes / open risks

- **Layers A/B are geometry-vs-LP on the same polyhedron** (they validate projection
  and tabulation, which is what R1 asks); the physics check is layer C plus the exact
  agreement with the independently-coded Phase-1 bisection (64.30 ≡ 64.30 kW,
  171.0 ≡ 171.0 kW).
- **Intra-step constraint excursion up to +0.39 K** between 5-min marks (layer C):
  bounded, one-sided, absorbable in Phase-3 tube margins (logged, parked).
- **Readiness converges in 2 iterations** — suspiciously fast but explainable: the
  1-hour deliverable projection is already nearly invariant (recovery to the safety box
  within one hour is easy at these q levels). Re-examine at deeper q / shorter recovery
  in Phase 3 stress tests.
- **α (hold-cost) ≈ 55 kW/K** of pre-cool is large; pre-cooling economics will bite in
  Phase 4 — the frontier value of pre-cooling (Phase 1) is not free.
- The 526 empty tabulation cells concentrate where humid × deep-q: expected physics,
  but they make F1 (value-of-context) likely dramatic — keep an eye on R2 (envelope
  near-empty in humid weeks) when real Houston data arrives in Phase 3.
