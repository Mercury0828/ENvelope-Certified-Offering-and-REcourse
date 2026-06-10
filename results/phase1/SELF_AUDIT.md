# Phase 1 — SELF AUDIT (2026-06-10)

## What was built

- `src/encore/envelope/duration.py`: feasibility LP over the 5-min virtual-input model
  (explicit sparse constraint construction, scipy HiGHS, D-009) + bisection
  `max_sustainable_cut` (tolerance 20 W). Constraints: dynamics (exact ZOH), T_j ≤ T_max,
  T_f ≤ T_f_max, affine U(x) bounds at both step endpoints (D-010) including the
  condensation floor and the passive-CDU bound (D-005), q_rej ∈ [0, q_rej_max], ramp
  including the pre-event transition (D-011), and the conservative affine power-cut cap
  (D-006). No bilinear terms.
- `experiments/phase1_duration.py`: full grid — 3 scenarios × 2 workloads × 2 initial
  states × 2 dew points × 7 durations = 168 bisections (~2,300 LPs), with programmatic
  acceptance assertions, frontier plots (PDF+PNG), CSV, key-numbers JSON, provenance.
- 6 fast smoke tests in `tests/test_duration_lp.py` (in the green 33-test suite).
- `results/phase1/DURATION_MEMO.md` — the gate memo, verdict **GO**.

## Acceptance checklist (guide §11 + startup prompt, Phase 1)

| Criterion | Status | Evidence |
|---|---|---|
| Frontier monotone non-increasing in d, every case | **PASS** | asserted programmatically in `check_acceptance` (slack 60 W for bisection noise); experiment exits cleanly |
| Pre-cooled dominates nominal start | **PASS** | asserted programmatically, all 84 (scenario×workload×weather×d) cells |
| Humid weakly inside dry | **PASS** | asserted programmatically (structural under D-007) |
| S3 present, labeled sensitivity-only | **PASS** | panel title and memo footnote carry "sensitivity only — Line-C adjacent, not the main story" |
| DURATION_MEMO.md complete | **PASS** | frontier figure + table, plain-language reading, literature sanity check, pre-cool value, humidity effect, d* recommendation (30 min, q 15–40% of P_base), explicit GO verdict with rule |
| SELF_AUDIT.md | **PASS** | this file |

Extra (unrequired) sanity assertion also passes: burst-workload frontier weakly inside
nominal-workload frontier.

## Key numbers (drive the gate)

- Baseline cooling power 288.3 kW per MW IT (COP_ref 3.80, pump 25 kW); max possible
  instantaneous cut = chiller share = 91.3% of baseline.
- **q(d = 30 min): S1 = 22.3%** (64 kW) nominal-start dry; **S2 = 59.3%** (171 kW)
  nominal-start dry; S2 worst standard case (burst, humid) = 53.1% ≫ 20% gate bar → **GO**.
- **Value of pre-cooling at d = 30:** S1 +9.4 pct-pts (dry) but only +1.3 (humid);
  S2 +30.7 pct-pts (dry). Humid shrinks the pre-cooled S1 frontier by 8.0 pct-pts.
- Literature anchor: S1 gives 33.7% @ 20 min vs Chen et al.'s ~30% @ ~20 min — matched.

## Honest notes / open risks

- **The S2 result is strong partly by construction:** the facility loop (60 MJ/K [est])
  and T_f_max = 35 °C [est] are engineering estimates; the GO margin (53% vs 20%) is
  large enough to survive substantial parameter error (roughly: halving usable facility
  buffer scales the d=30 cut to ~35%, still GO), but C_f and T_f_max deserve priority
  in any future calibration against a real plant.
- **Short-duration frontier is set by T_in,max + minimum flow**, not by the hotspot —
  a model feature (no CDU bypass below 30% flow) that merits a sentence in the paper.
- The LP power cap freezes COP at baseline supply temperature; the certified frontier is
  conservative (D-006). Not a risk to GO — it understates capability.
- Open-loop with known disturbances: Phases 2–3 (geometry, tightening, recourse) will
  shrink these frontiers; the gate rule anticipated that by setting the bar at 15–20%.
- Burst overlay is synthetic (+20% squares, D-008), pending trace-derived tail
  quantiles in Phase 3.

## Logged this phase

- No new DESIGN_DECISIONS entries beyond D-001..D-016 (all Phase-1-relevant decisions
  D-005..D-012 were logged when the modules were designed).
- PARKING_LOT unchanged except items already filed (facility-loop condensation bound,
  pre-cool cost accounting, PWA power refinement, pump-throttling credit).
