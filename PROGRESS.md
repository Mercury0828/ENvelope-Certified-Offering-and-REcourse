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
  status: in_progress
  completed_steps:
    - duration_lp             # src/encore/envelope/duration.py + smoke tests
  next_step: run experiments/phase1_duration.py full grid, write DURATION_MEMO.md + SELF_AUDIT.md
gate: phase1 is GO/NO-GO gate #1 — STOP after DURATION_MEMO.md
```

## Narrative log

- **2026-06-10** Phase 0 complete. Plant implemented fresh per guide 6.1 (E2E-CDRO path
  was a placeholder). All acceptance criteria pass; see `results/phase0/SELF_AUDIT.md`.
  Key calibration: ṁ_nom = 14 kg/s, C_w = 25 MJ/K → loop τ 5.3–8.0 min, facility τ
  50.5 min, junction 24 s; Gheni 17→25 °C sweep −63.3%. Decisions D-001..D-016 logged.
- **2026-06-10** Phase 1 started: duration-accounting LP implemented with conservative
  affine power surrogate (D-006), bisection on q per (scenario × workload × init ×
  weather × duration).
