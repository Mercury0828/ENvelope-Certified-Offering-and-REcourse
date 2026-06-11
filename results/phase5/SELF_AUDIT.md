# Phase 5 — SELF AUDIT (2026-06-10)

## What was built

- `src/encore/market/portfolio.py` — B5 ideal battery (energy/power-limited, round-trip
  η, annualized matched-band capex) and B6 capped workload curtailment (linear
  opportunity cost), per guide §7's deliberately simple comparison models;
  `config/market.yaml` holds every parameter with [est] tags.
- `src/encore/data/residuals.py` — REAL disturbance records: Google-trace heat
  residuals vs hour-of-day climatology (forecast-skill candidates measured, best kept)
  + NWP-skill dew residual model (D-042, incl. the double-scaling bug caught and the
  persistence-strawman rejection). W(c) refit on 743 real records (conformal k-NN,
  k = 80 / k_cal = 150 for the smaller pool). Simulation hours REPLAY real trace
  step-vectors.
- Readiness wiring (D-041 resolution): certified commitments now carry the R(q)
  polygon terminal with tube margins, cached per (T_dew, d, q-bucket).
- `experiments/phase5_weeks.py` — 3 real weeks × 7 days × 6 controllers × 3 seeds
  (378 controller-days), all on real ERCOT prices + real KIAH weather. Suite 51/51
  green.

## Acceptance checklist (guide §11, Phase 5)

| Criterion | Status | Evidence |
|---|---|---|
| All 6 controllers complete all weeks without crashes | **PASS** | 21 cells × 7 days × 3 seeds asserted complete per controller |
| Metric table generated | **PASS** | `metrics.csv` (per day×seed), `weekly_summary.csv` (aggregates) |
| B2 shows violations/penalties under burst days that B4 avoids | **PASS** | B2: 18 violation-days, worst **+8.74 K** over T_max; B4: **zero violations** in all 189 simulated days (asserted) |
| B4 profit ≥ B1 | **PASS** (asserted per week) | mild +$0.0 (rationally sits out), humid +$0.4, scarcity **+$24.6/day** |
| Showable-artifact milestone #2 | **PASS** | `artifacts/encore_phase5_artifact.zip` + tag `phase5-done` |

## Weekly summary (market value vs B1, $/day, 3-seed mean)

| | mild | humid | scarcity (Heather) | violations (worst) |
|---|---|---|---|---|
| B2 no-certificate | 2.6 | 492.3 | 155.6 | **8.74 K, 18 days** |
| B3 SAA | 0.5 | 78.1 | 37.4 | 0 (no guarantee — luck at 3 seeds) |
| **B4 ENCORE** | 0.0 | 0.4 | **24.6** | **0** |
| B5 battery | −4.1 | 270.6 | 75.4 | n/a |
| B6 curtailment | 4.1 | 584.7 | 164.1 | n/a (QoS cost modeled as $ only) |

Proto-F2 (`proto_F2.*`): B2 isolated on the violation axis; B4 is the only
thermal-side participant with revenue at zero violations.

## Honest notes / open risks

- **The Borg-2019 cell is brutally volatile at hall scale (~±25%/h)**, and hour-of-day
  is our only day-ahead context feature so far → certified offers concentrate in
  low-volatility daytime hours and B4's absolute $ are small. This is a property of
  the workload + context poverty, reported as such (guide §8 honest-result clause).
  Phase 6 levers, all guide-sanctioned: richer c (recent-residual regimes, job-mix
  share — guide 6.2 lists them), steadier dedicated-training halls as a sensitivity,
  concurrency-corrected burst statistics.
- **B6 dominating in $$ is the expected guide-2.2 story** (compute flexibility is
  deeper) — but its QoS cost is a single [est] $/MWh knob and it carries zero modeled
  risk; F2's point is the zero-QoS first tranche, not beating B6 in $.
- **B5's mild-week loss** (capex not recovered at low prices) is the matched-capex
  comparison working as intended.
- B4 had 9 infeasible event starts across 189 days (consecutive activations from
  warm states); the D-1-plan fallback absorbed all of them with zero violations and
  0.5 kWh average shortfall in the scarcity week (penalty $0.05/day ≪ ε budget).
- B3's zero violations at 3 seeds is sampling luck (its box is an empirical max of 20
  draws); Phase 6's 20+ seeds is where its tail shows.
- Trace/price alignment remains hour-of-day only (trace clock unanchored) — carried
  caveat, affects realism of heat-price correlation, not the safety machinery.
