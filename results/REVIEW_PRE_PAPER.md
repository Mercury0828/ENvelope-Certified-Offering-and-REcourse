# REVIEW_PRE_PAPER — comprehensive pre-paper audit of the experimental results
**Date:** 2026-06-11 · **Method:** one-shot clean-context adversarial review (subagent
with no prior context) + independent numeric cross-checks + fix-and-revalidate cycle.
All findings were verified against source/artifacts before acting; every fix is logged
(D-046, D-047, D-048) and the full Phase-6 evidence chain was regenerated.

## Verdict

The geometry/theory layer (Phases 1–2) was sound from the start. The closed-loop
evidence chain (Phases 5–6) contained **one critical simulation bug, one critical
reproducibility bug, one validation circularity, and one product-semantics
misalignment** — all caught by this audit, all fixed, and the corrected chain now
validates end-to-end: **0/171 delivery failures (CP95 ≤ 3.85%, ε = 10%), zero hotspot
violations, held-out coverage 0.904, bit-reproducible runs.** The headline numbers
changed materially (mostly became MORE interesting); no paper text existed yet, so
nothing has to be retracted. The results are now reasonable, expectation-consistent,
and rigorous within explicitly stated scope; remaining improvements are listed last.

## 1. Findings triage (clean-context reviewer A/B/C + own checks)

### Fixed (code + rerun)
| # | Finding | Verification | Fix |
|---|---|---|---|
| A1 | **State teleportation at hour boundaries** — idle hours reset to target steady state; infeasible event starts granted the ready state free; recovery energy never paid (negative `rebound_usd` artifact) | confirmed in `fallback.py`/`dayrun.py` | `simulate_policy(x0=carried)`; every hour starts from the true state (D-046) |
| A2 | Self-audit quoted stress numbers absent from artifacts | root-caused: `hash()` is **salted per process** → all week/stress seeds were non-reproducible across runs | CRC32 `stable_seed`; audits regenerated from artifacts only (D-046) |
| A3/A4 | Bogus "binomial CI" formula; vacuous validity assertion | confirmed (0/500 → "CI" 2.8e-6) | exact Clopper–Pearson everywhere; theory-faithful gates (D-046) |
| B1/B2 | In-sample certificate validation; look-ahead climatology forecast | confirmed | day-block split (fit 0–20 / eval 21–30) + causal climatology (D-046) |
| A8 | Conformal under-coverage in the binding bin (0.882) | reproduced on real data (0.883 held-out) | a-priori ε face allocation 0.45/0.45/0.10 → held-out joint coverage **0.904** (D-047) |
| B5 | Thm-2 assumes e₀ = 0; simulator didn't guarantee it | confirmed; first corrected run: 27% failures, mostly warm starts | e₀ = 1.5 K ball in tube margins (bound derived from idle-law convergence) + failure attribution gates (D-047) |
| NEW | **Settlement misalignment** (found by the corrected chain, not the reviewer): LP certified delivery over the activation window; guide 5.3 settles the WHOLE hour — in-hour recovery cancels delivered energy → 87 "in-box" failures | reproduced, root-caused | certification = window depth cap AND whole-hour energy (D-048) |
| NEW | **Readiness fixed point is empty under whole-hour settlement** (consecutive full-depth delivery thermodynamically impossible) | proven by iteration collapse | adjacency-pruned commitments + sprint recovery law (~20 min per 15 K); terminal startability by construction; R₁ kept as the startable-set object (D-048) |
| A5 | MPC internal delivery ledger uses planned (pre-clip) input | confirmed | accepted, documented in `mpc.py` (settlement uses realized power; only steering drifts) |
| C-class | F3 mathtext mangling; zero-variance cells unexplained; B5/B6 "0-risk" cells | confirmed | fixed label; cells explained/n-a'd in audit |

### Accepted with explicit statement (paper must carry these)
- **B10 — product scope**: the certified closed-loop product is the **2-state
  coolant-loop tranche**; Phase-1's S2 gate numbers (171 kW @ 30 min) are deterministic
  capability of the 3-state plant. Either extend tube margins to n = 3 (est. 1–2 days:
  margins are generic, needs the 2-input feedback term) or scope the claim. **Owner
  decision for Phase 7.**
- **B3 — dew channel is a model** (N(0, 1.2 K) NWP-skill, D-042): KIAH observations
  cannot reconstruct a DA forecast; archived NWP forecasts would replace it (listed).
- **B12 — trace clock unanchored to prices** (hour-of-day pairing only).
- **B8 — F1's uniform comparator** is one valid context-free construction, not a
  proven minimum; phrased accordingly.
- **B9 — ε = 0.05 certifies nothing at κ ≥ 0.5**: stated, dashed line stays in F1.
- **D-043 — recent-residual regime context is non-informative on Borg-2019**
  (corr ≤ 0.08): the genuine context enrichment is operator job-schedule data.

### Cross-checks that PASSED unchanged (reconciliations, report-ready)
- VB closed form ↔ Phase-1 frontier: E_cap(dry) 45.0 kWh ⇒ 90.1 kW @ 30 min vs LP
  91.3 kW (1.3%); Phase-2 3-state LP ≡ Phase-1 S2 (171.0 ≡ 171.0).
- Phase-2 cross-validation layers (projection exactness 100.00%) — definitionally
  independent of the delivery-semantics change.
- Implied capacity prices in revenue ≈ q-weighted ECRS, consistent with offers
  concentrating on price spikes; raw value distributions irregular (no fabrication
  signature); identical-violation cells traced to shared exogenous tail days.

## 2. The corrected headline results (artifacts in results/phase6/)

1. **The certification wall (F1)**: certified d=30 offers exist only below ~80% of
   Borg-cell-a volatility (35.8 kW per MW IT at κ = 0.5, dry); d = 15 doubles it;
   context-free certification is zero everywhere. Weather coupling (dew wall ~16 °C at
   κ = 0.5) survives.
2. **Closed loop (κ = 0.5 scenario, 3 real ERCOT/KIAH weeks × 20 seeds)**: B4 earns
   +$40.0/day (humid) and +$34.3/day (Heather scarcity) per MW IT with delivery ratio
   1.00, zero violations, zero penalties; uncertified B2 earns more but violates
   T_max on 10–75 days/week (up to 6.3 K). At κ = 1 B4 rationally abstains — the
   honest-result clause finding.
3. **Certificate validity**: 0/171 held-out obligations failed; CP95 ≤ 3.85% vs
   ε = 10%; 77 warm starts all covered by the e₀-ball + sprint recovery.
4. **F3**: degradation supply curve 431 → 134 kW over two decades of c_deg.
5. **Stress**: B4 zero violations/shortfall/penalties under all-burst, +3 K dew-shift
   and consecutive-call days; B2 2.6–5.5 K violations throughout.

## 3. Remaining improvement backlog (ranked, with effort)

1. **3-state tube margins** → certify the S2 product the gate approved (1–2 days;
   biggest claim-strength gain). Owner call.
2. **Pre-positioning lemma** for the e₀ ball + sprint law (theory writing, Phase 7).
3. **More obligations** for tighter validity CIs: extend to 10+ weeks (compute only).
4. **Real DA dew forecasts** (archived NWP) to replace the [est] 1.2 K model.
5. **Real steadier-hall trace** to replace κ as a scenario knob.
6. **Weather-coupled COP + priced pre-cool holding** (un-park D-007/α): currently the
   economics are internally consistent but plant efficiency is weather-flat.
7. Conformal per-bin calibration with finite-sample marginal guarantees (replaces the
   localized approximation; PARKING_LOT).
8. Warm-start sub-classification (|e₀| ≤ ball vs beyond) in attribution — cosmetic now
   (0 failures) but sharpens the Thm-2 statement.
9. Peak-channel concurrency correction for burst overlays (data/README caveat).
10. B6 opportunity-cost sweep (honesty knob for F2).

## 3b. Owner-approved backlog — RESOLUTION (2026-06-11, D-049/D-050)

1. **3-state tube margins — DONE**: the certified product is now the gate-approved S2
   facility-loop tranche (2×3 LQR gain, per-channel margins, CDU/q_rej row tightening);
   closed-loop chain, offering and stress all run on it. B10 retired.
2. **Real training-hall trace — DONE, with a finding**: Alibaba PAI GPU-2020 acquired
   and processed (2.0 M workers, 50.7 days). It certifies ~zero at d=30/ε=0.1 — not
   from bursts (its tails are thinner than Borg) but from SUSTAINED hour-scale load
   swings (energy face 643 vs 275 MJ), i.e., day-ahead job-schedule context is the
   missing ingredient. Paper structure: both real traces = public-data upper bounds;
   closed loop runs on PAI (honest near-zero) + a literature-anchored trainhall
   scenario, where the certificate validates 0/186 (CP95 ≤ 4.8%).
3. **Real NWP dew forecasts — DONE**: Open-Meteo previous-runs archive (2024, KIAH):
   measured DA residual std 2.01 K replaces the 1.2 K [est] model in records and in
   per-day realized residuals; all 10 evaluation weeks moved into 2024.
4. **e₀ lemma — scheduled** for Phase-7 theory writing (mechanism implemented and
   exercised: 111/111 warm starts delivered).
5. **More obligations — DONE**: 10 weeks × 20 seeds; 186 obligations on the validated
   configuration with zero failures.

## 4. Process lessons (pushed to skill_js after owner sign-off)
- A clean-context adversarial reviewer found in hours what weeks of green tests
  missed: **assertions inherited from flawed evidence chains pass flawlessly**.
- `hash()` seeding is a silent reproducibility killer on Python ≥ 3.3.
- Simulator/optimizer operating-point seams and METERING-DEFINITION seams (window vs
  whole-hour) are where certified-systems papers break; align the certified quantity
  with the settled quantity symbol-for-symbol before any experiment.
