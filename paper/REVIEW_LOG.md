# REVIEW_LOG — five-persona simulation, frozen concern table (2026-06-11)

Reviewers: A data integrity (11 items), B math/physics (17), C overclaims (22),
D style (13, APPLIED), E fresh-reader/TPC (28). Owner delegated approval
(final-draft mandate); all accepted items applied serially below.

## Consensus items (fixed first)
- A-7 = E-1: Table II bold criterion contradicted by B5/B6 rows → caption restated.
- A-2 = B-15 = E-22: "37 decisions" → 28 decisions / 183 rows.
- A-3 = E-18: 8× → ≈7×.
- B-14 = C-20 = E-8: empirics removed from proofs; VB proposition demoted to prose.
- B-3 = E-2: validation paragraph rewritten — failures attributed to warm starts as
  MECHANISM, cold-start gate is what Thm 2 directly tests; no in-ball claim without
  measurement.
- B-4 = C-11: conformal coverage stated as marginal-under-local-exchangeability;
  deployed conditioning (hour-of-day) disclosed; selection remark added.
- B-5 = C-12 = (A-6): VB stated as closed-form approximation with d>=15 qualifier;
  45 kWh scoped to the coolant tranche; discharge-limit mechanism corrected.
- C-15 (= guide §13): second DVFS mention in methodology deleted (D-3 edit amended).
- C-14: ERCOT/Houston removed from methodology.

## Disposition
- ACCEPTED + APPLIED: A-1..A-11; B-1,B-2(restated lemma),B-3,B-4,B-5,B-7(cap
  clause),B-9,B-10,B-11,B-12,B-13,B-14,B-15,B-16(i-iv);
  C-1..C-22; D-1..D-13; E-1..E-21,E-23..E-25,E-27,E-28.
- ACCEPTED, NOTED IN LIMITATIONS instead of rerun: B-8 (frozen-COP metering on both
  sides + fixed T_wb disclosed as setup convention; symmetric across B2-B4),
  B-17 (linear scaling of depth in loop inventories stated; no C_w rerun).
- DECLINED: B-6 fix-option(a) (proving MPC-layer corollary) — option (b) taken:
  corollary demoted to remark; headline runs use the fallback (matches code).
  B-16(v) operating-box footnote (clutter; LOW). E-26 superseded by D-13.
- E-16 author affiliations: inserted with %% OWNER-VERIFY comments.

Build after every file batch; bibtex rerun; pages kept in [10, 10.5].
Final fresh-reader verification pass run on the revised PDF (see end of file).

## Final fresh-reader verification (clean context, post-revision)

8 issues found, all fixed: frontier table 61.7pt overflow (recomposed);
settlement equation 44.6pt overflow (re-aligned; eq:box likewise); F1/F2 result
figures printed internal pipeline titles with undefined jargon (S2,
jobaware_eps03) — figures regenerated paper-clean from committed artifacts;
"controller-days" -> "day-seeds" (one echo); duplicate R(q) definition removed;
1.9 K claim scoped to the held-out replay (stress days reach 2.2 K); shortfall-cap
parenthetical moved next to s_h; Table II caption now defines "in-domain".
Verifier confirmed CLEAN: all number echoes (40+ items), LaTeX integrity (0
undefined refs/citations), no printing placeholders, theorem apparatus
consistent after demotions, Algorithm 1 self-contained, terminology consistent.

Final state: 10.0 pages, 29 references, 2 negligible overfull boxes (3.0pt,
1.5pt), compiles clean with bibtex. Owner inputs outstanding: 6 bibliography
entries marked %% OWNER-VERIFY in refs.bib (slide-sourced titles/volumes) and
the affiliation/funding block in main.tex.
