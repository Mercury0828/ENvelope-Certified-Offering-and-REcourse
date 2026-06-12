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

## Owner revision round (2026-06-11, 7 directives)

1 affiliations removed; 2 envelope-slices figure moved to IV (now IV-B with the
duration sweep); 3 main table tripled (3 blocks x 8 settlement-decomposition
columns incl. the negative-DeltaWear finding); 4 F1 -> single-column stacked
flat panels; 5 portfolio/F3 flattened; 6 added Fig day-trace (new closed-loop
sim, B2 crosses Tmax verified on-figure), Fig weekly-value bars, Fig duration
sweep, Table stress; text trimmed around them; 7 page budget relaxed -> final
10.7 pages (11 phys., last page 71%). All figures regenerated via
experiments/paper_figures.py from committed artifacts + one logged day-sim.

## External-review response round (2026-06-11, 6 major + 8 minor concerns)

R1 market realism: Remark (market realism) added to II-C; economic claims
   reworded to "under the ERCOT-price-driven stylized reserve settlement"
   (abstract/IV/conclusion); p_act x gamma offering sensitivity run (smooth,
   -20% commitment from p_act 0.05->0.30, -8% value gamma 1.5->3).
R2 theorem premise: start errors LOGGED on a fresh 20-seed nested replay.
   certified starts (envelope-feasible 22 or in-ball 17): ZERO failures; all
   24 failures beyond both conditions (median displacement 4.1 K), inside the
   priced budget. IV-E rewritten with premise accounting; abstract/conclusion
   updated to "zero failures among certified starts".
R3 model validation: envelope-level sensitivity table (C_w/C_f/h_jw +-20%,
   delta_c+1K, e0x2, COP-20%) added — certificate FAILS SAFE (h_jw-20%, e0x2
   zero the offer); worst-direction simultaneous-mismatch closed loop reported
   (violations up to 5.6 K) with conservative-identification guidance.
R4 ablations (owner-flagged essential): 4 ablated variants replayed over all
   ten weeks; new Table — single eps=0.3 (+47% value, 18 viol-days 4.9K:
   safety eroded), single eps=0.05 (-20% value), context-free (-24%),
   window-only (3 clean-in-box failures, 82% fail rate: certificate broken).
   Nested design uniquely combines 0 breaks + bounded excursions + value.
R5 conformal transparency: k/k_cal/features/allocation rationale added to
   III-B; nesting-direction reminder added.
R6 scarcity framing: "low-capex scarcity resource, not a high-utilization
   arbitrage asset" adopted.
Minor: Table I cell de-advertised; abstract density reduced (40.7->74.6
   dropped, 83% kept); job-aware mechanism sentence added; DVFS trigger +
   workload-impact scoping added; Fig.6 ylim from negative; main table 12 cols.
Declined/deferred: robust-MPC/DRO offering as full baselines (the single-set
   and context-free ablations cover the risk-level axis; B2 already runs the
   same MPC machinery — stated in IV-A); per-season coverage table (selected-
   hour validation is what the certificate gates; noted).
Final: 12 phys. pages (~11.4 content) per relaxed budget; suite 51/51.

## Baseline restructuring (owner, 2026-06-11): B7 single-risk robust + B8 context-free promoted into Table III with full 20-seed/3-block statistics (mainline_b7b8.csv); ablation table kept at 5 rows with cross-reference footnote; B2 = online-MPC-without-envelope mapping and B7 = robust-MPC/DRO-family proxy stated in IV-A; table footnotes moved outside tabular (fixed 761pt natural-width overflow).

## Full-paper verification round (owner, 2026-06-11): two clean-context verifiers. Logic: 7 fixed (portfolio fig regenerated WITH B7/B8; B5/B6 MV footnote; fit-block gloss; ECRS in Remark 2; limits (iii) incl B7-B8; eqref-below). Data: 230+/240 numbers re-derived exactly; 3 MED prose fixes (failed-starts median 7.0K; sweep -18% full; beyond-domain 5+5 split); LOWs (wear convention, ablation 38). 19% figure verified vs jobaware_stats.json. Verdict: claims supported at stated n; certified-start bound CP95<=15.4% stated honestly.
