# Phase 7 — citation verification memo (guide §3 / Appendix A; 2026-06-11)

## Verify-flagged items — RESOLVED

| Ref | Guide flag | Verified result | How to cite |
|---|---|---|---|
| Emerald AI / DCFlex Phoenix demo | "Nature-family venue — verify" | **arXiv:2507.00909 ONLY — no journal-ref as of 2026-06-11.** Title: "Turning AI Data Centers into Grid-Interactive Assets: Results from a Field Demonstration in Phoenix, Arizona". Authors: **Colangelo, Coskun, Megrue, Roberts, Sengupta, Sivaram, Tiao, Vijaykar, Williams, Wilson, MacFarland, Dreiling, Morey, Ratnayake, Vairamohan**. 256-GPU cluster, 25% power reduction for 3 h, Oracle/NVIDIA/SRP via EPRI DCFlex. | Cite as arXiv preprint (Colangelo et al., 2025). **Slides' "Nature Energy" claim is NOT supported — do not use.** Re-check journal-ref at submission. |
| Acun et al. 2026 | "ACM e-Energy — verify" | **Confirmed**: "Investigating Power Consumption Flexibility of AI Data Centers", ACM e-Energy '26 (Banff, June 2026); BU PEAC Lab (Coskun group); 18–55% flexibility across AI workload types. | Cite e-Energy '26 proceedings (Acun et al., 2026). Grab final author list from the proceedings PDF at bib compile. |
| Fu, Han, Baker, Zuo | "verify year/venue" | **Confirmed**: "Assessments of data centers for provision of frequency regulation", **Applied Energy 277 (2020) 115621**. Server power mgmt + chilled-water supply-temp setpoint co-control; +3% of design power regulation capacity with chillers active. | (Fu et al., 2020, Applied Energy). |
| Chen et al. 2026 LCDC DR potential | "venue: verify — search suggests Energy and Buildings" | **NOT FOUND** in three targeted searches. | **DROPPED (owner decision 2026-06-11)**: duration-mismatch motivation re-anchors on Gheni'26 + Ghatikar'12 + Acun'26; "closest neighbor" framing removed. |

## Spot-checked anchors (consistent with known bibliography; capture DOIs at bib compile)

- Takci, Day, Qadrdan 2025, *Energy Reports* — "Data centres as a source of flexibility for power systems" (ScienceDirect pii S2352484725001623). ✓
- Ghatikar et al. 2012, LBNL report — DC DR field studies, cooling DR 2–8 min response, ~25% site load. ✓
- Wierman et al. 2014, IGCC — "Opportunities and challenges for data center demand response". ✓
- Vrettos & Andersson 2016 (IEEE TSE); Vrettos, Oldewurtel, Andersson 2016 (IEEE TPS, robust energy-constrained reserves, three-level structure). ✓
- Gorecki et al. 2017, *Energy and Buildings* (Swiss market experimental demo). ✓
- Zhao, Zheng, Litvinov 2015 (IEEE TPS, do-not-exceed limits). ✓
- Hao, Sanandaji, Poolla, Vincent 2015 (IEEE TPS, TCL aggregate flexibility / virtual battery). ✓
- Junker et al. 2018, *Applied Energy* (flexibility function). ✓
- Warrington, Goulart, Mariéthoz, Morari 2013 (IEEE TPS, policy-based reserves). ✓
- Norris et al. 2025 (Duke Nicholas Institute, "Rethinking Load Growth" curtailment headroom). ✓
- Texas SB6 (June 2025, PUCT implementation ongoing); Google DR agreements (Aug 2025, I&M/TVA). ✓ (cite statute + one law-firm summary; one news/IR source)

## Budget (owner constraints, 2026-06-11)

Target: IEEE Trans. Smart Grid, **10–10.5 pages total, ≤30 references.**
Curated list (28): Takci'25; Colangelo'25 arXiv; Acun'26; Gheni'26; Oh'25; Zhang'25;
Ravi'26; Chen'23; Fan&Zhao'26; Ghatikar'12; Fu'20; Wierman'14; Vrettos'16 TSE;
Vrettos'16 TPS; Gorecki'17; Zhao'15 DNE; dynamic operating envelopes (1 representative);
Hao'15; Junker'18; Warrington'13; baseline-gaming (1); Lei'18 conformal (1);
Tirmazi'20 Borg trace; Weng'22 PAI trace (NSDI); Norris'25; SB6 statute (1);
Google DR news (1); E2E-CDRO (the prior paper, if citable as preprint).
Data-access footnotes (gridstatus, IEM ASOS, Open-Meteo) are footnotes, not references.

## Process rule (guide §10)

No citation enters the LaTeX bib without a DOI/arXiv ID captured here first. This file is
the single source of truth for Phase 7 references.
