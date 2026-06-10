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
next_phase: 2                 # envelope geometry — DO NOT START until owner confirms gate
status: STOPPED_AT_GATE_1     # per guide Section 11, awaiting owner decision
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
