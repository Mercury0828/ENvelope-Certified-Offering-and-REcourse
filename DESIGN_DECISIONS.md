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

## 2026-06-10 — D-017: skill_js repo verified and adopted (supersedes D-001's refusal, not its caution)

**Question.** D-001 declined to download `github.com/Mercury0828/skill_js` during the
autonomous run. The owner then explicitly instructed: pull it and use it.

**Decision.** Cloned (on explicit owner instruction) to `~/.encore-vendor/skill_js`
(outside the project repo) and inspected before use. Verified contents: it is the
owner's own research-methodology startup package (START_HERE, RESEARCH_PROTOCOL with
Jason's standing directives, skills 01–09, templates) — documentation only, no
executable code. Adopted as a methodology reference. Where its standing directives and
guide.md conflict, **guide.md wins** (per the package's own rule): in particular the
"auto-continue phases" directive does NOT override guide §11's hard stops at gates #1
and #2; it applies to Phases 3→6.

**Follow-ups it imposes:** (a) ENCORE has no GitHub remote yet — wire and push at
milestones once the owner provides the URL; (b) distill generalizable ENCORE lessons
back into skill_js as they arise; (c) tag phase completions (`phase0-done`,
`phase1-done` to be added).

## 2026-06-10 — D-018: Geometric-route division of labor (Phase 2)

**Decision.** The exact-projection + tabulation pipeline (the R1 "polytope route") is
demonstrated and cross-validated on the **2-state** envelope (guide's default, D-013):
fixed-q slices are exact 2-D polygons, tabulated over (d, T_dew, q). The **3-state**
product envelope uses the *same lifted polyhedron* via direct LP queries (F, membership,
trajectories) and will be embedded un-projected as constraints inside the D-1 offering
problem (Phase 4) — projection of the 4-D (x, q) set is unnecessary for any downstream
consumer. **Rationale.** Exactness where the theory lives, zero approximation where the
optimizer lives; avoids 3-state vertex-enumeration cost with no loss.

## 2026-06-10 — D-019: Delivery constraint form in the envelope

**Decision.** Cumulative over the activation window: Σ_{t∈A}(P̄−P_t)Δt ≥ r q ΔH
(guide 6.3 "along the activation profile"). Conservative vs settlement's whole-hour sum
(5.3); the Phase-1 "sustained" form is kept as a flag and shown to lower-bound the
cumulative envelope (test).

## 2026-06-10 — D-020: Activation profile

**Decision.** Activation occupies the first round(r·12) steps of the hour, r = d/60 by
default (the product's maximal activation). Other placements/r values are a spec field,
not enumerated in Phase 2.

## 2026-06-10 — D-021: Envelope domain and first-step ramp

**Decision.** The envelope is defined inside an explicit operating box (DOE-style
domain); x₀ need not be a steady state, so the pre-event→first-step ramp link is
dropped (inter-step ramps kept). Absolute input guards keep slices bounded for the
projection algorithm.

## 2026-06-10 — D-022: Polytope library choice (guide §12 "pick in Phase 0/2, log it")

**Decision.** pypoman's Bretl–Lall `project_polytope` for exact 2-D slices (with a
dummy-equality workaround for its eq-required assertion); scipy ConvexHull for
H-reps/areas; pycddlib (block/Fourier elimination) verified available as backup; the
`polytope` package is unused. **Rationale.** Bretl–Lall scales with output complexity
(8-vertex polygons in ~0.2 s) rather than the 14-D lifted dimension.

## 2026-06-10 — D-023: Cross-validation design (Phase 2 acceptance)

**Decision.** Three layers: (A) on-grid polygon membership vs feasibility LP — tests
projection exactness, must be ~100%; (B) continuum samples vs the conservatively
snapped tabulated object — quantifies designed conservatism, must be ≥98% with ZERO
anti-conservative errors; (C) re-simulation of LP-optimal trajectories at 30 s — the
non-circular physics check. Knife-edge points (<1e-3 K from a facet) excluded from A as
floating-point tie-breaks.

## 2026-06-10 — D-024: Intra-step excursion margin

**Finding/decision.** Enforcing constraints at 5-min marks admits ≤ +0.4 K intra-step
T_j excursions (layer C). Fold a 0.5 K state-constraint margin into the Phase-3 tube
tightening rather than densifying the control grid. Parked in PARKING_LOT for Phase 3.

## 2026-06-10 — D-025: Phase 3 runs on synthetic contextual ground truth first

**Decision.** The tightening/fallback machinery is built and validated against a seeded
synthetic conditional disturbance process (`src/encore/data/synthetic.py`) whose ground
truth is known — so quantile-box coverage is verifiable exactly. Real data
(ERCOT/KIAH/GPU traces per `data/DATA_REQUEST.md`) refits the same estimator with no
code changes. **Rationale.** Coverage validation against a known distribution is the
only way to *test* the estimator (real data can only show consistency); also unblocks
Phase 3 while the owner collects files.

## 2026-06-10 — D-026: W(c) record definition and box construction

**Decision.** Historical records are HOURLY summaries: (max over the hour's 5-min steps
of the heat-load deviation, hourly dew-point forecast residual). Box per context via
k-NN (k = 200, normalized features): heat two-sided at [ε/4, 1−ε/4], dew one-sided at
1−ε/2 — Bonferroni joint coverage ≥ 1−ε, and containment of one record ≡ containment
of the hour's whole disturbance trajectory (what Thm 2 needs).

## 2026-06-10 — D-027: Tube margins and scope

**Decision.** Fallback policy u = ū + K(x − x̄) with fixed K from discrete LQR
(feedback-authority level swept over {20, 50, 100} kW/K offline; best mean-F̃ kept and
logged by the experiment). Margins M_t = Σ|A_K^i E_d|·w̄_Q tighten every lifted-row
(states, U(x) bounds, ramp, delivery, terminal); the condensation floor is robustified
by w̄_D. Symmetric heat bound w̄_Q = max(|lo|, hi) of the box. Certification scoped to
the 2-state envelope (guide's default geometry); 3-state tube margins deferred to the
Phase-4 embedding work.

## 2026-06-10 — D-028: The fallback certificate IS the tightened LP

**Decision.** "Certified" means exactly: the tube-tightened lifted LP is feasible at
(x₀, q), and the certificate object is its nominal trajectory + the fixed gain
(guide 6.5's definition, implemented literally in `control/fallback.py`).

## 2026-06-10 — D-029: Online MPC form

**Decision.** Deterministic suffix LP each 5 min: nominal constraints, current dew
forecast, remaining-delivery constraint, terminal state in the readiness polygon,
L1 tracking of the certified plan as objective; on infeasibility switch permanently to
the fallback policy for the rest of the hour. No robustness online (guide 6.4).

## 2026-06-10 — D-030: Two unconditional comparators for the value-of-context result

**Decision.** Proto-F1 compares F̃_conditional against (a) the *pooled-marginal* box —
common practice, demonstrably under-covers bursty bins (invalid certificate there), and
(b) the *uniform* box (elementwise max over a context sample) — the smallest valid
context-free certificate, against which F̃_cond ≥ F̃_uniform holds bin-wise (guide
6.4's geometric claim). **Rationale.** Comparing only against (a) would overstate the
value of context by using an invalid baseline; the honest headline is "context buys
depth in calm bins AND validity in bursty bins".

## 2026-06-10 — D-031: W(c) is a budget-augmented polytope, not a pure box

**Question.** Treating the hourly-max heat-deviation quantile as a *persistent*
per-step bound made tube margins consume the entire thermal headroom: the tightened
envelope was EMPTY at the nominal state even at q = 0 (a 1-hour worst case of "the
burst bound applies at every step" is ~10× the energy of any real disturbance hour).

**Decision.** W(c) = { w : w_t ≤ w̄(c) ∀t, Σ_t max(w_t, 0)·Δt ≤ Ē(c) } × {dew ≤ d̄(c)}
— the energy-budget face encodes that bursts are short. Historical records gain the
third channel (positive-deviation energy); per-face quantiles at 1−ε/4 with k = 150
(the Bonferroni slack absorbs k-NN edge-smoothing bias; conformal calibration parked
for Phase 6). Tube margins become the exact support function of the budget polytope —
a greedy largest-coefficients-first fill, still closed-form. Guide 6.3 explicitly
allows polytopic W. Negative deviations carry no budget: they can only cause benign
input clipping (less extraction than commanded ⇒ more delivered cut, colder loop);
covered by the empirical validation rather than the margin calculus, stated honestly.

**Rationale.** This is the difference between "certifiable product exists" and "tube
machinery technically correct but useless" — and it is itself a finding for the paper:
duration-style flexibility certification NEEDS a disturbance-energy face, a pure
amplitude box is structurally too conservative.

## 2026-06-10 — D-032: Online MPC carries depth-indexed tube margins

**Question.** The first MPC (nominal constraints, guide's "deterministic MPC" read
literally) violated T_max inside the box — it plans onto the exact boundary and one
positive deviation crosses it.

**Decision.** The suffix LP carries the same offline tube margins indexed by prediction
depth k (error restarts at each re-solve from the measured state). Since M_k is
nondecreasing, suffix margins ≤ certificate margins at the same absolute time, so the
certified fallback plan stays suffix-feasible — recursive feasibility (Thm-3 template)
holds by construction. Still deterministic, still no online min-sup; margins are fixed
offline numbers added to RHS vectors.

## 2026-06-10 — D-034: Real-data sources (owner-directed)

**Decision (owner instruction).** (a) ERCOT prices via `gridstatus` annual historical
packages (DAM hourly + RTM **15-min settlement SPP** — the model's ΔH-accounting wants
settlement granularity, not 5-min SCED LMP), HB_HOUSTON, 2023–2024; AS MCPC attempted,
manual NP4-188-CD fallback stands if MIS daily docs have expired. (b) KIAH weather =
IEM ASOS real hourly observations (TMY3 rejected: model needs real joint price/weather
days). (c) IT traces = **Google Borg 2019 cell-a `instance_usage`** (supersedes the
guide §9 Alibaba/Azure suggestion, owner's call): 4 random parquet shards (~2.5M rows,
public GCS bucket over plain HTTPS, no auth needed) — a uniform row sample whose
per-window SUM estimates the fleet profile shape (~280 rows/window, ~6% noise).
Processed to a 1 MW hall 5-min mean/peak series with affine power map (idle 0.3 [est]).
Caveats logged in data/README.md: peak series is a non-simultaneity upper bound
(concurrency adjustment parked for Phase 5); trace clock is not wall-aligned to prices.

## 2026-06-10 — D-035: Baseline P̄^cool,0 is flat under the frozen-COP surrogate

**Decision.** Under D-006's frozen COP, total daily cooling energy is schedule-invariant
(every joule extracted at the same COP), so the no-market optimum — and hence the
guide-5.4 exogenous baseline — is the nominal steady state: P̄_t ≡ P_base. B1 and the
baseline generator coincide by construction. Becomes a real optimization when the
COP(T_in) refinement is promoted (PARKING_LOT).

## 2026-06-10 — D-036: RT-energy term in the D-1 objective = energy-neutral shift

**Decision.** Stored event heat is re-extracted during recovery at the same COP, so the
expected RT-cost effect of offering q_h is E[r_h]·q_h·ΔH·(π_rt,recovery − π_rt,event),
with recovery priced at the next hour's mean RTM. Linear in q, sign-correct (events on
price peaks are profitable twice).

## 2026-06-10 — D-037: Degradation term and offer optimization form

**Decision.** Degradation cost per activated hour = c_deg·∫[T_j − T_thr]_+ dt evaluated
on the certified nominal plan at candidate q (exact for the plan; trajectories are LP
outputs). T_thr = 70 °C [est], c_deg = 2 $/K·h [est] (C3(iii) sweeps it later). The V1
offering is per-hour separable (plant re-enters ready state between hours; holding is
free under frozen COP), solved by grid search over [0, F̃_h] — an LP is unnecessary
until cross-hour coupling (pre-cool scheduling with real holding costs) arrives.

## 2026-06-10 — D-038: Activation and scenario model (V1)

**Decision.** Activation exogenous per guide 5.2: r_h Bernoulli(p_act = 0.15 [est]) with
r = d/60 when called; B3's SAA envelope uses the elementwise max over 20 sampled
scenario records (no probabilistic guarantee — that is B3's defining property);
B2 uses the deterministic envelope; B4 the conformal-certified F̃.

## 2026-06-10 — D-039: Inter-hour operation

**Decision.** Idle (non-activated) hours run a track-to-ready feedback law
u = Q_IT + K(x − x_ready); activated hours run the committed plan via fallback or
tube-margin MPC. State carries hour to hour; all controllers face common random
numbers. Settlement applies only to activated hours (D-040).

## 2026-06-10 — D-040: Settlement shortfall only for activated obligations

**Question.** Guide 5.3's s_h = [r_h q_h ΔH − Σ(P̄−P)Δt]_+ literally yields positive
shortfall for hours with NO obligation whenever realized cooling power exceeds baseline
(bursts), charging penalties to idle plants (B1 was fined $52 for not offering).

**Decision.** s_h is computed only when r_h·q_h > 0; hours without an activated
obligation settle nothing. This is the evident intent of 5.3 (shortfall against an
obligation), logged because it is a formula edge-case the paper text should state.

## 2026-06-10 — D-041: No terminal constraint in V1 committed plans (negative result kept)

**Question.** Consecutive activations can start events from warm states (2-3
"infeasible starts"/day at p_act = 0.15), where the realized state cannot run the
committed plan and the simulator falls back to the D-1 plan with feedback absorbing
the gap (observed: zero violations, zero shortfall for B4).

**Decision.** Tried terminal = ready-state box: it over-tightens to F̃ ≡ 0 everywhere —
a naive return-to-start terminal KILLS the product, demonstrating exactly why guide 6.3
defines readiness as a SET (Phase-2's R(q) is far larger than the ready box). V1 ships
without terminal constraints + explicit infeasible-start fallback and counting; wiring
the true readiness polygon into committed plans is Phase-5 work. The negative result is
paper-worthy (ad-hoc terminal penalties vs readiness sets).
