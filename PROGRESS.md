# PROGRESS.md

## Machine-readable status

```yaml
current_phase: 1
phase0:
  status: complete            # all acceptance criteria pass, SELF_AUDIT written
  completed_steps:
    - env_setup               # venv 'encore', py3.12.10, all packages, gurobi verified
    - repo_scaffold
    - plant_dynamics          # 2/3-state, virtual-input + closed-loop forms, ZOH 30s/5min
    - virtual_input_set
    - power_map_fit           # cop_c0=1.4027577 cop_c1=0.7986212 (D-014, D-016)
    - simulation_harness
    - unit_tests              # 33/33 green
    - step_response_experiment
    - supply_sweep_experiment
    - self_audit
phase1:
  status: complete            # gate memo written, verdict GO
  completed_steps:
    - duration_lp             # src/encore/envelope/duration.py + smoke tests
    - full_grid_experiment    # 168 bisections, all acceptance assertions pass
    - duration_memo           # results/phase1/DURATION_MEMO.md — VERDICT: GO
    - self_audit
  gate_verdict: GO            # S2 sustains 53.1-59.3% of P_base at d=30 (bar: 15-20%)
  recommended_d_star_min: 30
  recommended_q_range_pct_of_base: [15, 40]
gate1_owner_decision: GO      # confirmed by owner 2026-06-10 ("Gate1 确定。启动Phase 2")
phase2:
  status: complete            # memo written, verdict GO (geometric route)
  completed_steps:
    - lifted_deliverability   # reachability.py: Gz<=h in (x0, q, u), hour horizon
    - geometry                # F(x,c) LP, exact Bretl-Lall slices, TabulatedEnvelope
    - readiness_fixed_point   # 2-iter convergence at q in {50, 65} kW, d=30
    - virtual_battery         # closed forms; median 0.9% / worst 2.7% vs LP
    - cross_validation        # 2,400 pts: layer A 100.00%, layer B 99.00%, 0 anti-conservative
    - envelope_memo           # results/phase2/ENVELOPE_MEMO.md — R1 VERDICT: GO
    - walkthrough_artifact    # WALKTHROUGH.md + zip prepared; tag phase2-done after owner GO
    - self_audit
  gate_verdict: GO            # geometric route adopted; ML-surrogate fallback retired
gate2_owner_decision: GO      # confirmed by owner 2026-06-10
phase3:
  status: complete            # acceptance pass on synthetic ground truth; SELF_AUDIT written
  completed_steps:
    - synthetic_ground_truth  # data/synthetic.py (D-025)
    - conditional_boxes       # conformal k-NN budget polytopes W(c) (D-031, D-033)
    - tube_margins            # greedy support-function margins, LQR gain sweep (D-027)
    - tightened_envelope      # build_lifted(tube=) — F-tilde
    - fallback_certificate    # control/fallback.py (D-028)
    - online_mpc              # depth-indexed margins + fallback switch (D-029, D-032)
    - validation_experiment   # 500 scen/bin: 0 in-box violations; MPC fail 3.6% <= eps
  key_results:
    proto_F1: context-free certification EMPTY everywhere; conditional certifies 44.6/20.6 kW (dry bins, ready state); humid bins uncertifiable at d=30 eps=0.1 (synthetic process)
  caveat: numbers are synthetic-process-dependent; refit on real data when it lands
phase4:
  status: complete            # acceptance pass on two real days; SELF_AUDIT written
  completed_steps:
    - data_loaders            # ERCOT DAM/RTM/ECRS + KIAH day loaders
    - baseline_generator      # frozen, flat under frozen COP (D-035)
    - settlement              # 5.3 exact, activated-hours-only shortfall (D-040)
    - offering                # per-hour separable D-1 (D-036/D-037), B2/B3/B4 envelopes
    - day_simulator           # 24-h continuity, idle track-to-ready law (D-039)
    - two_day_experiment      # 2023-08-17 humid + 2024-01-16 dry (Heather)
  key_results:
    dry_day: B4 +$189/day vs B1, 0 penalty/violations; B2 +$653 but T_j 87.1 C + shortfall
    humid_day: B4 sits out (phase-3 finding holds end-to-end); B2 T_j 89.0 C
    negative_result: ready-box terminal collapses F-tilde to 0 (D-041) -> readiness SET wiring is Phase-5 work
phase5:
  status: complete            # all acceptance pass; SELF_AUDIT + artifact #2
  completed_steps:
    - portfolio_baselines     # B5 battery + B6 curtailment (config/market.yaml)
    - real_residual_records   # W(c) refit on 743 real records (D-042)
    - readiness_terminal_wiring  # R(q) polygon in committed plans (D-041 resolved)
    - three_week_runs         # mild/humid/scarcity x 7d x 6 ctrl x 3 seeds
  key_results:
    B4: zero violations in 189 days; +$24.6/day scarcity week; sits out mild/humid (rational)
    B2: 18 violation-days, worst +8.74 K — buys revenue with chip damage
    F2_shape: B2 alone on violation axis; B6 > B5 > B3 > B4 in $ at zero violations
  caveat: Borg cell volatile at hall scale + hour-of-day-only context -> small B4 $; Phase-6 levers listed in SELF_AUDIT
phase6:
  status: complete            # all acceptance pass; SELF_AUDIT written
  completed_steps:
    - F1_context_value        # context-free 0 kW everywhere; conditional 24.6 (d=30) / 80.5 (d=15) kW dry; dies dew>=16
    - F2_main_table_20seeds   # 2,520 controller-days; B4 zero cert-scope violations; cert validity 2.2% <= eps
    - F3_cdeg_supply_curve    # 225->81 kW over two decades of c_deg; mild day exits market
    - stress_tests            # burst / dew-shift / consecutive: B4 clean, B2 +8-12 K
    - make_figures            # Makefile + orchestrator + FIGURES_MANIFEST.json
  fixes: [D-043 regime non-informative, D-044 robust-floor ready, D-045 idle-at-nominal]
phase7:
  status: not_started         # paper drafting — OWNER-SUPERVISED, not autonomous (guide §11)
  next_step: owner kicks off drafting sessions; verify-flagged citations (guide §3) must be checked first
autonomous_pipeline: COMPLETE  # phases 0-6 done; all gates passed (1: GO, 2: GO)
remote: https://github.com/Mercury0828/ENvelope-Certified-Offering-and-REcourse (main; push at milestones)
skill_js: lessons pushed (29c93a4)
owner_todo:
  - download data per data/DATA_REQUEST.md (ERCOT prices, KIAH weather, GPU traces) — needed for Phase 5/6 realism; Phase 4 can proceed on synthetic prices meanwhile
```

## Narrative log

- **2026-06-10** Phase 0 complete. Plant implemented fresh per guide 6.1 (E2E-CDRO path
  was a placeholder). All acceptance criteria pass; see `results/phase0/SELF_AUDIT.md`.
  Key calibration: ṁ_nom = 14 kg/s, C_w = 25 MJ/K → loop τ 5.3–8.0 min, facility τ
  50.5 min, junction 24 s; Gheni 17→25 °C sweep −63.3%. Decisions D-001..D-016 logged.
- **2026-06-10** Phase 1 complete. q–d frontier over the full grid; all programmatic
  assertions (monotone, pre-cool dominance, humid ⊆ dry) pass. S1 matches the
  ~30%/~20 min literature anchor (33.7% @ 20 min); S2 sustains 53–59% of baseline
  cooling power for 30 min (gate bar 15–20%). **GATE #1 VERDICT: GO.** Recommended
  product: d* = 30 min, q ∈ 15–40% of baseline cooling power. Run stopped at the gate
  per guide §11 — Phase 2 not started.
- **2026-06-10** Owner confirmed Gate #1 GO; skill_js verified as owner's methodology
  package and adopted (D-017). Phase 2 executed: lifted deliverability polyhedron,
  exact slice projections + tabulated runtime envelope, readiness fixed point, VB
  closed forms. Cross-validation 2,400 pts (100.00% exact-layer, 99.5% overall, zero
  anti-conservative); VB within 2.7% of LP; envelope-vs-dewpoint monotone (weather
  coupling lives in the pre-cool/ready state and E_cap). **GATE #2 (R1) VERDICT: GO —
  geometric route adopted.** Stopped at gate 2; Phase 3 not started.
- **2026-06-10** Owner confirmed Gate #2 GO; skill_js lessons pushed; ENCORE remote
  wired and pushed (main + tags). Phase 3 executed on synthetic contextual ground
  truth: conformal k-NN budget-polytope W(c) (a pure amplitude box provably empties
  the envelope — D-031), tube-tightened F̃ with swept LQR gain, fallback certificate =
  tightened-LP feasibility, depth-indexed-margin MPC with fallback switch. Validation:
  0 in-box safety violations (500 scen × 2 policies × 2 certifiable bins), delivery
  failure 0%/3.6% ≤ ε=10%, corner + beyond-box injections behave. Proto-F1: context-free
  certification empty everywhere; conditional certifies 44.6/20.6 kW (dry), humid bins
  flagged no-offer (synthetic-process-dependent; R2-honesty). Phase 4 next (no gate).
- **2026-06-10** Real data acquired (D-034): ERCOT DAM/RTM/ECRS 2023-24 (HB_HOUSTON),
  KIAH hourly weather, Google Borg 2019 trace shards → 1 MW hall profile.
- **2026-06-10** Phase 4 complete. Market layer (baseline/settlement/offering/dayrun)
  + two real-day end-to-end runs (humid Aug day; Winter Storm Heather dry day with
  ECRS at $1,000–1,500/MWh). Exact ledger reconciliation asserted; offers inside
  envelopes by construction. B4: +$189/day market value with zero violations on the
  dry day, sits out the humid day; B2 buys profit with T_j violations on both days.
  D-035..D-041 logged (incl. the settlement edge case and the terminal-box negative
  result). Phase 5 next (no gate).
- **2026-06-10** Phase 5 complete. B5/B6 baselines; W(c) refit on real trace/weather
  residuals (D-042: double-scaling caught, NWP-skill dew model, climatology heat
  forecast); readiness R(q) terminal wired into commitments (D-041 resolved). 3 real
  weeks × 6 controllers × 3 seeds: B4 zero violations in 189 days with +$24.6/day in
  the scarcity week; B2 18 violation-days (worst +8.7 K); proto-F2 produced. All
  acceptance assertions pass; artifact #2 zipped; tagged phase5-done. Phase 6 next.
- **2026-06-10** Phase 6 complete — the autonomous pipeline (phases 0–6) is DONE.
  F1: context-free certification is zero everywhere, conditional recovers 24.6/80.5 kW
  (d=30/15) in dry weather, all certification dies above dew≈16 °C on this workload.
  Main table 20 seeds: B4 +$26/day scarcity, delivery ratio 1.00, certificate validity
  2.2% ≤ ε; B2 worst +13.1 K. F3 degradation supply curve monotone. Stress tests clean.
  `make figures` regenerates everything + FIGURES_MANIFEST. Fixes D-043/044/045 logged
  (robust-floor ready states, idle-at-nominal semantics, regime non-informativeness).
  Phase 7 (paper) is owner-supervised per guide §11.
