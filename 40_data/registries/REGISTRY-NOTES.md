# Blind practitioner registry: notes

Output file: `registry_real.json`. The builder is `build_registry.py`, which rebuilds the registry and checks that every snippet and evidence quote appears verbatim in the text. These notes cover method, counts and uncertain items.

## Method

- **Inputs used:** only `text/*.txt`, `text/*.meta.json` and `documents.json` in this folder. I did not open the gold graph, the benchmark, the code or anything else in the repository, and I did not use the web.
- **How I read:** I read the operative regulations and amendments in full: MERC GIRREGS 2019 and its 2023 and 2024 amendments, RERC 2015, 2021, 2023 and 2024, the ROC Rules 2020 and 2024, the MNRE PMSG order and guidelines, and the ALMM and DCR OMs. I searched the large files (the MSEDCL tariff order MH-C3-004 at 2.6 MB, and the ALMM list) for rooftop terms. I scanned the DISCOM circulars.
- **Node ids:** each id is `<doc_id>#cl-<clause as printed>`.
  - For an amending instrument, the clause ref is the regulation number it substitutes or inserts (for example `MH-C3-003#cl-2.1(j)`), not the amending paragraph number.
  - Annexure clauses are written `Annexure-1.c`.
  - Documents with no clause numbers get descriptive refs: `p3` (third paragraph), `GCR-2` (FAQ number), `Amendment-i` (row Sl. No. of an amendment table), and `encl.a-b` (enclosed OM).
- **Snippets:** each snippet is an exact copy of the extracted text, newlines included and capped at 600 characters. OCR artefacts are left in place, such as missing spaces in MNRE OMs and garbled characters in MSEDCL CC/331.
- **Where a file has two languages:**
  - MH-C3-002 and RJ-C3-003: I took snippets from the official English gazette pages, not the machine-translated pages, because the two disagree (see uncertain items).
  - MH-C3-003, IN-C3-001 and RJ-C3-005: the English half.
- **Effective dates:** the `effective_date` from `documents.json`, with these exceptions:
  - The 07.07.2025 PMSG amendment OM bundled in IN-C1-001 uses 2025-07-07.
  - The 09.02.2024 ALMM OM enclosed in IN-C2-003 uses 2024-02-09.
  - IN-C1-003 uses 2024-02-13, the launch date its own text gives.
  - MH-C6-001 is null, because the document is undated.
- **Edge confidence:**
  - `high`: the newer text states the substitution, insertion or amendment of the named clause.
  - `medium`: explicit applicability or subsumption language, but no clause-level repeal.
  - `low`: implicit. Every low edge carries a `reason`.
  - Edge `effective_date` is the effective date of the newer node.

## Counts

| | IN | MH | RJ | Total |
|---|---|---|---|---|
| Nodes | 41 | 48 | 36 | 125 |
| Edges (by from-node) | 15 | 16 | 16 | 47 |

- **Two cross-jurisdiction edges:** MH-C5-005 3.2 and MH-C6-001 GCR-2 both point to IN-C1-001 5(e). Both are low confidence.
- **Edge types:** 26 supersedes, 12 partially_supersedes, 9 amends.
- **Edge confidence:** 31 high, 8 medium, 8 low.
- **Node confidence:** 84 high, 35 medium (OCR, translated or summary sources), 6 low (garbled OCR).
- **Document-level relations (3):**
  - MERC Net Metering Regs 2015 (not in the corpus) repealed by MH-C3-001 Reg 20. High confidence.
  - RJ-C3-001 to RJ-C3-002: a prospective replacement with no repeal clause. The two coexist (Reg 1.4 and 3.4). Medium confidence.
  - The Phase-II programme (IN-C1-002) subsumed into PMSG (IN-C1-003 para 1). Medium confidence; this is not a repeal.

## Main chains found

- **MH:**
  - 2019 to 2023: 2.1(j), 8.3, 8.11, 9.5, 11.5 proviso, 12/12.1, Annexure-1(h).
  - 2023 to 2024: 2.1(j) virtual net metering provisos, and 8.11, which the 2024 amendment substitutes as a regulation "of the Amendment Regulations".
  - 2019 to 2024: 9.7, and Annexure-1(c) (feasibility in 15 days with presumed feasibility, deemed approval up to 10 kW).
- **RJ:**
  - 2015 to 2021, partial: DT limit 30% to 50%, capacity 80% to 100% of sanctioned load, settlement, check meter.
  - 2021 to 2023: 6.1 (DT limit 80%), 10.14.3, 12.5.2 (+40%), 12.5.6, 12.6.1(a)/(b)/(d), 15.2.
  - 2021 to 2024: 8.8 (feasibility 20 to 15 days, deemed approval up to 10 kW) and 8.12 (commissioning 30 to 15 days). The 12.6.1(a) third proviso was added in 2024.
  - Suo-motu order RJ-C3-004: net metering up to 1 MW or sanctioned load/contract demand.
- **IN:**
  - ROC Rules 2020 to 2024: 11(7) to 11(7)/(7A), 11(8), 11(9).
  - Phase-II CFA (40%/20%) to PMSG CFA (60%/40% up to 3 kW).
  - IN-C1-005 clarifies PMSG 5(f).
  - The 2025 amendment OM changes 5(i), Annexure-1 (Phase-II claim deadline moved from October 2024 to 31.12.2025) and 6(f).
  - ALMM: efficiency thresholds amended by IN-C2-007, abeyance OMs, and ALMM in force from 1.4.2024.

## Uncertain items and judgement calls

1. **RJ 2015 to 2021 is not a repeal.** RJ-C3-002 Reg 1.4 says the 2021 Regulations "remain in force along with" the 2015 Regulations, and grandfathers systems commissioned up to 30.06.2021. I coded the clause edges as partially_supersedes at medium confidence. The check-meter edge is low. A gold registry might treat this relation as a full supersession, or as no edge at all.
2. **RJ-C3-003 translation conflicts with the English text.** The machine-translated Hindi pages list a substitution of 12.5.3 ("Net Billing facility up to the contracted demand") and omit the substitution of 12.6.1(a)/(d). The English gazette pages (pp. 5-7) show the reverse. I followed the English and did not create a 12.5.3 edge. The translated pages of MH-C3-002 likewise invent a different 11.10 text.
3. **The earlier RJ suo-motu order is missing.** RJ-C3-004 cites an order of 07.09.2021 that limited net metering to 500 kW. That order is not in the corpus, so the edge is RJ-C3-002 3.2 to RJ-C3-004 12, typed "amends" at medium confidence. In substance it is a direction, not an amendment of the regulation.
4. **The ROC 2021 amendment is missing.** ROC Rules 11(4), which provides net metering up to 10 kW and gross metering above, was changed by the 2021 Amendment Rules. Those rules appear only as a quotation inside RJ-C3-004 and are not in the corpus. I left IN-C3-002 11(4) without a successor edge, and it is probably stale. The 2023 ROC amendment (G.S.R. 437(E)) is cited in IN-C3-001 but is also absent.
5. **MERC tariff order MH-C3-004 7.13.79.** It displaces the off-peak treatment in Reg 11.4(d) for LT-residential RTS consumers. Because it is an order and not a regulation amendment, I coded it as a low-confidence partial supersession. Para 7.1.34, on grid support charges, applies the 11.5 proviso and supersedes nothing.
6. **ALMM suspensions.**
   - I coded "held in abeyance" (IN-C2-003) as supersedes at medium confidence; it is a suspension.
   - The FY 2023-24 abeyance (IN-C2-004 1.6) is ended by IN-C2-002, which lapses by its own terms on 1.4.2024.
   - IN-C2-002 never mentions the February OMs, so the edge from IN-C2-003 1 to IN-C2-002 1 is low.
   - IN-C2-006 para 8 says net-metering projects must use ALMM modules unless exempt. That conflicts with the suspended 09.02.2024 OM, which said ALMM does not apply to self-owned capacity. I recorded no edge.
   - The intermediate ALMM OMs of 22.03.2024, 07.08.2024 and 10.03.2023 are cited but not in the corpus.
7. **DISCOM circulars that restate superseded regulations.** MSEDCL CC/322 (MH-C5-001) restates 2019 Reg 2.1(j), with its under-1 MW limit. MSEDCL's 2024 letter MH-C5-006 relaxes the arrears bar. CC/331 (MH-C5-005) and the MEDA FAQ (MH-C6-001) carry the Phase-II 40%/20% CFA. All four edges are low and implicit. MSEDCL circulars MH-C5-003 and MH-C5-004 implement the repealed MERC 2015 Regulations (through CC/258), but nothing in the corpus withdraws them, so I recorded no edge.
8. **JVVNL orders amend a missing base order.** RJ-C5-002 (JPR5-1153) and RJ-C5-003 amend JVVNL order JPR5-1073 of 21.09.2021, which is not in the corpus. RJ-C3-006 revises the tariff in JPR5-1158, also absent. I recorded RJ-C5-002 clause 4.1 (DT limit 80%) as a node with no edge.
9. **OCR quality.**
   - In the 2025 amendment OM inside IN-C1-001, two-column OCR interleaves the existing and amended text, so those snippets are low confidence.
   - CC/331 clauses 3.1 and 3.2 are garbled.
   - The threshold table in IN-C2-001 is illegible.
   - Some snippets are cut at 600 characters; most of these still include the operative figure.
10. **Left out:** clauses that don't bear on the requested topics. These include agreement formats, RPO, REC, virtual and group net-metering settlement mechanics, GEOA clarifications in MH-C3-005, the CEA 2019 connectivity amendment (IN-C3-003), vendor-registration orders (RJ-C5-005), meter-testing SOPs (MH-C5-010, MH-C5-012, RJ-C5-004), and the other PMSG components (IN-C1-004, IN-C1-006, IN-C1-007, IN-C1-008).
