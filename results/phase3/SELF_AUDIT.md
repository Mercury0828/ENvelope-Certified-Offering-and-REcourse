# Phase 3 — SELF AUDIT (2026-06-10)

## What was built

- `src/encore/data/synthetic.py` — seeded synthetic contextual disturbance ground truth
  (context = hour / burst-share / dew forecast / humidity regime; per-step heat
  deviations with short bursts + hourly dew residuals), standing in for real data
  (D-025; swap-in path documented in `data/DATA_REQUEST.md`).
- `src/encore/tighten/quantile_boxes.py` — k-NN conditional disturbance sets W(c) with
  **localized split-conformal calibration** (per-face, Bonferroni; D-033 inside D-031's
  entry). W(c) is a **budget polytope**: per-step amplitude bound + positive-energy
  budget + dew bound (D-031).
- `src/encore/tighten/tube.py` — fixed-gain (LQR, authority swept {10,20,50,100} kW/K)
  tube margins as the exact support function of the budget polytope (greedy closed
  form); margins enter every row of the lifted envelope via `build_lifted(..., tube=)`.
- `src/encore/control/fallback.py` — the certificate = feasibility of the tightened LP
  (D-028); policy simulation against realized disturbances with physical input clipping.
- `src/encore/control/mpc.py` — cheap deterministic suffix-LP MPC carrying the same
  margins indexed by prediction depth (recursive feasibility by construction, D-032),
  L1-tracking the certified plan, permanent fallback switch on infeasibility.
- `experiments/phase3_tightening.py` — coverage validation, proto-F1, 500-scenario
  held-out validation per bin, worst-case injections. 47/47 tests green.

## Acceptance checklist (guide §11, Phase 3)

| Criterion | Status | Evidence |
|---|---|---|
| ≥500 held-out scenarios per context bin: zero safety violations inside F̃ | **PASS** (certifiable bins) | dry-calm & dry-bursty: 0 in-box violations / 500 scenarios × 2 policies (`validation.csv`); humid bins have empty F̃ — explicitly recorded as "no certifiable offer", see honest notes |
| Empirical delivery-failure rate ≤ ε (binomial CI reported) | **PASS** | fallback 0.0%; MPC 3.6% (CI95 hi 5.2%) vs ε = 10% |
| Fallback engages and recovers in injected worst-case runs | **PASS** | box-corner (front-loaded budget extreme point): 0 violations + delivery OK in both bins; 1.5× beyond-box: MPC→fallback switch engages, hour completes |
| Conditional F̃ ⊋ unconditional F̃ (proto-F1) | **PASS, dramatically** | conditional certifies 44.6 / 20.6 kW (dry-calm / dry-bursty, ready state); the valid context-free (uniform-box) certificate is **empty in every bin**; the pooled-box comparator pretends 25.7 kW but under-covers bursty bins (0.876 / 0.845 < 0.9 → invalid), `coverage.csv` + `proto_F1.*` |

Extra: conditional-box coverage 0.88–0.95 across bins (target ≥ 0.9 − sampling tol);
MPC switch counts 27 / 91 per 500 (more switching in the bursty bin, as expected).

## Key findings (synthetic-process-dependent; real-data refit pending)

1. **A pure amplitude box is structurally useless for this product** — it emptied the
   envelope entirely (margins treat a burst bound as a persistent 1-hour load). The
   budget face (bursts are short) is what makes certification possible at all (D-031).
   This is a paper-worthy structural observation, not an implementation detail.
2. **Context value here is not "bigger boxes vs smaller boxes" but certifiable vs not:**
   context-free certification is impossible (uniform box ⇒ F̃ ≡ ∅); conditioning
   recovers 44.6 / 20.6 kW in dry contexts — the strongest possible form of F1.
3. **Humid bins are uncertifiable at d = 30, ε = 0.1 from the ready state** with this
   synthetic process (dew floor 24 °C + 2.4–2.7 K dew-residual bound + tube margins eat
   the 17.7 K-equivalent budget). This is guide-R2 honesty: the result, if it persists
   on real Houston data, IS the headline ("uncontextualized certification near-impossible
   in humid climates; context tells you when to offer").
4. **Most conservatism now sits in the delivery margin** (pricing the fixed gain's
   in-window response to disturbances). The affine disturbance-feedback upgrade (parked,
   guide 6.5) attacks exactly this term.

## Honest notes / open risks

- Numbers (44.6/20.6 kW; humid-empty) are functions of the **[est] synthetic process**
  (25%-amplitude bursts; dew σ up to ~1.4 K). They validate machinery and trends, not
  Houston economics. Real traces/weather (DATA_REQUEST) refit W(c) without code changes.
- Conformal calibration is *localized* (k-NN weighted) — approximate, validated
  empirically here (coverage table); exact finite-sample marginal guarantees would need
  full split-conformal per fixed bin (parked for Phase 6).
- Negative heat deviations carry no budget face; they only cause benign input clipping
  (more delivered cut, colder loop) — covered by validation, not by the margin calculus
  (D-031, stated in the module docstring).
- MPC's 3.6% delivery-failure rate vs fallback's 0% comes from switching mid-window
  after disturbances that the pure fallback absorbs; within ε, and Thm-3's claim
  (safety inheritance + cost) is intact, but Phase-5 closed-loop economics should watch
  whether switching is too eager (L1 tracking weight is a free knob).
- Phase-3 validation is 2-state per D-027; the 3-state product envelope gets its
  robustness treatment in the Phase-4 D-1 embedding.
