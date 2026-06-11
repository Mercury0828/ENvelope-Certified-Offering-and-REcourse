# Phase 6 — SELF AUDIT (regenerated 2026-06-11 after the pre-paper audit; supersedes
# the 2026-06-10 version, whose closed-loop numbers predate D-046/D-047/D-048)

Every number below is read from a committed artifact in this directory (file named in
parentheses). The evidence chain is the CORRECTED one: hour-continuous state (no
teleporting), CRC32 deterministic seeds, day-block held-out replay (fit days 0–20,
eval days 21–30), causal climatology forecast, conformal W(c) with a-priori face
allocation, tube margins with the e₀ = 1.5 K warm-start ball, whole-hour settlement
certification + activation-window depth cap, adjacency-pruned commitments, sprint
recovery between events.

## Acceptance checklist (guide §11, Phase 6)

| Criterion | Status | Evidence |
|---|---|---|
| Figures publication-grade, shared style | **PASS** | F1_context, F2_portfolio_k{100,050}, F3_cdeg (PDF+PNG, encore.mplstyle) |
| Every number regenerable by one `make figures` | **PASS** | executed end-to-end post-fix; `FIGURES_MANIFEST.json`; CRC32 seeds make reruns bit-comparable |
| Provenance manifest | **PASS** | FIGURES_MANIFEST.json + per-experiment provenance JSONs |
| F1–F3 + main table + stress, 20+ seeds | **PASS** | this directory; two workload scenarios κ ∈ {1.0, 0.5} |

## Headline results

**F1 — the certification wall** (`F1_kappa.csv`, `F1_dew.csv`): at hour 14, dry day,
held-out-fit conformal W(c): the d = 30 product certifies 76.7 kW at κ = 0.1, 35.8 kW
at κ = 0.5, 3.6 kW at κ = 0.8 and **nothing at κ = 1.0** (Borg-2019 cell-a at full-hall
scale, ~±25%/h); d = 15 certifies exactly 2× throughout (energy-driven product).
Context-free certification is zero at every κ and every dew point. At κ = 0.5 the dew
wall sits near 16 °C for d = 30.

**Main table, 20 seeds × 3 real weeks** (`main_table_k050.csv` / `_k100.csv`):

| κ = 0.5 | mv $/day (±σ) | Σq kW/day | delivery ratio | penalties | viol days |
|---|---|---|---|---|---|
| B4 humid | **+40.0 ± 40.6** | 44.4 | 1.00 | 0 | **0** |
| B4 scarcity | **+34.3 ± 52.4** | 165.6 | 1.00 | 0 | **0** |
| B4 mild | +1.0 | 19.7 | 1.00 | 0 | 0 |
| B2 (no cert) humid | +243.7 | 347.9 | 0.96 | $1.40/day | **73 days, max 6.2 K** |
| B3 (SAA) humid | +74.7 | 85.8 | 1.00 | 0 | 0 (no guarantee) |

At κ = 1.0 B4 rationally commits nothing anywhere (true negative, reported); B2 still
violates on 10–75 days/week.

**Certificate validity** (`certificate_validity_k050.json`): 171 obligations on
held-out replay days — **0 delivery failures of any kind** (0 warm-start, 0
out-of-box, 0 clean-in-box); Clopper–Pearson 95% upper bound 3.85% ≤ ε = 10%. 77 of
171 events started warm (within the e₀ ball after sprint recovery) and all delivered.
Held-out joint box coverage 0.904 (target ≥ 0.90, 240 eval hours).

**F3** (`F3_cdeg.csv`, κ = 0.5): scarcity-day commitment falls monotonically
431 → 134 kW as c_deg sweeps 0.5 → 50 $/K·h (value $262 → $141/day); the mild day
exits the market above c_deg ≈ 10–20. γ ∈ {1.5,3}× moves nothing for B4 (zero in-box
penalties).

**Stress** (`stress_summary.csv`, κ = 0.5, deliberately beyond-box): B4 — zero
violations, zero shortfall, zero penalties in ALL three scenarios (all-hours top-decile
burst day, +3 K dew shift, 6-hour consecutive calls); B2 — 2.6–5.5 K violations and
penalties in all three. Graceful-degradation criterion met with margin.

## What changed since the superseded audit (D-046/D-047/D-048)

1. Hour-boundary state teleportation fixed → recovery energy and warm starts real.
2. CRC32 seeds → bit-reproducible experiments (root cause of the earlier
   audit-vs-artifact mismatch).
3. Day-block held-out replay + causal forecast → no in-sample circularity.
4. Clopper–Pearson CIs; theory-faithful certificate gates with failure attribution.
5. ε face allocation (0.45/0.45/0.10) + e₀ = 1.5 K ball (derived) in the tube.
6. **Settlement alignment**: certification now enforces BOTH the activation-window
   depth cap and the whole-hour settlement energy (guide 5.3) — window-only
   certification was anti-conservative once in-hour recovery existed.
7. **Structural finding**: the infinite-horizon readiness fixed point is EMPTY under
   whole-hour settlement (consecutive full-depth delivery is thermodynamically
   impossible) → commitments are adjacency-pruned and recovery hours use a sprint law
   (full extraction headroom, ~20 min for a 15 K excursion); terminal startability
   holds by construction.

## Honest notes / open risks

- κ = 0.5 is a labeled SCENARIO (steadier-hall reference), not a measurement: Borg
  cell-a at κ = 1 supports no certified d=30/ε=0.1 product, and the paper must lead
  with that as a finding about workload volatility, using the κ-wall as the
  requirement curve. Real dedicated-training-hall traces would replace κ.
- Warm-start coverage relies on the e₀ = 1.5 K ball + sprint recovery; the bound is
  derived from the idle law, not yet stated as a lemma — Phase-7 theory writing must
  formalize it (or condition Thm 2 explicitly).
- Dew channel remains the NWP-skill model (D-042); heat channel is real.
- ε = 0.05 certification: zero at κ ≥ 0.5 (F1_kappa.csv dashed curve) — stated.
- B5/B6 risk cells are model assumptions (render n/a); B3's clean weeks are luck, not
  guarantee; B2's mv remains inadmissible-by-safety.
- 2-state certified product (D-027); S2/3-state numbers are deterministic capability.
