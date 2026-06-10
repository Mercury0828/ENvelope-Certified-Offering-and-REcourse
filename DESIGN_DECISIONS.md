# DESIGN_DECISIONS.md — append-only log

Format: date | question | decision | rationale. Per guide.md Section 0: when the guide
does not answer a design question, choose the most conservative option and log it here.

---

## 2026-06-10 — D-001: Third-party "skill" download requested in startup prompt

**Question.** The startup prompt asked to first download a skill from
`https://github.com/Mercury0828/skill_js` before starting the mission.

**Decision.** Declined; not downloaded, not executed.

**Rationale.** Unvetted third-party code from an unknown repository, unrelated to this
Python research project (name suggests JavaScript). The run's own standing rules permit
network access only for package installation. Executing unreviewed external code in an
autonomous run is a supply-chain risk; nothing in Phase 0/1 requires it.

## 2026-06-10 — D-002: Python version

**Question.** Guide requires Python 3.12; only 3.11.4 was installed on this machine.

**Decision.** Installed CPython 3.12.10 via the Windows `py` launcher
(`py install 3.12`, signed index from python.org), created user-local venv
`%USERPROFILE%\.virtualenvs\encore`.

**Rationale.** Keeps the guide's pinned version; user-local, no system-wide installs.

## 2026-06-10 — D-003: Gurobi license source

**Question.** Guide says license is provided via `GRB_LICENSE_FILE`; that variable is
unset on this machine.

**Decision.** Gurobi found a valid academic WLS license in its default location; a
trivial LP solves (verified 2026-06-10). Proceed with Gurobi available. Phase 0/1
numerical work uses scipy's HiGHS for the small feasibility LPs (see D-009); no license
material is in the repo.

**Rationale.** License works regardless of the env var; nothing in Phase 0/1 requires
Gurobi specifically (per startup prompt).

## 2026-06-10 — D-004: Sign and topology of the facility-loop coupling (3-state model)

**Question.** Guide 6.1 writes `C_w dT_w/dt = h_jw (T_j − T_w) − q̇_ext [+ optional
facility-loop coupling h_wf (T_w − T_f)]` and `C_f dT_f/dt = h_wf (T_w − T_f) − q̇_rej`.
Taken literally, the `+ h_wf (T_w − T_f)` term in the T_w equation is anti-physical
(positive feedback), and energy extracted by q̇_ext vanishes from the system while
h_wf-heat appears in the facility loop from nowhere.

**Decision.** Implement the 3-state model in the energy-consistent series topology:

- `C_j dT_j/dt = Q_IT − h_jw (T_j − T_w)`
- `C_w dT_w/dt = h_jw (T_j − T_w) − q̇_ext`   (q̇_ext = CDU heat transfer, coolant loop → facility loop)
- `C_f dT_f/dt = q̇_ext − q̇_rej`              (q̇_rej = heat rejection to ambient, chiller/tower)

with inputs u = (q̇_ext, q̇_rej) in the virtual-input (optimization) form. In the
closed-loop *physical* form used for step-response characterization, the CDU is passive:
T_in = T_f + δ_hx, so q̇_ext = ṁ c_p (T_w − T_f − δ_hx) — which recovers exactly the
guide's `h_wf (T_w − T_f)` coupling structure with h_wf = ṁ c_p and the physical
(negative-feedback) sign. The 2-state model drops T_f and sets q̇_rej ≡ q̇_ext
(no facility buffering; extraction is rejected immediately).

**Rationale.** Conserves energy exactly (required by the <1% energy-balance acceptance
test), keeps dynamics LTI in the virtual input, and reconciles the guide's h_wf form as
the closed-loop special case. Most conservative reading that is physically consistent.

## 2026-06-10 — D-005: CDU passive-HX bound in the 3-state input set

**Question.** During a chiller power cut, can the CDU still cool the coolant below the
facility-loop temperature?

**Decision.** No. In the 3-state model, U(x) includes
`q̇_ext ≤ ṁ_max c_p (T_w − T_f − δ_hx)` (passive heat exchange only; chiller assist on
the CDU is not credited during events). Deep pre-cooling reaches low T_in by chilling
the facility loop itself (chiller assist acts on T_f), consistent with guide 6.1's
chiller-assist topology statement.

**Rationale.** Conservative (no free chiller assist while chiller power is being cut);
keeps the bound affine in x.

## 2026-06-10 — D-006: Cooling-power surrogate inside the Phase-1 LP

**Question.** P_cool = P_pump(ṁ) + q̇_rej/COP(T_in − T_wb) is nonconvex in the decision
variables through ṁ(q̇_ext, T_w) and T_in.

**Decision.** In the Phase-1 feasibility LP, certify the power cut with the conservative
affine surrogate `P_cool,t = P_pump(ṁ_nom) + q̇_rej,t / COP_ref`, where COP_ref is
evaluated at the *baseline* supply temperature and the scenario wet bulb, and pump power
is held at nominal. Both choices over-estimate realized cooling power during an event
(raising T_in during a cut improves COP; throttling flow cuts pump power), so any
certified q is deliverable.

**Rationale.** Keeps Phase 1 to plain LPs (per startup prompt), errs conservative.
PWA refinement in (q̇, T_in) is parked for Phase 2 (see PARKING_LOT).

## 2026-06-10 — D-007: Wet-bulb temperature held fixed across dry/humid cases

**Question.** The Phase-1 humid case raises T_dew 15→22 °C. Should T_wb (which sets COP
and hence baseline power) co-vary?

**Decision.** Hold T_wb = 22 °C [est] for both dry and humid Phase-1 cases; only T_dew
(the condensation floor) varies.

**Rationale.** Lower COP in humid weather makes a given kW power cut *thermally cheaper*
(less extraction lost per kW cut), which can push the humid kW-frontier *outside* the dry
one — confounding the condensation-floor effect the phase is designed to isolate, and
breaking the guide's required assertion "humid ⊆ dry" for reasons that are not bugs.
With T_wb shared, baseline power is identical across cases and humidity enters only
through the T_in floor, making the assertion structurally meaningful. Physical caveat
(T_wb ≥ T_dew requires near-saturation in the humid case) is noted in the memo;
re-coupling COP to weather happens in Phase 3's uncertainty model (parked).

## 2026-06-10 — D-008: Burst overlay definition (synthetic, Phase 1)

**Decision.** Burst workload = nominal 1 MW plus +20% (200 kW) square bursts occupying
5-min intervals 2 and 5 of the event window (minutes 5–10 and 20–25), encoded as the
peak-over-interval statistic per guide 6.2. Defined on absolute event time and truncated
to each duration d, so feasibility for d+5 implies feasibility for d (monotone frontier
is structural). Magnitude is [est] pending trace tail quantiles (Phase 3+).

## 2026-06-10 — D-009: LP solver for Phase 1

**Decision.** Phase-1 feasibility LPs are built as explicit sparse matrices and solved
with scipy `linprog(method="highs")`. Gurobi is verified working (D-003) and remains the
solver for later phases per guide §12; cvxpy is installed.

**Rationale.** ~2,000 tiny LPs inside bisection loops; HiGHS is deterministic, fast,
license-free, and dependency-light. Nothing in Phase 0/1 requires Gurobi (startup prompt).

## 2026-06-10 — D-010: State-dependent input bounds enforced at both interval endpoints

**Decision.** The affine-in-x bounds of U(x) are imposed at both x_t and x_{t+1} for each
5-min step in the Phase-1 LP.

**Rationale.** T_w moves within a step; enforcing at both endpoints is conservative for
monotone intra-step trajectories at negligible LP cost.

## 2026-06-10 — D-011: Ramp limit value

**Decision.** q̇_ext ramp limit = 200 kW/min [est] (full 1 MW swing within one 5-min
control step), enforced including the transition from the pre-event operating point.

**Rationale.** Chillers/CDUs unload over minutes; at 5-min control granularity this is
effectively non-binding. The guide tags ramp limits [est]; a tighter value would be
arbitrary precision Phase 0/1 cannot calibrate. Revisit with vendor data (parking lot).

## 2026-06-10 — D-012: Pre-cooled "ready state" definition

**Decision.** Pre-cooled initial state = steady state at supply temperature
T_in,pre = max(T_in,min, T_dew + δ_cond), i.e., exactly at the condensation floor.
No condensation constraint is placed on the facility-loop temperature T_f (guide
constrains T_in only); this gap is parked for Phase 2.

## 2026-06-10 — D-013: 2-state vs 3-state default (guide 6.1 "decide in Phase 0")

**Decision.** The 2-state model (T_j, T_w) is the default for envelope geometry
(Phase 2+); the 3-state model is used for simulation fidelity and is exactly the S2
thermal-mass scenario in Phase 1.

**Rationale.** Follows the guide's stated default; Phase-1 S1-vs-S2 results quantify
what the third state buys, informing whether Phase 2 needs it.

## 2026-06-10 — D-014: COP calibration anchoring

**Decision.** The two free coefficients (c0, c1) of COP = c0 + c1 (T_supply − T_wb) are
fit to (i) anchor COP = 3.0 [est] at T_supply = 17 °C with calibration wet bulb
T_wb = 15 °C [est], and (ii) reproduce the [Gheni26] target: 63.3% cooling-power
reduction for the 17→25 °C supply sweep at 1 MW load with pump at nominal. COP is
clamped to [2, 12] [est] outside the fitted range. Fitted values are stored in
config/plant.yaml with a [fit] tag and guarded by a unit test.

**Rationale.** One anchor + one trend target identifies exactly two coefficients; the
anchor magnitude is an engineering estimate of warm-water chiller-assisted effective COP
at low supply temperature (trend-based acceptance, 40–75% band).

## 2026-06-10 — D-015: Internal units

**Decision.** All internal computation in SI (W, J/K, s, °C). Config values carry
human-scale units (kW, MJ/K) in their names and are converted once at load time.
Reports/plots display kW and minutes.

## 2026-06-10 — D-016: Nominal coolant flow set by the time-constant band

**Question.** With ṁ_nom = 17.1 kg/s (design ΔT 15 K) and C_w at the top of the guide's
range (25 MJ/K), the 3-state loop mode is 4.35 min — just below the guide's 5–20 min
acceptance band (the 2-state loop mode, 6.5 min, was fine).

**Decision.** ṁ_nom = 14.0 kg/s (design loop ΔT ≈ 18.3 K [est]), pump coefficient
rescaled (a_p = 9.111 W/(kg/s)³) to keep P_pump(ṁ_nom) ≈ 25 kW, COP coefficients refit
(c0 = 1.4027577, c1 = 0.7986212). Resulting nominal step-response time constants:
junction 0.4 min; loop 7.95 min (2-state) / 5.25 min (3-state); facility 50.5 min —
all within guide 6.1 ranges. Nominal operating point becomes T_w ≈ 43.3 °C,
T_j ≈ 68.3 °C (hotspot headroom 16.7 K).

**Rationale.** C_w is already capped at the guide's range top, so flow is the remaining
free calibration knob; a higher design ΔT is plausible for warm-water direct-to-chip
and is tagged [est] for Phase-0-style recalibration when real plant data exists.
