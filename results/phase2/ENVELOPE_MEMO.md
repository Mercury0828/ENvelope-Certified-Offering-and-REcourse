# Phase 2 — ENVELOPE MEMO (GO/NO-GO gate #2: the geometric route, risk R1)

**Date:** 2026-06-10 · **Inputs:** `config/plant.yaml` (unchanged since Phase 0) ·
**Code:** `src/encore/envelope/{reachability,geometry,readiness,virtual_battery}.py` ·
**Experiments:** `experiments/phase2_envelope_{xval,geometry}.py` ·
**Artifacts:** `envelope_slices.*`, `envelope_vs_dewpoint.*`, `readiness_sets.*`,
`vb_vs_lp_frontier.*`, `xval_summary.json`, `xval_mismatches.csv`, `vb_consistency.csv`,
provenance JSONs.

**Question (R1).** Does the virtual-input polytope route work — is the deliverable set
computable as exact polytope geometry, without the lossy sampling + ML-surrogate
fallback? **Answer: yes, cleanly. Verdict at the end: GO.**

## 1. What was built

The one-hour deliverability condition of guide 6.3 (safety throughout, cumulative
delivery ≥ r·q·ΔH over the activation window, terminal readiness) is assembled as a
single polyhedron in z = (x₀, q, u₀…u₁₁) with states eliminated through the exact
ZOH dynamics (`reachability.py`). Everything downstream is linear algebra:

- **F(x, c) = max deliverable q:** one LP (~3 ms). Membership is monotone in q
  (verified: single threshold on 40-point scans, zero violations).
- **Fixed-q slices** of the deliverable set in the (T_j, T_w) plane: exact 2-D
  projections (Bretl–Lall via pypoman, D-022), tabulated over a (d × T_dew × q) grid =
  the guide-6.3 runtime lookup with conservative nearest-neighbor snapping off-grid.
  1,500 polygons build in ~5 s.
- **Readiness sets** R(q, d): fixed-point iteration R_{k+1} = proj_x{deliverable with
  x_N ∈ R_k} from the safety box — converges in **2 iterations** (support-gap 0 to
  machine precision); replaces the slides' quadratic terminal penalty.
- **Virtual battery (Thm-1 payload):** closed forms for E_cap(c), P_max(x), P_chg(x,c),
  α(c) in plant parameters and context (`virtual_battery.py`).

The 3-state (S2) envelope uses the same lifted machinery via direct LP; its exact
projection is not needed because the lifted form embeds directly into the D-1 offering
problem (Phase 4) as constraints — no projection step, no approximation.

## 2. Cross-validation (the R1 evidence; acceptance ≥98% on ≥2,000 points)

| Layer | What it tests | n | Agreement |
|---|---|---|---|
| A — projection exactness | polygon membership vs direct feasibility LP, on-grid (q, T_dew) | 1,200 | **100.00%** |
| B — tabulated runtime object | continuum (x, q, T_dew) with conservative snapping vs LP | 1,200 | **99.00%**, all 12 mismatches conservative-direction; **0 anti-conservative** |
| C — physical re-simulation | optimal trajectories at q = F(x)−ε re-run at 30 s | 200+200 | 5-min marks match LP states to 1e-6; worst intra-step excursion **+0.36 K** (2-state) / **+0.39 K** (3-state) above T_max |

Total membership points 2,400, overall agreement **99.5%** ≥ 98%. The guide's R1
detection threshold (<95% agreement → fall back to sampling+surrogate) is nowhere near
triggered: the geometry is *exact* where it claims to be exact, and the only mismatches
are the designed conservatism of grid snapping (mean snap loss ~½ grid spacing in q).

The +0.4 K intra-step excursion is a real (small) continuous-time effect of enforcing
constraints at 5-min marks; it is bounded and one-sided — fold a ~0.5 K margin into the
Phase-3 tube tightening (noted in PARKING_LOT; conservative direction available).

## 3. The envelope object (headline numbers, 2-state, 1-h horizon, cumulative delivery)

- F(x_nominal, dry, d=30) = **66.1 kW** (23% of P_base); pre-cooled dry **92.7 kW**.
- **Weather coupling lives in the ready state and the capacity, not the nominal
  discharge:** F from the *nominal* start is flat in T_dew (the condensation floor only
  binds when cold), while the *pre-cooled* frontier falls from 92.7 kW (dew ≤ 16 °C) to
  62.3 kW (dew 24 °C) at d = 30 — see `envelope_vs_dewpoint.*`. This sharpens the paper
  story: dew point gates how much coolth you can *bank*, i.e. E_cap and the readiness
  set, exactly the "battery whose capacity depends on the weather".
- Readiness: the nominal operating state is inside R∞ for committed offers of 50 and
  65 kW at d = 30 (hour-after-hour deliverability); R∞ shrinks with q (area 2,113 →
  1,867 K² from 50 → 65 kW).

## 4. Virtual-battery equivalence (Thm-1 numerical evidence)

Closed forms track the LP frontier with **median |error| 0.9%, worst 2.7%** over
d ∈ [15, 60] min × {dry, humid} × {nominal, pre-cooled} × {2-state, 3-state}
(`vb_consistency.csv`, overlay figure `vb_vs_lp_frontier.*`):

- **E_cap:** 45.0 kWh of deliverable cut (dry) vs 33.6 kWh (humid) per MW IT (2-state)
  — capacity drops 25% from dew 15 → 22 °C, linearly via T_w_lo(T_dew).
- **P_max:** chiller share (263 kW) minus the forced-extraction penalty once
  T_w > T_in,max (the short-duration binding mechanism found in Phase 1, now in closed
  form).
- **α (leakage analog):** holding 1 K of pre-cool costs ≈ **55 kW** of extra chiller
  power at this operating point (affine-COP slope at low lift) — zero inside the
  frozen-COP certification surrogate, but economically first-order for the D-1 layer:
  pre-cooling buys frontier but is *expensive to hold*. This is the battery's real
  self-discharge and goes into the Phase-4 cost model.

The deliverable set is a polyhedron by construction (projection of a polyhedron), F is
its support-style value function — concave piecewise-affine in x along monotone
directions; the Thm-1 proof skeleton (projection + explicit VB construction) now has a
numerically verified target ≤3% off the exact LP geometry.

## 5. Gate verdict (R1 decision)

**GO — adopt the geometric route.** Grounds: exact-projection agreement 100%, overall
≥99.5% (bar: 98%), zero anti-conservative errors, all degenerate/empty cells handled
explicitly (526 of 1,500 grid cells are legitimately empty deep-q × humid combinations),
single-envelope computation seconds-fast (bar: minutes). The sampling+ML-surrogate
fallback (Plan B of R1) is retired. Phase 3 should proceed on this representation:
2-state polygons/tabulation as the certified object, lifted-LP embedding for the
3-state product envelope inside D-1.

## Caveats

1. Cross-validation layers A/B validate the *projection/tabulation* step against the
   same lifted polyhedron; the non-circular physics check is layer C (re-simulation),
   which passed with the +0.4 K intra-step caveat above.
2. Readiness iteration is exact for the 2-state model; the 3-state product will use
   box terminal sets inside the lifted LP until Phase 4 decides whether more is needed.
3. All Phase-1 conservatisms (frozen COP, pump at nominal, T_wb fixed) carry over
   unchanged (D-006/D-007); they understate the envelope.
