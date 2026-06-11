# ENCORE — paper outline (IEEE TSG; guide §1–4, §13 skeleton; owner-supervised)

**Title (working):** Certified Cooling-Side Flexibility for Liquid-Cooled AI Data
Centers: Context-Dependent Envelopes, Day-Ahead Offering, and End-to-End Delivery
Guarantees

**Novelty claim (guide §1, verbatim discipline):** the certified flexibility envelope —
an exactly characterized, context-dependent, weather-coupled deliverable set for
cooling-side (q, d) products — plus a two-stage offering scheme whose delivery
guarantee survives from day-ahead commitment to real-time control.

## I. Introduction
- Hook: AI DC load growth + grid scarcity (SB6, Google DR, EPRI DCFlex — Zone 1 only).
- Gap: compute-side flexibility is demonstrated (Colangelo'25 arXiv, Acun'26);
  cooling-side thermal inertia is quantified (Gheni'26 [+ Chen'26 if resolved]) but
  never CERTIFIED as a market product; duration mismatch is the blocker.
- Contributions C1/C2/C3 exactly as guide §4.
- E2E-CDRO differentiation table (§3.3) here or in II.

## II. Related work — the four lines (§3.1) + four missed lines (§3.2)
  with the differentiation sentences from the guide, verbatim where possible.

## III. Problem setting (guide §5)
- Timescales; product (q, d) — the ONE institutional element; settlement 5.3
  (whole-hour energy, γ-penalty); exogenous baseline + Remark 5.4 (baseline gaming).

## IV. Plant model (guide 6.1–6.2)
- 2/3-state virtual-input LTI; state-dependent affine U(x); condensation floor;
  context vector c; peak statistics + the single DVFS sentence.
- Setup conventions stated plainly: load anchoring at 1 MW nominal, lumped 85 °C
  hotspot proxy, frozen-COP surrogate.

## V. The certified flexibility envelope (C1; guide 6.3, Thm 1)
- Lifted deliverability polyhedron; F(x,c); exact projections; readiness sets;
  weather-coupled virtual battery closed forms (capacity = f(context)).
- The whole-hour settlement alignment (window cap AND hour energy — D-048 as a
  modeling necessity, presented as part of the product semantics).

## VI. Two-stage offering with delivery guarantees (C2; guide 6.4–6.7, Thms 2–3)
- Conformal conditional disturbance sets W(c) with a-priori face allocation.
- NESTED sets: W_safe (ε_safe) for the safety clause, W_del (ε_del) for the delivery
  clause — Thm 2 stated with both clauses; failures beyond W_del are priced (γ).
- Tube margins with fixed gain; e₀ pre-positioning lemma (disturbance-aware bound
  e_ss ~ w̄/K_rec for the sprint recovery law); adjacency-pruned commitments
  (empty fixed point ⇒ recovery hour by construction).
- D-1 offering with expected-penalty term; D-day cheap MPC + certified fallback.

## VII. Case study (C3; Phase 6 artifacts, all regenerable by `make figures`)
- Data: PAI trace + causal job-aware DA forecast; ERCOT 2024 (10 weeks);
  KIAH obs + archived NWP dew forecasts. All real, end-to-end.
- F1: certification wall + the information arrow (climatology 40.7 → job-aware
  74.6 kW on the SAME real hall). Finding: what blocks certification is day-ahead-
  unforecastable SUSTAINED load (energy face), not bursts; job information moves it.
- Main table: B1–B6, 10 weeks × 20 seeds; scarcity week $97/day/MW at 414 kW/day;
  avg $10.6 vs B2 price ceiling $35 (honest framing: value is scarcity-concentrated;
  B4 ≈ 30% of ceiling with 0 in-certificate violations vs B2's 229 violation-days).
- Certificate validation: 0 in-W_safe episodes, 0 clean-in-box failures, CP bounds;
  beyond-box ≤1.6 K = DVFS domain (stated as Thm-2's conditional scope).
- F3 degradation supply curve; stress tests (beyond-box, graceful).
- Portfolio framing: per-MW; 100 MW campus ≈ $390k/yr, zero capex/QoS.

## VIII. Limitations & outlook
- Duration limitation, topology assumption, metering point, DVFS backstop (the four
  pre-empted attacks, guide §13); price-limited average value; d=15 layering, affine
  feedback, per-context gains as future work.

## NOT in the paper (owner decision 2026-06-11)
- The development-iteration history (rejected design variants) stays in
  DESIGN_DECISIONS.md only. The paper presents the final design with its a-priori
  justifications. Scope-defining limitations (conditional safety, priced failures,
  price-limited value) STAY in the paper — they are shields, not targets.

## Drafting order (proposed)
1. VII (results exist → write around frozen artifacts) → 2. V–VI (theory, needs the
   e₀ lemma + nested-set Thm-2 statement) → 3. IV, III → 4. II, I → 5. VIII, abstract,
   cover letter (with E2E-CDRO differentiation).
