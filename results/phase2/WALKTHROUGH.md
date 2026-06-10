# WALKTHROUGH — the certified-envelope component (showable artifact, Phase 2)

One focus component, math → code → numerical evidence, per the showable-artifact
milestone (guide §11). Audience: a colleague who has read guide.md §6.1–6.3.

## 1. Math

**Plant (guide 6.1).** LTI virtual-input form, x = (T_j, T_w) [2-state] or
(T_j, T_w, T_f) [3-state], u = q̇_ext (and q̇_rej), exact ZOH at Δt = 5 min:

    x_{t+1} = A_d x_t + B_d u_t + E_d Q_IT

All (ṁ, T_in) bilinearity lives in the state-dependent box U(x):

    ṁ_min c_p (T_w − T_in,max) ≤ q̇_ext ≤ ṁ_max c_p (T_w − max(T_in,min, T_dew + δ_cond))
    [3-state adds q̇_ext ≤ ṁ_max c_p (T_w − T_f − δ_hx)]

**Deliverability (guide 6.3).** (q, d) deliverable from x₀ iff ∃ u₀…u_{N−1} (N = 12,
one hour) with: safety T_j,t ≤ T_max (and T_f,t ≤ T_f,max) for all t; inputs in U(x) at
both step endpoints; cumulative delivery Σ_{t∈A}(P̄ − P_t)Δt ≥ r q ΔH over the
activation window A = first r·N steps, r = d/60; terminal x_N ∈ R (readiness);
P_t through the conservative affine surrogate P_t = P_pump + q̇_rej,t/COP_ref.

Substituting the dynamics, every constraint is affine in z = (x₀, q, u): the
deliverable set D = {(x₀, q) : ∃u, Gz ≤ h} is the projection of a polyhedron — hence a
polyhedron (Thm 1 skeleton), F(x,c) = max{q : (x,q) ∈ D} is a parametric LP value,
monotone in q, and the readiness set is the fixed point R = proj_x D(R).

## 2. Code map

| Object | File | Key function |
|---|---|---|
| ZOH dynamics, U(x) | [src/encore/plant/dynamics.py](../../src/encore/plant/dynamics.py), [virtual_input.py](../../src/encore/plant/virtual_input.py) | `discrete_matrices`, `q_ext_bounds` |
| Lifted polyhedron Gz ≤ h | [src/encore/envelope/reachability.py](../../src/encore/envelope/reachability.py) | `build_lifted(p, EnvelopeSpec)` |
| F(x,c), membership, trajectories | [src/encore/envelope/geometry.py](../../src/encore/envelope/geometry.py) | `max_q`, `is_member`, `extract_trajectory` |
| Exact x-plane slices + runtime lookup | same | `project_slice` (Bretl–Lall), `TabulatedEnvelope` |
| Readiness fixed point | [src/encore/envelope/readiness.py](../../src/encore/envelope/readiness.py) | `readiness_iteration` |
| Virtual-battery closed forms | [src/encore/envelope/virtual_battery.py](../../src/encore/envelope/virtual_battery.py) | `vb_params`, `vb_frontier` |
| Tests (12 envelope + 33 plant/duration) | [tests/](../../tests/) | `pytest -q` → all green |

## 3. Numerical evidence

**Cross-validation** (`experiments/phase2_envelope_xval.py`, seed 20260610):

| Check | n | Result |
|---|---|---|
| Polygon membership ≡ feasibility LP (on-grid) | 1,200 | 100.00% agreement |
| Tabulated lookup vs LP (continuum, conservative snap) | 1,200 | 99.00%, 0 anti-conservative |
| 30-s re-simulation of LP-optimal trajectories | 400 | states match to 1e-6 at 5-min marks; worst intra-step T_j excursion +0.39 K |
| Consistency with Phase-1 frontier (independent bisection code) | — | F(event-only) = 64.30 kW ≡ Phase-1 64.30 kW (2-state); 171.0 ≡ 171.0 kW (3-state) |
| VB closed form vs LP frontier | 48 cells | median 0.9%, worst 2.7% (d ≥ 15 min) |

**Degenerate-case handling:** 526/1,500 tabulation cells are empty (deep cuts in humid
contexts) — detected and stored as empty, never silently extrapolated.

**vs-degenerate comparison:** dropping the condensation floor (T_dew → −∞) inflates the
pre-cooled d=30 frontier from 62.3 to 92.7 kW at dew 24 °C — i.e., a certification that
ignores the dew-point side would over-promise by ~49% on a humid day; this is the gap
the joint hotspot+condensation certificate closes (cf. `envelope_vs_dewpoint.*`).

Reproduce: `python experiments/phase2_envelope_xval.py && python experiments/phase2_envelope_geometry.py`
(env: venv `encore`, Python 3.12; provenance JSONs alongside the artifacts).
