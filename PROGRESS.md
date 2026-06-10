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
next_phase: 3                 # tightening + fallback — DO NOT START until owner confirms gate 2
status: STOPPED_AT_GATE_2     # per guide Section 11, awaiting owner decision
owner_todo:
  - provide GitHub remote URL for ENCORE (no remote configured; gh CLI absent)
  - confirm gate 2 (R1: geometric route GO)
  - data list for Phase 3 will be generated on gate-2 GO (ERCOT, KIAH, GPU traces)
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
