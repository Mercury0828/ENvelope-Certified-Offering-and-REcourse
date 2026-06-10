# ENCORE — Project Guide

**ENvelope-Certified Offering and REcourse**
*Certified cooling-side flexibility offering for liquid-cooled AI data centers*

Target venue: **IEEE Transactions on Smart Grid (TSG)**
Status: Phase 0 (project bootstrap)
Owner: Jason (Jiachen Shen). This document is the project constitution. Last updated: 2026-06-10.

---

## 0. How to use this document

This guide governs every phase of the project. Rules for any agent (Claude Code / dr-claw) working in this repo:

1. **Read this entire file before writing any code.** When a design question arises, the answer is in here. If it is genuinely not in here, log the question and your chosen resolution in `DESIGN_DECISIONS.md` and proceed with the most conservative option.
2. **Scope control is binding.** Section 7 lists what is IN the model, what is DOWNGRADED to remarks/parameters, and what is CUT. Do not promote a DOWNGRADED or CUT item into the model, ever, without an explicit instruction from the owner in a new prompt.
3. **The "reality three-zones" rule (Section 2.3) is binding.** Real-world institutional detail lives in motivation, data, and experiment scenarios — never in model structure. The model contains exactly ONE institutional element: the product duration parameter `d`.
4. **Theorem targets (Section 6.7) define what "done" means for the theory.** Code exists to (a) verify the theory numerically and (b) produce the evidence in Section 8.
5. **Phases have acceptance criteria (Section 11).** A phase is not complete until its criteria pass and the self-audit is written. Phases 1 and 2 are GO/NO-GO gates: produce the gate memo, stop, and wait for the owner's decision.
6. All numerical parameter values in Section 6 are **initial values with sources tagged** `[Gheni26]`, `[slides]`, or `[est]` (engineering estimate). Phase 0 calibration may revise them; revisions are logged in `config/plant.yaml` with a comment and in `DESIGN_DECISIONS.md`.

---

## 1. Thesis

**One paragraph.** Liquid-cooled AI data centers hold short-term thermal headroom in their cooling loops: cooling power can be cut for tens of minutes (and banked in advance by pre-cooling) without touching any compute workload, bounded above by chip hotspot temperature and below by the condensation (dew-point) margin. This project turns that headroom into a **day-ahead, penalty-backed market offering with certified deliverability**: we (i) characterize the exact set of deliverable (power, duration) offers as a context-dependent polytope — a "weather-coupled thermal virtual battery"; (ii) robustify it offline against contextual uncertainty (workload bursts, dew-point forecast error) so that any offer inside the tightened envelope carries a distributionally robust delivery-and-safety guarantee executed by a cheap online MPC with a certified fallback; and (iii) quantify, on ERCOT prices and Houston humidity, what this flexibility is worth, what it costs in GPU wear, and where it sits relative to batteries and workload curtailment.

**The exact novelty claim for the paper (do not strengthen it):**

> "To our knowledge, this is the first work to formalize the thermal headroom of **liquid-cooled** AI data centers as a **day-ahead, penalty-backed** flexibility offering whose deliverability is **jointly certified against hotspot and condensation constraints**."

All four qualifiers (liquid-cooled / day-ahead / penalty-backed / jointly certified) are load-bearing. Removing any one of them makes the claim false against existing literature (Section 3).

**Forbidden claims** (each is contradicted by prior work — see Section 3.2):
- "First to study cooling-side data center demand response." (Ghatikar et al. field-tested it in 2012.)
- "First cooling resource to participate in electricity markets." (Fu et al. tracked regulation signals with chilled-water setpoints.)
- "Dual-sided constraints are structurally unprecedented." (Building comfort bands are two-sided.)
- "No one has studied data center flexibility markets." (Large literature, lines A–D in the slides.)

---

## 2. Background: why this, why now

### 2.1 Three facts that establish relevance (Intro material, fully verified 2026-06)

1. **Flexibility is becoming a legal obligation in Texas.** SB6 (signed June 2025) requires large loads (≥75 MW) interconnecting after Dec 31, 2025 to install, *before interconnection*, equipment allowing ERCOT to directly curtail them during firm load shed; reported implementation involves mandatory load flexibility with ~24-hour advance notice plus real-time telemetry. The 24-hour-notice + real-time-execution structure is the legal mirror of our D-1 commitment + D-day recourse architecture. The question for operators is no longer *whether* to be flexible but *how to satisfy flexibility obligations at minimum cost* — and cooling headroom is the only tranche with zero QoS cost.
2. **Flexibility is already being traded for interconnection speed at GW scale.** Google signed its first formal demand-response agreements (Indiana Michigan Power, TVA, Aug 2025), then expanded to Entergy Arkansas, Minnesota Power, DTE; by early 2026 it reports ~1 GW of DR capacity written into long-term supply contracts, explicitly framed as enabling faster interconnection. A utility counting a data center's flexibility toward interconnection needs an auditable statement of *how much, how long, under what conditions* — which is exactly what a certified envelope is. **The certificate is the product.**
3. **Industry field demos are converging on this gap.** EPRI's DCFlex / Emerald AI Phoenix demonstration (256-GPU cluster, 25% power cut for 3 h) was compute-side only; DCFlex has publicly stated it is preparing demonstration hubs that include cooling and backup-power flexibility. This both validates the direction and sets a clock: estimated window before a cooling-side field demo + follow-up modeling paper closes the domain-first opportunity is **6–12 months**. Speed matters.

Secondary motivation (one sentence each in the paper): ERCOT 4CP transmission-charge avoidance is a 15-minute-window use case that physically matches the cooling loop's time constant; the Duke "curtailment-enabled headroom" study quantifies tens of GW of interconnection headroom for modestly flexible loads.

### 2.2 Why cooling-side, given compute-side is bigger

Honest framing, used verbatim in the paper when needed: compute-side flexibility is deeper (25%+ of facility load) but has QoS cost and activation latency (checkpointing, migration). Cooling headroom is **shallow but free and fast**: the first tranche of any flexibility obligation, deliverable with zero customer impact for tens of minutes. The portfolio view (cooling as bridging resource for compute) is FUTURE WORK — V1 treats workload-only flexibility and batteries as comparison *baselines*, not co-optimized resources (Section 7).

### 2.3 The "reality three-zones" rule (binding)

Real-world institutional detail is allowed to live in exactly three places:
- **Zone 1 — Intro/motivation:** SB6, Google 1 GW, DCFlex, 4CP appear as facts. Zero modeling cost.
- **Zone 2 — Parameters and data:** real ERCOT price series, real Houston dew-point series, Gheni-calibrated plant parameters. This is data, not model structure.
- **Zone 3 — Experiment scenario design:** e.g., one experiment simulates an "emergency call" day; the price scenario set includes a scarcity day.

The **model itself stays stylized** (capacity payment + shortfall penalty, price-taker), exactly as in the original slides, with ONE institutional addition: the product **duration parameter `d`** — included because it is physically forced (a 20–40 min resource cannot pretend to be an unlimited-duration resource), not institutionally decorative. No ECRS rule text, no SB6 rule text, no 4CP mechanics in the formulation. This keeps the formulation universal across PJM/ERCOT/EU, avoids regulatory moving targets, and keeps the theorem set clean.

---

## 3. Literature positioning

### 3.1 The four lines from the slides (verified, keep)

- **Line A — DC as grid flexibility resource:** Takci et al. 2025 (*Energy Reports*, survey); Emerald AI / DCFlex Phoenix field demo 2025 (arXiv 2507.00909, published in a Nature-family journal — **verify exact venue/author list before citing**; slides say "Colangelo et al., Nature Energy"); Acun et al. 2026 (ACM e-Energy, 18–55% AI DC power flexibility — **verify**). All compute-side.
- **Line B — Liquid-cooled DC operations & DR potential:** Gheni et al. 2026 (*Applied Energy*; supply water 17→25 °C yields ~63.3% cooling power reduction — our calibration anchor). Chen et al. 2026 — LCDC DR potential ~30% average power cut for ~20 min, with explicit capacity–duration–rebound trade-off; **note: the matching paper found in search appears to be in *Energy and Buildings*, not Applied Energy — verify the citation before submission.** This paper is our closest neighbor AND the strongest evidence for the duration-mismatch problem our product definition solves.
- **Line C — Thermal storage / prosumer:** Oh 2025 (RTES), Zhang 2025 (Carnot battery), Ravi 2026 (heat prosumer). We differ: no add-on hardware; the loop itself is the resource. Caution: scenario S3 in Phase 1 (buffer tank) is a sensitivity check only — never let it become the main story or we collapse into Line C.
- **Line D — Day-ahead bidding/commitment:** Chen 2023 (bi-level DC bidding, workload-side), Fan & Zhao 2026 (workload day-ahead commitment with deliverability). We adopt their commitment-and-deliverability frame, change the resource.

### 3.2 Four missed lines that MUST be cited (or reviewers from those communities will reject)

1. **Old data-center DR (2010–2016), including cooling-side field tests.** Ghatikar et al. 2012 (LBNL, "Demand response opportunities and enabling technologies for data centers: findings from field studies") field-tested cooling-system DR; chiller/CRAC activation response 2–8 min; up to ~25% site load reduction in tests at four California DCs. Fu, Han, Baker, Zuo ("Assessments of data centers for provision of frequency regulation" — **verify year/venue**) tracked market regulation signals by co-adjusting server frequency and chilled-water supply-temperature setpoint (+3% of design power regulation capacity with chillers active). Wierman et al. 2014 (IGCC survey "Opportunities and challenges for data center demand response"). Citing these is what makes our narrowed claim honest.
2. **Buildings-to-grid reserve provision (the methodological template).** Vrettos & Andersson 2016 (IEEE Trans. Sustainable Energy, "Scheduling and provision of secondary frequency reserves by aggregations of commercial buildings"); Vrettos, Oldewurtel, Andersson 2016 (IEEE Trans. Power Systems, "Robust energy-constrained frequency reserves from aggregations of commercial buildings" — three-level: daily robust capacity allocation → robust MPC every 15–30 min → real-time feedback); Gorecki, Fabietti, Qureshi, Jones 2017 (*Energy and Buildings*, experimental demonstration in the Swiss market); FLEXLAB experiments (Vrettos, Kara, MacDonald, Andersson, Callaway). Our structure is descended from this line; we say so, and we differentiate on: (a) the lower bound is coupled to an *exogenous stochastic variable* (dew point), not a static comfort band; (b) minutes-scale loop dynamics + seconds-scale bursty GPU heat vs. hours-scale building mass; (c) the certified-envelope object itself.
3. **"Certify the max offer" ancestors.** Do-Not-Exceed limits (Zhao, Zheng, Litvinov, IEEE TPS 2015, "Variable resource dispatch through do-not-exceed limit"); dispatchable region literature; dynamic operating envelopes (Australian DER literature, AEMO/CSIRO and follow-on academic work); virtual battery / aggregate TCL flexibility (Hao, Sanandaji, Poolla, Vincent, IEEE TPS 2015, "Aggregate flexibility of thermostatically controlled loads"); flexibility function (Junker et al. 2018, *Applied Energy*); policy-based reserves (Warrington, Goulart, Mariéthoz, Morari, IEEE TPS 2013). Our envelope is a context-dependent DNE limit / dynamic operating envelope for a thermal resource; citing the lineage is a strength.
4. **DR baseline/measurement literature** (baseline gaming, customer baseline load rules, self-reported baseline manipulation). Cited once, in the Remark of Section 5.4, to justify the exogenous-baseline assumption.

### 3.3 Differentiation from the E2E-CDRO paper (in review at TSG — same editorial pool; must be explicit in the paper and cover letter)

| Axis | E2E-CDRO (prior, in review) | ENCORE (this work) |
|---|---|---|
| Decision object | Operating cost (control problem) | Market commitment + certificate (offering problem) |
| Where DRO acts | Online min–sup CDRO-MPC | Offline constraint tightening of the envelope |
| Theory object | Ambiguity set + reformulation | Reachability geometry of deliverability |
| Market layer | None | (q, d) product, settlement, shortfall penalty |
| Real-time layer | Heavy robust MPC | Deliberately simple deterministic MPC + certified fallback (a feature, not a weakness) |

---

## 4. Contributions (final form — exactly three)

- **C1 (Object): The Certified Flexibility Envelope.** Exact characterization of the deliverable (offer q, duration d) set of a liquid-cooled DC under joint hotspot/condensation constraints, as a context-dependent polytope, with a closed-form **weather-coupled thermal virtual battery** equivalent (capacity, power limits, leakage all functions of context — "a battery whose capacity depends on the weather"). [Absorbs: productization, duration triplet, Thm 1.]
- **C2 (Method): Two-stage offering with end-to-end delivery guarantees.** D-1 scenario-based offering constrained to the robustified envelope; D-day cheap rolling MPC with a certified fallback policy; main theorem: any offer inside the tightened envelope satisfies safety almost surely and delivery ratio ≥ ρ with probability ≥ 1 − ε under the contextual ambiguity model. [Absorbs: original C2+C3, Thms 2–3, offline DRO erosion.]
- **C3 (Evidence): Quantified value and realism.** ERCOT prices + Houston humidity + GPU traces + Gheni-calibrated plant. Three quantified findings: (i) value of certification (penalties/violations vs. uncertified and stochastic baselines); (ii) cooling flexibility's position in a portfolio vs. battery and workload-curtailment baselines; (iii) degradation-cost sensitivity of the optimal offer. [Absorbs: degradation supply-curve idea, portfolio comparison, practical-value narrative.]

---

## 5. Problem setting

### 5.1 Timescales
- **D-1 (day-ahead):** hourly offers for the next operating day, decided under forecast uncertainty.
- **D-day (real-time):** rolling control every Δt = 5 min; market interval ΔH = 1 h; plant simulated internally at 30–60 s.
- Plant-level seconds dynamics are NOT simulated in the optimization; they enter via intra-interval peak statistics (Section 6.2) with hardware DVFS named once as the ultimate backstop.

### 5.2 Product definition (the ONE institutional element in the model)
For each hour h the operator offers a pair **(q_h, d)**: "if activated, reduce cooling power by up to q_h (kW) below baseline, sustainable for up to d minutes within the hour." `d` is a product parameter, d ∈ {15, 30, 60} min, fixed per experiment (not optimized jointly in V1). Activation is exogenous: scenario variable r_h ∈ [0,1] = fraction of the hour activated, with r_h · 60 ≤ d. Stylized; maps loosely to short-duration reserve / emergency products without naming any.

### 5.3 Settlement (unchanged from slides)
- Revenue: Σ_h π^cap_h · q_h (capacity-style payment).
- Shortfall: s_h = [r_h q_h ΔH − Σ_{t∈T(h)} (P̄^cool,0_t − P^cool_t) Δt]_+ ; Penalty: Σ_h γ_h s_h.
- Profit = Revenue − RT energy cost − Penalty − degradation proxy cost (Section 6.6).
- γ_h: default 2× π^cap_h equivalent; sensitivity in {1.5, 3}× .

### 5.4 Baseline P̄^cool,0 — exogenous, with the verifiability Remark
The no-offer baseline is **exogenous to the D-1 offering optimization**: computed once as the forecast-based optimal cooling schedule *without* market participation (a separate, prior optimization), then frozen. It is NOT a decision variable co-optimized with q (that is textbook baseline gaming).
**Remark (paper text, two sentences, no theorem):** unlike generic DR loads, the cooling counterfactual is *verifiable*: cooling power is a known physical function of independently metered IT power, weather, and nominal setpoints, so the baseline can be computed and audited by the counterparty from telemetry; manipulating it requires distorting the IT load itself, whose opportunity cost dwarfs DR revenue. Cite DR-baseline-gaming literature once. **Do not build a mechanism-design model.**
**Metering point:** delivery is measured at the **cooling subsystem meter**; the facility-meter discrepancy caused by leakage feedback (Section 6.1) is reported as a result, not a constraint.

### 5.5 Notation anchor (keep symbols compatible with the slides)
x_t = (T_j, T_w, T_f): junction/cold-plate lumped temp, loop coolant temp, facility-loop temp. u_t: virtual input q̇_ext (heat-extraction rate), mapped to physical (ṁ, T_in). ξ_t: disturbances (Q_IT heat load, T_amb, T_dew). q_h, d, r_h, s_h, γ_h, π^cap_h, A_{h,t}, R_{h,t} as in slides. Context c: (job-queue features, weather forecast, thermal state, forecast-residual history).

---

## 6. Modeling architecture

### 6.1 Plant model (2–3 state LTI via virtual input)

**Reference facility:** 1 MW IT, single-phase direct-to-chip (water/PG25), W32-class warm-water loop **with chiller assist available** (this topology assumption is what makes deep pre-cooling — and hence the condensation bound — reachable; state it explicitly in the paper; dry-cooler-only systems cannot approach the dew point and the lower bound is then inactive).

**States and dynamics (continuous, then discretized at 5 min for control / 30–60 s for simulation):**
- C_j dT_j/dt = Q_IT(t) − h_jw (T_j − T_w)
- C_w dT_w/dt = h_jw (T_j − T_w) − q̇_ext(t) [+ optional facility-loop coupling h_wf (T_w − T_f)]
- (optional 3rd state) C_f dT_f/dt = h_wf (T_w − T_f) − q̇_rej(t)
- 2-state version (drop T_f) is the default for the envelope geometry; 3-state for simulation fidelity. Decide in Phase 0; log the decision.

**The virtual-input trick (binding design choice):** the control is q̇_ext directly. The bilinear physical relation q̇_ext = ṁ c_p (T_w − T_in) is handled by a **state-dependent input set** U(x) = { q̇ : reachable by (ṁ, T_in) ∈ [ṁ_min, ṁ_max] × [T_in,min(T_dew), T_in,max] }, inner-approximated by a polytope (in the 1-state-coupling case, box bounds q̇ ∈ [q̇_min(x, T_dew), q̇_max(x)] with affine-in-x bounds). Dynamics stay linear; all nonlinearity lives in U(x). **Do NOT use McCormick relaxations; do NOT put ṁ·ΔT products into the optimization.**

**Cooling power map:** P^cool = P_pump(ṁ) + P_chiller = a_p·ṁ³ (piecewise-affine, 3 segments) + q̇_rej / COP(T_supply, T_wb), COP affine in (T_supply − T_wb) over the operating range. Calibration anchor `[Gheni26]`: raising supply water 17→25 °C cuts cooling power ~63% — fit the COP/pump split to reproduce this trend (trend, not exact number).

**Leakage feedback [CUTTABLE]:** P_IT(T_j) = P_IT,0 · (1 + κ (T_j − T_ref)), κ ∈ [0.001, 0.004] /K `[est, chip literature]`. One coefficient. Purpose: facility-meter net reduction < nominal q (honesty + a detail no market model has). **If it dirties any derivation in Phase 2, demote to a Discussion paragraph and set κ = 0 in the model.** Cut decision logged.

**Constraints:** T_j ≤ T_max (symbolic; default 85 °C lumped proxy `[est]`); T_in ≥ T_dew(t) + δ_cond, δ_cond = 2 K `[est]`; ṁ/ṁ_nom ∈ [0.3, 1.0]; T_in ∈ [18, 45] °C; ramp limits on q̇_ext `[est]`.

**Initial parameter ranges `[est]`, to be calibrated in Phase 0:** coolant inventory 2–6 m³/MW → C_w ≈ 8–25 MJ/K; C_j (silicon+cold plates, lumped) ≈ 0.5–2 MJ/K; loop time constant 5–20 min; facility loop 20–60 min; junction sub-loop seconds–tens of seconds (absorbed into C_j lumping — note the approximation in the paper); Q_IT nominal 1 MW with burst structure from traces (Section 9).

**Phase 0 sanity tests (must pass):** steady-state energy balance closes to <1%; step response time constants in the stated ranges; reproducing the `[Gheni26]` supply-temperature trend direction and magnitude order.

### 6.2 Uncertainty model

- **Uncertain quantities:** per-5-min **peak** IT heat Q̂_IT,t (peak-over-interval statistic computed in trace preprocessing — this is how seconds-scale bursts enter without seconds-scale simulation), dew point T_dew,t (forecast error as AR(1) residual on top of forecast), activation r_h (finite scenario set in D-1).
- **Context c** ∈ R^k: hour-of-day, day-type, planned job mix (train/inference share), weather forecast (T_amb, T_dew), current thermal state, recent forecast residuals.
- **Contextual quantile machinery (reuse E2E-CDRO code where available):** conditional distribution of (Q̂_IT, ΔT_dew) given c via k-NN / kernel conditional estimator; extract (1−ε) conditional quantile **boxes** W(c) (axis-aligned; default ε = 0.1, also run 0.05). Optionally inflate by a Wasserstein radius for the DR statement in Thm 2; V1 may state Thm 2 with conditional-quantile boxes + scenario-style validation if the Wasserstein version resists clean proof — log the choice.
- **DVFS backstop sentence** appears once in the paper; never modeled.

### 6.3 The envelope: deliverability = backward reachability (replaces simulation + ML surrogate)

**Definition.** For nominal context c and disturbance box W, an offer (q, d) is *deliverable from state x* iff there exists an input sequence in U(·) keeping T_j ≤ T_max and T_in ≥ T_dew + δ_cond for all w ∈ W, delivering cumulative reduction ≥ r q ΔH along the activation profile, and steering the terminal state into the **readiness set** R_next (the deliverable set for the next hour's obligation — this replaces the ad-hoc quadratic terminal penalty Φ from the slides; same geometric toolset, unified theory).

**Computation.** With LTI dynamics + polytopic U, X, W: the deliverable set is a polytope projection (Fourier–Motzkin / parametric LP / support functions). 2–3 states × 12 steps (1 h at 5 min) is trivially tractable offline. F(x, c) = max { q : x ∈ BR_q(c) } is **monotone non-increasing in q** → bisection. No ML surrogate; if a fast lookup is needed at runtime, tabulate/interpolate the polytope family over a context grid (interpolation of H-representations only between same-combinatorial-structure neighbors; otherwise nearest-neighbor conservative).
**Robust version:** tighten via Pontryagin difference of the constraint tube by W(c) (standard tube-MPC tightening with fixed feedback gain K, Section 6.5), i.e., margins computed from the closed-loop error set.

**Virtual-battery reparameterization (Thm 1 payload):** map the deliverable polytope to (E_cap(c), P_max(c), P_min(c), self-discharge α(c)) — closed-form in plant parameters and context. Headline sentence: *a thermal virtual battery whose capacity depends on the weather* (rises with hotspot margin, shrinks as dew point rises).

### 6.4 Offline tightening (how CDRO enters — and where it does NOT)

DRO acts **offline only**: conditional quantile boxes W(c) → constraint tightening → tightened envelope F̃(x, c). There is **no online min–sup**. Relative to the slides' CDRO-MPC, this is a *simplification* of the online layer and the enabler of the guarantee. The "value of context" result is geometric: conditional boxes ⊂ unconditional box ⇒ F̃_conditional ⊇ F̃_unconditional ⇒ higher certifiable offers. **This envelope-expansion comparison is the headline figure of the paper.**

### 6.5 Certified fallback + cheap online MPC

- **Fallback:** fixed-gain tube policy u = ū_t + K(x − x̄_t) around a nominal deliverable trajectory; offline robust-feasibility check (convex) certifies it for all w ∈ W(c). "Certified" means exactly: *this simple law exists and is feasible for the whole box*. (Affine disturbance-feedback upgrade = reviewer-response ammunition, NOT V1.)
- **Online:** deterministic MPC (12-step horizon, current forecasts, delivery-tracking constraint A/R as in slides, terminal constraint x ∈ R_next). If infeasible at any step → switch to fallback. Certificate inheritance: MPC-with-fallback is never worse than fallback (Thm 3, textbook recursive-feasibility template).
- Solver: Gurobi via cvxpy (LPs/QPs only in the online layer).

### 6.6 D-1 offering problem

max over {q_h} of Σ_h π^cap_h q_h − E_scenarios[ RT energy cost + Σ γ_h s_h + c_deg Σ_t [T_j,t − T_thr]_+ Δt ]
subject to: (q_h, d) ∈ F̃(x̄_h, c^DA_h) for all h (the envelope constraint — this is where C1 plugs into C2); pre-cooling plan feasibility; scenario set over (workload day-type, dew-point trajectory, activation r_h) — 20–50 scenarios, plain SAA (the distributional robustness already lives inside F̃; do not double-robustify the D-1 objective in V1).
Degradation proxy: single coefficient c_deg ($/K·h above T_thr `[est]`), swept in C3(iii). **No Arrhenius model, no cycling-fatigue model.**

### 6.7 Theorem targets

- **Thm 1 (Envelope geometry & VB equivalence).** For the LTI plant with polytopic U, X, W = {0}: the deliverable set {(x, q)} for fixed (d, r) is a polyhedron; F(x,c) is piecewise-affine, concave in x on its domain, monotone in q; closed-form virtual-battery parameters (E_cap, P_max, P_min, α) as functions of (plant params, T_dew, T_max, x). Proof: projection of a polyhedron + explicit construction.
- **Thm 2 (DR delivery-and-safety guarantee).** If (q, d) ∈ F̃(x, c) (tightened with (1−ε) conditional boxes and tube margins), then under the fallback policy: safety constraints hold for all w ∈ W(c), and P(delivery ratio ≥ ρ | c) ≥ 1 − ε under any distribution consistent with the conditional ambiguity model. (If the Wasserstein-form proof resists, state with quantile boxes + held-out empirical validation; log the choice.)
- **Thm 3 (Certificate inheritance / recursive feasibility).** Online MPC with fallback terminal ingredients is recursively feasible on W(c) and inherits Thm 2's guarantee; closed-loop cost ≤ fallback cost. Template proof (tube MPC); novelty is the application, say so honestly.

---

## 7. Scope control (binding lists)

**IN the model (5 items, two of which are simplifications):**
1. Duration-parameterized product (q_h, d) — replaces pure hourly capacity.
2. Reachability/polytope envelope — replaces simulation + ML surrogate.
3. Offline conditional-quantile tightening — replaces online min–sup CDRO-MPC (a deletion).
4. Certified fixed-gain fallback + cheap deterministic online MPC (a simplification of the online layer).
5. Leakage feedback term κ [CUTTABLE → Discussion paragraph if it dirties Phase 2].

**DOWNGRADED (remarks / parameters / scenarios — never constraints or mechanisms):**
- Verifiable baseline → exogenous baseline + 2-sentence Remark (5.4). No mechanism design, no proposition.
- Degradation → one proxy coefficient c_deg + one sensitivity figure.
- Intra-interval bursts → peak-over-interval statistic in trace preprocessing + one DVFS sentence.
- Activation uncertainty r_h → scenario parameter in D-1. Rebound → readiness terminal set (structural) + one consecutive-activation stress-test experiment (no cross-hour chaining constraints).
- ERCOT/SB6/4CP institutional detail → Zones 1–3 only (Section 2.3).

**CUT (future work, one sentence each at most, or silence):**
- Compute-assist / bridging-resource co-optimization (dilutes the cooling-side brand; battery and workload appear as comparison baselines only — their models are deliberately simple: battery = ideal energy/power-limited storage; workload = capped curtailment with linear opportunity cost).
- Bidirectional product (negative-price down-flex / pre-cool absorption).
- Strategic bidding / price-maker; multi-DC or multi-CDU aggregation; affine disturbance-feedback policies; mechanism design for baselines; two-phase cooling; CFD-grade thermal detail; online DRO.

**Anti-scope-creep rule for the agent:** any new feature idea goes into `notes/PARKING_LOT.md` with one line of rationale — and out of the code.

---

## 8. Experiment & evaluation plan (C3)

**Controllers/baselines (6):**
B1 No-market MPC (cooling-only optimum; defines baseline P̄^cool,0).
B2 DA offering + deterministic MPC (no robustness, naive envelope = deterministic F).
B3 DA offering + scenario-stochastic MPC (no certificate).
B4 **ENCORE** (tightened envelope + fallback + cheap MPC).
B5 Battery baseline (same revenue product served by an ideal BESS sized to matched capex band; simple model).
B6 Workload-only curtailment baseline (capped, linear opportunity cost).

**Metrics:** economic — profit, Σq_h, delivery ratio, shortfall penalty, recovery (rebound) energy cost; safety — hotspot violation count/magnitude, condensation-margin violations, certificate validity (empirical violation rate vs ε); robustness — AI-burst day, dew-point-shift day, consecutive-activation stress test.

**Three headline figures:**
F1 *Value of context*: envelope volume / max certifiable q under unconditional vs conditional tightening, across humidity regimes. (The money figure.)
F2 *Portfolio positioning*: profit & violation scatter of B1–B6; cooling flexibility as the zero-QoS first tranche.
F3 *Degradation sensitivity*: optimal Σq_h and profit vs c_deg sweep.

Plus the standard table: all controllers × all metrics × 3 representative weeks (mild / humid-summer / scarcity-price), 20+ Monte Carlo seeds; report mean ± std.

**Honest-result clause:** if the tightened envelope is near-empty in humid weeks (Risk R2), report it as a finding — "uncontextualized certification of liquid-cooling flexibility is nearly impossible in humid climates; context recovers X%" — which strengthens F1 rather than killing the paper.

---

## 9. Data & calibration sources

- **Prices:** ERCOT day-ahead energy (settlement point: a Houston-area hub) + a short-duration AS price series as π^cap proxy; include summer scarcity days. Source: ERCOT MIS public reports (downloaded manually by owner if scraping is blocked; agent should generate the exact file list needed).
- **Weather/dew point:** NOAA/Iowa Environmental Mesonet, station KIAH (Houston Intercontinental), hourly T_amb/T_dew, ≥2 full years.
- **IT heat traces:** Alibaba GPU cluster trace (2020/2023) and/or Azure LLM inference traces; preprocessing recipe: map utilization → power via affine GPU power model, aggregate to 1 MW hall, compute per-5-min mean AND peak series; synthesize burst overlays (square bursts, 1–10 min, magnitude from trace tail quantiles) for stress days.
- **Plant calibration:** Gheni et al. 2026 trends (supply-temp vs cooling-power curve) + ranges in 6.1. If the owner supplies the E2E-CDRO plant code, port and adapt; else implement fresh per 6.1.
- All datasets cached under `data/` (gitignored), with `data/README.md` documenting source, URL, retrieval date, preprocessing script hash.

---

## 10. Risk register

- **R1 — Virtual-input polytope fails** (U(x) inner approximation too lossy, or projection degenerates). Detection: Phase 2 cross-validation < 95% agreement. Plan B: fall back to the slides' sampling + surrogate envelope; paper drops to Applied-Energy-grade theory; still publishable. Decision at Phase 2 gate.
- **R2 — Envelope collapses under Houston humidity variance.** Plan B: it's an honest headline finding (see 8); also report a drier-climate sensitivity (e.g., Phoenix weather) as contrast.
- **R3 — Reviewer overlap with E2E-CDRO → "incremental".** Mitigation: Section 3.3 table goes into the paper + cover letter; online layer is *simpler* by design — frame as contribution.
- **R4 — Scooped by a cooling-side field demo + fast modeling paper (DCFlex pipeline).** Mitigation: speed; V1 full draft target ≤ 2 months from Phase 0; if a demo publishes mid-project, cite it as motivation (it validates, doesn't duplicate, unless it includes day-ahead certified offering — monitor).
- **R5 — Thm 2's Wasserstein form resists clean proof.** Plan B in 6.2/6.7: quantile-box version + empirical validation; acceptable for TSG if stated precisely.

---

## 11. Phase plan with acceptance criteria

> Convention: each phase ends with `results/phaseN/SELF_AUDIT.md` (what was built, what passed, what was logged to DESIGN_DECISIONS.md, open risks). Acceptance is trend-based where numeric: match direction and order of magnitude, not exact values. **Phases 1 and 2 are GO/NO-GO gates: produce the memo and STOP.**

**Phase 0 — Bootstrap & plant.** Repo scaffold (Section 12), environment, config-driven plant implementation (2- and 3-state), simulation harness, unit tests.
*Acceptance:* energy-balance closure <1%; step-response time constants within 6.1 ranges; Gheni supply-temp trend reproduced in direction and order (~tens of % cooling-power cut for 17→25 °C); pytest green; `results/phase0/` contains step-response plots + parameter table with source tags.

**Phase 1 — Duration accounting (GO/NO-GO gate #1).** Compute the q–d frontier: max sustainable cooling-power cut vs duration d ∈ {5,…,60} min, under scenarios S1 (coolant loop only), S2 (+facility loop), S3 (+small buffer tank, sensitivity only), each × {nominal, burst} workload × {pre-cooled to ready state, nominal start}.
*Acceptance:* `results/phase1/DURATION_MEMO.md` with frontier plots, a table, and an explicit recommendation of product duration d* and plausible q ranges; sanity expectation (trend): S1 full-depth cut sustainable for ~20–40 min order (consistent with Chen et al.'s ~30%/~20 min); memo states the GO/NO-GO rule: **GO if S2 sustains ≥15–20% of cooling power for d = 30 min**; if not, recommend product redefinition. **STOP after the memo.**

**Phase 2 — Deterministic envelope geometry (GO/NO-GO gate #2).** Implement BR-set projection, F(x,c) bisection, readiness sets, VB reparameterization.
*Acceptance:* cross-validation vs brute force — sample ≥2,000 (x, q, c) points, check polytope membership against direct open-loop feasibility LP; agreement ≥98% (mismatches analyzed in memo); monotonicity of F in q verified numerically; VB closed-form vs polytope volume consistency; envelope shrinks monotonically as T_dew rises (plot); `results/phase2/ENVELOPE_MEMO.md` with GO/NO-GO on the geometric route (R1 decision). **STOP after the memo.** *Showable-artifact milestone after GO:* git tag, zip with src/tests/config/DESIGN_DECISIONS.md/results/phase2 + WALKTHROUGH.md (math → code refs → cross-validation table).

**Phase 3 — Tightening + fallback.** Conditional quantile boxes W(c), tube margins with fixed K, tightened F̃, fallback robust-feasibility certification, online MPC with fallback switch.
*Acceptance:* on ≥500 held-out disturbance scenarios per context bin: zero safety violations inside F̃; empirical delivery-failure rate ≤ ε (with binomial CI reported); fallback engages and recovers in injected worst-case runs; conditional F̃ ⊋ unconditional F̃ demonstrated (proto-F1 figure).

**Phase 4 — D-1 layer + settlement simulator.** Scenario-based offering (6.6), baseline P̄^cool,0 generator, settlement accounting.
*Acceptance:* end-to-end one simulated day runs B1→B4; profit decomposition reconciles to the settlement formulas exactly; offers respect F̃ by construction (assert in code).

**Phase 5 — Closed loop + all baselines.** B1–B6 implemented and smoke-tested on 3 representative weeks.
*Acceptance:* all 6 controllers complete all weeks without crashes; metric table generated; qualitative sanity: B2 shows violations/penalties under burst days that B4 avoids; B4 profit ≥ B1. *Showable-artifact milestone #2.*

**Phase 6 — Full experiments & figures.** F1–F3 + main table + stress tests, 20+ seeds.
*Acceptance:* figures publication-grade (matplotlib, consistent style file); every number in figures regenerable by one `make figures`; results provenance manifest.

**Phase 7 — Paper drafting.** Handled with owner supervision (not autonomous); guide Sections 1–4, 13 are the outline skeleton.

---

## 12. Engineering conventions

```
encore/
  guide.md                  # this file — the constitution
  DESIGN_DECISIONS.md       # append-only log: date, question, decision, rationale
  PROGRESS.md               # phase status, resumable state pointers
  notes/PARKING_LOT.md      # scope-creep quarantine
  config/                   # plant.yaml, market.yaml, uncertainty.yaml, experiment yamls
  src/encore/
    plant/                  # dynamics, power maps, U(x) polytope
    envelope/               # BR projection, bisection, VB params, readiness sets
    tighten/                # conditional quantiles, tube margins
    control/                # fallback, online MPC
    market/                 # D-1 offering, baseline generator, settlement
    data/                   # loaders & preprocessing (traces, weather, prices)
  experiments/              # one runnable script per figure/table, config-driven
  tests/                    # pytest: energy balance, monotonicity, settlement reconciliation
  results/phaseN/           # plots, memos, SELF_AUDIT.md (committed)
  data/                     # raw/cached datasets (gitignored) + data/README.md
```

Rules: Python 3.12, user-local env (conda/venv); cvxpy + Gurobi (license via `GRB_LICENSE_FILE` env var — **never commit license material**); numpy/scipy; polytope ops via `polytope`/`pypoman`/`pycddlib` (pick in Phase 0, log it); deterministic seeds everywhere; every experiment writes a provenance JSON (git hash, config hash, seed); no GPU needed before Phase 5 (and likely never); runtimes: any single offline envelope computation should stay <minutes, full Phase 6 sweep <hours on a workstation. Plots: one shared mplstyle; label axes with units; no screenshots as results.

---

## 13. Writing rules for the paper (Phase 7, recorded now)

- Use the exact novelty claim from Section 1; never the forbidden claims.
- Related work must include all four missed lines (3.2) with the differentiation sentences provided there.
- Reality stays in its three zones (2.3). The formulation section contains zero ISO names.
- The E2E-CDRO differentiation table (3.3) appears in the intro or related work AND the cover letter.
- Tone: claims sized to evidence; the duration limitation, the topology assumption (chiller assist), the metering-point choice, and the DVFS backstop are stated plainly — pre-empting the known reviewer attacks: duration mismatch → product parameter d; baseline gaming → Remark 5.4; "why not a battery / why not compute" → F2 + Section 2.2 framing; "does condensation ever bind" → topology assumption + Houston data; "5-min control vs second bursts" → peak statistics + DVFS sentence; "ERCOT-specific" → stylized model, Zone-2 data only; "hardware validation" → Gheni calibration + DCFlex/Emerald ecosystem motivation.
- References flagged **verify** in Section 3 must be checked against the actual papers before any citation is written.

---

## Appendix A — Reference shortlist (full bibliographic check required at Phase 7)

Slides' own: Takci'25 Energy Reports; Emerald/DCFlex demo (arXiv:2507.00909; Nature-family venue — verify); Acun'26 ACM e-Energy (verify); Gheni'26 Applied Energy; Chen'26 LCDC DR potential (venue: verify — search suggests Energy and Buildings); Oh'25; Zhang'25; Ravi'26 Applied Energy; Chen'23 Energy; Fan & Zhao'26 arXiv.
Missed-line anchors: Ghatikar et al. 2012 (LBNL field studies); Fu, Han, Baker, Zuo (DC frequency regulation; verify year/venue); Wierman et al. 2014 (IGCC); Vrettos & Andersson 2016 (TSE); Vrettos, Oldewurtel, Andersson 2016 (TPS); Gorecki et al. 2017 (Energy & Buildings, Swiss market experiments); Warrington et al. 2013 (TPS, policy-based reserves); Hao et al. 2015 (TPS, TCL virtual battery); Junker et al. 2018 (Applied Energy, flexibility function); Zhao, Zheng, Litvinov 2015 (TPS, DNE limits); dynamic operating envelopes (AEMO/CSIRO + academic follow-ons); Campi & Garatti 2008 (scenario approach — only if used); DR baseline-gaming literature (one representative cite).
Context facts (Intro): Texas SB6 (June 2025; PUCT implementation ongoing — cite statute + one law-firm summary); Google DR agreements (Aug 2025 I&M/TVA; ~1 GW by early 2026); EPRI DCFlex; Duke curtailment-headroom study (Norris et al. 2025).

## Appendix B — Symbol table

| Symbol | Meaning | Unit |
|---|---|---|
| q_h | offered cooling-power reduction, hour h | kW |
| d | product duration parameter | min |
| r_h | activation fraction of hour h (scenario) | – |
| P̄^cool,0_t | exogenous no-offer cooling baseline | kW |
| P^cool_t | realized cooling power | kW |
| A_{h,t}, R_{h,t} | accumulated delivery / remaining obligation | kWh |
| s_h, γ_h | shortfall, penalty rate | kWh, $/kWh |
| π^cap_h | capacity payment | $/kW·h |
| T_j, T_w, T_f | junction-lump, loop coolant, facility-loop temps | °C |
| q̇_ext | virtual input: heat extraction rate | kW |
| ṁ, T_in | physical inputs: flow, supply temp | kg/s, °C |
| T_dew, δ_cond | dew point, condensation margin | °C, K |
| Q_IT, Q̂_IT | IT heat load (mean / per-interval peak) | kW |
| W(c) | conditional (1−ε) disturbance box | – |
| F, F̃ | envelope (nominal / tightened) | kW |
| c, c_deg, κ | context vector; degradation proxy coef; leakage coef | –, $/K·h, 1/K |
| Δt, ΔH | control / market interval | 5 min, 1 h |
