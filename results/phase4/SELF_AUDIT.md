# Phase 4 — SELF AUDIT (2026-06-10)

## What was built

- `src/encore/data/loaders.py` — real-data day loaders (ERCOT DAM/RTM/ECRS, KIAH dew).
- `src/encore/market/baseline.py` — frozen exogenous baseline (guide 5.4; flat under
  the frozen-COP surrogate, D-035 — B1 and the baseline generator coincide).
- `src/encore/market/settlement.py` — guide 5.3 symbol-for-symbol: revenue, shortfall
  s_h, penalty (γ = 2π^cap), RT cost at the cooling meter, degradation proxy; ledger
  carries every intermediate. Activated-hours-only shortfall (D-040, an edge case the
  literal formula gets wrong — fined idle plants for bursts).
- `src/encore/market/offering.py` — D-1 offering (guide 6.6): per-hour separable V1
  (D-037), objective = π^cap q − E[RT-shift (D-036) + degradation-on-plan], envelope
  constraint **by construction** (q searched over [0, F̃_h] only, re-asserted).
  Three envelope kinds: deterministic (B2), 20-scenario SAA box (B3), conformal
  certified (B4).
- `src/encore/market/dayrun.py` — 24-h day simulator with state continuity, activation
  calls, track-to-ready idle law (D-039), common random numbers across controllers.
- `experiments/phase4_one_day.py` — two real days end-to-end; tests `test_market.py`
  (suite 51/51 green).

## Acceptance checklist (guide §11, Phase 4)

| Criterion | Status | Evidence |
|---|---|---|
| End-to-end one simulated day runs B1→B4 | **PASS** (×2 days) | 2023-08-17 (humid) and 2024-01-16 (dry, Winter Storm Heather); 288 5-min steps each, all four controllers |
| Profit decomposition reconciles to the settlement formulas exactly | **PASS** | asserted < 1e-9 per controller per day in the experiment AND independently re-derived in `test_settlement_reconciles_exactly` |
| Offers respect F̃ by construction (assert in code) | **PASS** | grid limited to [0, F̃_h] + explicit assertion in `make_offers` + re-check in the experiment |

## Headline numbers (real prices, synthetic disturbances)

| | 2023-08-17 humid | 2024-01-16 dry (Heather) |
|---|---|---|
| B4 Σq / market value vs B1 | 0 kW / $0 (sits out — Phase-3 humid finding holds end-to-end) | 646 kW / **+$189**, zero penalty, zero shortfall, max T_j 79.6 ≤ 85 |
| B2 (no certificate) | +$1,147 but **T_j = 89.0 °C** (4 K violation) | +$653 but **T_j = 87.1 °C** + 1.85 kWh shortfall |
| B3 (SAA, no guarantee) | +$160, no violation (lucky day) | +$217, no violation (lucky day) |

The value-of-certification narrative (C3-i) is visible end-to-end on real prices: B2's
extra profit is purchased with safety violations; B4's certified offers are smaller but
clean; ECRS at $1,000–1,500/MWh in Heather's morning hours is exactly the price regime
where certified cooling flexibility pays.

## Deviations / honest notes

- **D-041 negative result:** a ready-state-box terminal constraint collapses F̃ to zero
  everywhere — naive return-to-start terminals kill the product; the Phase-2 readiness
  SET must be wired into committed plans (Phase 5). Until then: 2-3 infeasible event
  starts/day are handled by falling back to the D-1 plan (feedback absorbed them: zero
  violations/shortfalls for B4 on both days; counted in the ledger CSV).
- Disturbances/activations remain the seeded synthetic process; trace-residual refit of
  W(c) and trace/price alignment are Phase-5 preprocessing.
- B3's clean days here are luck, not safety — its box has no coverage guarantee; the
  Phase-5/6 Monte-Carlo (20+ seeds) is where its violation rate shows.
- T_wb stays at 22 °C (D-007); on the −13 °C-dew winter day this overstates chiller
  COP pessimistically? (COP_ref is fixed; both baseline and offers use the same map, so
  comparisons are internally consistent). Weather-coupled COP remains parked.
- Profit is negative in absolute terms for all controllers (cooling is a cost center);
  the economically meaningful quantity is market value vs B1, reported per ledger.
