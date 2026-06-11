# Phase 6 — SELF AUDIT (final, 2026-06-11; supersedes earlier versions)

Final configuration after the pre-paper audit (D-046/047/048) and the owner-approved
upgrades (D-049/050): **certified 3-state S2 product**, real Alibaba-PAI ML-cluster
trace + literature-anchored "trainhall" scenario, real day-ahead NWP dew forecasts,
10 real 2024 ERCOT/KIAH weeks × 20 seeds, hour-continuous simulation, held-out
day-block validation, CRC32-deterministic seeds. Every number below is read from a
named committed artifact.

## Acceptance checklist (guide §11, Phase 6)

| Criterion | Status | Evidence |
|---|---|---|
| Publication-grade figures, shared style | **PASS** | F1_context, F2_portfolio_{alibaba,trainhall}, F3_cdeg (PDF+PNG) |
| One-command regeneration + provenance | **PASS** | `make figures`; FIGURES_MANIFEST.json; bit-reproducible seeds |
| F1–F3 + main table + stress, 20+ seeds | **PASS** | 2 configs × 10 weeks × 20 seeds = 2,800 B4 controller-days |

## Headline results

**F1 — the certification wall** (`F1_kappa.csv`, `F1_dew.csv`): certified S2 offers vs
workload volatility (Borg-scaled axis): 187.7 kW (κ=0.1) → 81.0 (κ=0.5) → 36.3
(κ=0.65) → 0 (κ≥0.8), d=30, dry. **Both real public traces sit at/beyond the wall**:
Borg cell-a (κ=1, short bursts) and Alibaba PAI (tail-κ≈0.77 but hourly-energy face
643 MJ vs Borg's 275 — sustained day-ahead-unforecastable load swings) certify ~0.
Panel (b): dew coupling on real NWP forecasts.

**Main table** (`main_table_{alibaba,trainhall}.csv`, 10 weeks × 20 seeds):
- **alibaba (real PAI trace):** B4 rationally commits nothing (= B1) — the honest
  public-data result. Summer weeks show 7–51 violation-days for the IDLE plant itself
  (max +4.5 K): sustained-overload hours (residuals anchored at the 1 MW nominal reach
  1.33 MW) exceed floor-limited cooling capacity in Houston summer — an
  infrastructure-sizing observation, identical across B1/B4 (D-050; the load-anchoring
  convention is a setup choice the paper must state).
- **trainhall (literature-anchored steadier-hall scenario):** B4 **+$12.5/day** market
  value averaged over all 10 weeks (92 kW/day committed; scarcity week higher),
  delivery ratio 1.00, penalties $0, **zero hotspot violations in 1,400 day-seeds**;
  B2: 245 violation-days, worst +12.9 K; B3 +$14.4 with no guarantee; B5 +$6.5
  (capex drag); B6 +$25.6 (QoS-cost knob).

**Certificate validity** (`certificate_validity_trainhall.json`): **186 obligations,
0 delivery failures of any kind** (111 warm starts — all inside the e₀ ball + sprint
recovery — 0 failed; 0 out-of-box failures; 0 clean-in-box failures). Clopper–Pearson
95% upper bound **4.8% ≤ ε = 10%**. On alibaba the gate is vacuous (0 obligations) and
stated.

**F3** (`F3_cdeg.csv`, trainhall, S2 scale): scarcity-day committed capacity falls
monotonically 1,511 → 524 kW as c_deg sweeps 0.5 → 50 $/K·h (value $916 → $554/day);
the mild day exits above c_deg ≈ 20–50.

**Stress** (`stress_summary.csv`, trainhall): B4 zero violations, zero shortfall, zero
penalties under the all-hours-burst, +3 K dew-shift and 6-hour-consecutive-call days;
B2 6.0–13.4 K violations with penalties in all three.

## Honest notes (carried to the paper)

- The trainhall configuration is a labeled SCENARIO (training power is near-constant
  in published measurements; emulated as Borg×0.5) — both real public traces defeat
  ε=0.1/d=30 certification through distinct mechanisms (bursts vs sustained swings);
  the genuine missing ingredient is operator job-schedule context (guide 6.2),
  unavailable in any public trace.
- PAI summer idle-plant violations = sustained overload under the residual-anchoring
  convention (D-042/D-050); alternative anchoring (plant rated at trace peak) is a
  listed Phase-7 setup discussion.
- Heather-week days before 2024-01-19 lack archived forecasts (obs-as-forecast
  fallback, 5 of 70 days, disclosed).
- ε = 0.05 and pre-cool-cost/weather-coupled-COP items unchanged (parked, listed).
