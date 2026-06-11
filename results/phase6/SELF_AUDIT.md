# Phase 6 — SELF AUDIT (C3-final, 2026-06-11; supersedes earlier versions)

Final configuration after the C3-optimization rounds (D-051/D-052), everything REAL
end-to-end: Alibaba-PAI ML-cluster trace + **causal job-aware day-ahead forecast**
(running-jobs survival + issue-day level), real ERCOT DAM/RTM/ECRS prices, real KIAH
weather with **archived NWP day-ahead dew forecasts**, 10 weeks of 2024 × 20 seeds,
certified 3-state S2 product, **nested safety/delivery conformal sets**
(ε_safe = 0.05 / ε_del = 0.3), design gain 300 kW/K, e₀ = 1.25 K
(disturbance-aware), held-out day-block validation, CRC32-deterministic seeds.
Design knobs were selected on the FIT block only; the eval block was replayed once.
Every number below is read from a named committed artifact.

## Headline results

**F1 — the value of information** (`F1_kappa.csv`, `provenance_F1.json`): on the SAME
real PAI trace, the certified S2 offer at hod 14 (dry day) is **40.7 kW with a
climatology day-ahead forecast vs 74.6 kW with the job-aware forecast (+83%)** —
day-ahead job information moves the hall along the certification wall. Wall curve
(Borg-scaled volatility axis): plateau 124.5 kW (e₀-dominated) for κ ≤ 0.4, then
92 → 50 → 0 kW at κ = 0.65/0.8/1.0.

**Main table** (`main_table_jobaware_eps03.csv`, 10 weeks × 20 seeds, ε_del = 0.3):

| | B4 (certified) | B2 (naive) | B3 (SAA) | B5 (battery) | B6 (curtail) |
|---|---|---|---|---|---|
| market value $/day/MW | **10.60** | 35.09 | 14.92 | 6.46 | 25.61 |
| committed kW/day | 54 | 388 | 126 | 616 | 333 |
| delivery ratio | 0.95 | 0.82 | 0.97 | 1.00 | 1.00 |
| violation day-seeds (of 1,400) | 10 (≤1.6 K, all beyond-W_safe) | **229 (≤9.8 K)** | 47 (≤4.9 K) | 0 | 0 |

- **Scarcity week (Heather): B4 +$97.1/day/MW with 414 kW/day committed** — value is
  scarcity-concentrated, as DR economics should be. Annualized ≈ $3.9k/MW-yr →
  ≈ $390k/yr for a 100 MW campus, with ZERO capex (B5 needs battery capex for less
  value) and zero workload impact (B6's value prices QoS damage at c_qos).
- B2 is the PRICE CEILING (~$35): no strategy can beat it at these prices. B4
  captures ~30% of it on average and near-parity in scarcity — while B2 pays with
  229 violation day-seeds up to +9.8 K and delivery ratio 0.82.

**Certificate validity** (`certificate_validity_jobaware_eps03.json`):
- **0 in-W_safe violation episodes** (the Thm-2 safety clause holds on its stated
  domain); 10 beyond-W_safe episodes in 1,400 day-seeds, all ≤ 1.57 K — the
  DVFS-backstop domain (guide 6.2), vs B2's 9.8 K.
- **0 clean-in-box delivery failures**; cold-start failure rate 0/22 (CP95 ≤ 15%);
  overall failure rate 19.7% ≤ ε_del = 0.3, all priced through γ penalties
  (B4 penalties $0.17/day avg). ε_del = 0.1 frontier point: 12.7% overall, mv $9.1.
- 100/122 warm starts (boundary commitments under e₀ drift) — covered by the
  1.25 K ball; warm-start failures (24) fall under the priced ε_del budget.

**F3** (`F3_cdeg.csv`): scarcity-day supply curve 1,368 → 498 kW (c_deg 0.5 → 50),
value $867 → $445/day; mild day exits at c_deg ≈ 20.

**Stress** (`stress_summary.csv`, deliberately beyond-box = DVFS domain): B4 bounded
≤ 2.2 K vs B2 6.9 K (burst), 0 K vs 5.1 K (consecutive), 0 K vs 4.3 K (dew shift).

## Honest notes (carried to the paper)

- Average value is PRICE-LIMITED: 2024 ERCOT capacity prices outside scarcity are a
  few $/MWh; the B2 ceiling shows this is a market fact, not a product weakness.
- The trace's summer sustained-overload hours put even the idle plant 0.25 K over
  T_max on 5 day-seeds (B4 ≡ B1 there; load-anchoring convention documented, D-050).
- ε_del = 0.3 is aggressive but penalty-backed and empirically consistent (19.7%
  observed); the ε_del = 0.1 point is reported alongside.
- The job-aware forecast uses only issue-time-known information + fit-block
  statistics; its honest ceiling on this trace is ~−19% residual energy (PAI churn
  volume is genuinely day-ahead-uncertain). Better operator job schedules would move
  the hall further along the wall (F1's arrow).
- Remaining honest levers (future): d=15 product layering, affine disturbance
  feedback, per-context gains, weather-coupled COP with priced pre-cool holding.
