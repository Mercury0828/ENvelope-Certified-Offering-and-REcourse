# Phase 6 — SELF AUDIT (2026-06-10)

## What was built

- **F1** (`phase6_F1_context.py`) — the headline value-of-context figure: certified
  envelope vs information level across the dew range, real Borg-2019 heat residuals +
  NWP-skill dew model, ready states at the robust floor (D-044). Includes the d = 15
  shorter-product curve (gate-1 tie-back).
- **F2 + main table** (`phase6_F2_table.py`) — 3 real weeks × 6 controllers × **20
  seeds** (2,520 controller-days), full §8 metric set incl. delivery ratio, rebound
  energy, condensation-floor clip events, certificate validity.
- **F3** (`phase6_F3_cdeg.py`) — degradation supply curve over two decades of c_deg.
- **Stress tests** (`phase6_stress.py`) — AI-burst day (top-decile real burst hours),
  +3 K dew-shift day (beyond the NWP bound), 6-hour consecutive-activation day.
- **One-command reproduction**: `make figures` / `python experiments/make_figures.py`
  (+ `--skip-table`), writing `FIGURES_MANIFEST.json` (script → artifacts, git hash,
  config hashes, seed).

## Acceptance checklist (guide §11, Phase 6)

| Criterion | Status | Evidence |
|---|---|---|
| Figures publication-grade, consistent style file | **PASS** | all via `config/encore.mplstyle`, PDF+PNG, labeled axes with units; visually inspected |
| Every number regenerable by one `make figures` | **PASS** | `Makefile` + `experiments/make_figures.py`; regeneration executed end-to-end with all assertions green |
| Results provenance manifest | **PASS** | `FIGURES_MANIFEST.json` + per-experiment provenance JSONs |
| F1–F3 + main table + stress tests, 20+ seeds | **PASS** | this directory |

## Headline numbers

- **F1:** context-free certification = **0 kW everywhere**; hour-of-day-conditional
  certification recovers **24.6 kW** (d = 30) and **80.5 kW** (d = 15) per MW IT in dry
  weather (dew ≲ 15 °C); all certification dies above dew ≈ 16 °C for this volatile
  workload while the deterministic ceiling continues at 55–93 kW — certification value
  AND its humidity limit in one picture.
- **Main table (20 seeds):** B4 market value +$26.0/day (scarcity), +$3.6 (humid),
  $0 (mild — rationally sits out); delivery ratio 1.00; **zero violations beyond the
  one workload-tail day that hits the idle B1 identically (+0.02 K)**. B2: 50–74
  violation-days per week, worst +13.1 K. Certificate validity: **2/89 delivery
  failures = 2.2% ≤ ε = 10%** (CI95 hi 5.4%).
- **F3:** committed capacity falls smoothly 225 → 81 kW as c_deg goes 0.5 → 50 $/K·h on
  the scarcity day (value $82 → $54/day); the mild day exits the market above
  c_deg ≈ 1 — degradation pricing acts as the marginal screen exactly as C3(iii)
  anticipates. γ ∈ {1.5, 3}× moves nothing for B4 (zero in-box penalties; stated).
- **Stress:** burst day — B4 0 violations, 0.35 kWh shortfall, $0.78 penalty (graceful,
  inside ε) vs B2 +11.9 K and $26 penalties; dew-shift +3 K — B4 clean (floor clipping
  handled); consecutive activations — B4 zero shortfall/violations (readiness wiring).

## Fixes made during this phase (all logged)

- **D-044**: certified ready states must pre-cool only to the ROBUST floor — the
  nominal-floor ready state made every certified envelope infeasible from its own
  start for dew ≥ 16 (caught by F1's cliff diagnosis).
- **D-045**: idle hours hold the NOMINAL point; pre-cool only ahead of commitments —
  the always-at-ready idle law let workload tails push even no-market B1 over T_max in
  humid weeks at 20-seed depth. B1 semantics now exactly match the D-035 baseline.
- **D-043** (negative finding): recent-residual volatility regime is non-informative
  on Borg-2019 (corr ≤ 0.08) — context enrichment needs operator job-schedule data.
- mojibake-safe editing note: PowerShell `Get-Content` without `-Encoding` corrupted a
  UTF-8 script once; rewritten via the file tools (process note, no code impact).

## Honest notes / open risks

- One humid day-seed (1 of 2,520) shows +0.02 K over the lumped T_max proxy with NO
  market participation — an out-of-box workload tail, identical for B1/B4, within the
  0.5 K intra-step tolerance (D-024). The acceptance assertion is therefore "B4 never
  worse than idle, ≤ 0.5 K", not an unconditional zero — stated plainly.
- B4's absolute $ remain modest on this trace (volatile mixed cluster + hour-of-day
  context only). The paper should present per-MW scaling and the steadier-hall
  sensitivity as the realistic upside; the zero-QoS first-tranche framing (guide 2.2)
  is the positioning, not $-dominance over B6.
- B3 shows 1 violation-day (humid, +0.02 K = the same exogenous tail) and zero others
  at 20 seeds; its lack of guarantee shows in F1-style coverage, not yet in closed-loop
  tails — worth a targeted adversarial seed study if a reviewer pushes.
- Trace/price alignment remains hour-of-day only; F2 magnitudes inherit that caveat.
