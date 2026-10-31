# Blind registry r3: notes

## Method

- **Inputs used:** only `text/*.txt`, `text/*.meta.json`, `documents.json` and `registry_real_r2_prior.json`, all in this directory. Nothing under the repository, no gold registry, no web.
- **How the work was split:** the prior r2 registry (IN/MH/RJ) was split into `fragments/IN.json` and `fragments/MHRJ.json`. Six parallel agents each followed `AGENT_BRIEF.txt` and wrote one fragment: DL, GJ, KA, TNUP, IN, MHRJ.
  - The IN and MHRJ agents reviewed and corrected the prior, then extended it to the documents it did not cover.
  - The other four built their jurisdictions from scratch.
- **Snippets and quotes:** every snippet and evidence quote was sliced from the source text in python, not retyped.
- **What `build_registry.py` does:** it merges `fragments/*.json` and fails if any of these checks fail:
  - every snippet is an exact substring of its document's text and is at most 600 characters;
  - every `node_id` equals `doc_id#cl-clause_ref`;
  - each node's jurisdiction matches `documents.json`;
  - every edge endpoint exists as a node;
  - edge types are only supersedes, amends or partially_supersedes;
  - every `evidence_quote` is verbatim in the newer document (the `to_node`'s document);
  - no edge or document supersession points to a draft;
  - confidence values are valid.

  It then writes `registry_real.json`, reads it back and checks it again. `python3 build_registry.py --check <fragment>` checks a single fragment.
- **Edge types:**
  - `supersedes` means the whole clause was substituted, deleted or omitted.
  - `amends` means words or provisos were inserted or partly changed.
  - `partially_supersedes` means part of the older clause is overridden without a textual amendment, usually by a different instrument.
  - Implicit supersession is always given confidence `low` and a `note` with the reason. Every low edge has one.
- **Drafts:** GJ-C3-006 (draft GERC Fifth Amendment) and GJ-C3-008 (draft GIDRES Regulations 2026) appear as nodes tagged DRAFT and have no incoming edges. The draft GIDRES Reg 1.4 proposes repealing the 2016 regulations, which is recorded on its node only. The notified Fifth Amendment, GJ-C3-007, does carry edges.
- **Statements of Reasons, FAQs, portal pages and orders:** SoRs (GJ-C4-\*, UP-C4-001) and FAQs/portal pages are nodes only. MERC's clarification order (MH-C3-005) is also nodes only, because it clarifies rather than amends. DISCOM circulars are never treated as amending a regulation.

## Counts (registry_real.json)

Totals: **683 nodes, 186 edges** (90 supersedes, 38 amends, 58 partially_supersedes; 109 high, 40 medium, 37 low confidence), and **17 document supersessions**. All 111 documents have at least one node. Edges are counted under the jurisdiction of the newer (`to`) node.

| Jur | Nodes (h/m/l) | Edges | supersedes / amends / partial | Edge conf h/m/l | Cross-jur | Doc supersessions |
|---|---|---|---|---|---|---|
| DL | 89 (86/3/0) | 33 | 17 / 8 / 8 | 23/7/3 | 0 | 1 |
| GJ | 93 (85/8/0) | 33 | 19 / 12 / 2 | 25/6/2 | 0 | 0 |
| IN | 154 (102/42/10) | 44 | 14 / 10 / 20 | 21/15/8 | 3 | 5 |
| KA | 118 (85/25/8) | 17 | 5 / 0 / 12 | 0/5/12 | 0 | 5 |
| MH | 96 (54/34/8) | 19 | 11 / 3 / 5 | 14/0/5 | 0 | 1 |
| RJ | 57 (35/13/9) | 18 | 9 / 2 / 7 | 11/4/3 | 0 | 3 |
| TN | 31 (24/6/1) | 3 | 0 / 0 / 3 | 0/1/2 | 0 | 1 |
| UP | 45 (33/11/1) | 19 | 15 / 3 / 1 | 15/2/2 | 0 | 1 |

The three cross-jurisdiction edges run from MH clauses to IN PM Surya Ghar clauses. Each is a Phase-II CFA clause overridden by the PMSG scheme.

## Corrections to the r2 prior

- **IN-C1-001 is not the consolidated PMSG CFA guidelines.** It is the amendment memo of 07.07.2025, with the original 07.06.2024 guidelines attached; the original matches IN-C1-011.
  - All the original-clause nodes moved to IN-C1-011.
  - IN-C1-001 now holds only the amended clauses 5(i), 6(f) and Annexure-1 (formerly "Amendment-i/ii/iii") and its own para 2, dated 2025-07-07.
  - Node ids for IN-C1-001 therefore differ from r2.
- **Edge types changed:**
  - Rights of Consumers 11(7) → 11(7A) is now `amends`, because 7A is an insertion.
  - The clarification memos IN-C1-005 and IN-C1-012 are now `partially_supersedes`, because they change no text.
  - MH-C5-001 2.1 → MH-C3-003 2.1(j) is now `partially_supersedes`, because a circular is not textually substituted.
  - RJ-C3-002 3.2 → RJ-C3-004 cl-12 is now `partially_supersedes`, because a Reg 19 direction is not a textual amendment.
- **Effective date:** MH-C6-001 GCR-2 had no effective date; it is now "UNKNOWN".

## Uncertainties

- **OCR and layout:**
  - Two-column "existing / amended" tables are interleaved in UP-C3-003, UP-C3-005, IN-C2-008 and IN-C1-001. Those snippets are medium confidence.
  - Pages 1-6 of IN-C3-005 (CEA 2013) are unreadable.
  - The text is poor in KA-C3-002 (the deemed-approval capacity figure is lost), KA-C5-001/008/009/010, MH-C5-005/011/012, RJ-C5-001/002/003/005 and the GJ draft Fifth Amendment.
  - TN-C5-004 is untranslated Tamil with garbled glyphs, and its meta.json labels the language "mr". It has one low node.
- **Invented clause refs:** where nothing is printed, labels were made up. Examples: SoR "Issue I", KA SOP headings ("III Timelines >150kW", "VNM viii.8"), RJ-C3-001 summary-table row numbers, MH `para-1`/`GCR-1`. Matching these to a gold registry by clause ref will be fragile.
- **Karnataka:** most edges are low or medium. The 2026 DSPV Regulations repeal the 2016 SRTPV Regulations (Reg 24.1, which is not in the corpus). The edges from 2016-rule clauses as revised by the 2023 tariff order onto 2026 Regs 8.1-8.4 rest on that general repeal, not on clause-specific words.
- **Dates:**
  - The documents.json date was sometimes overridden by a date printed in the text: Gazette dates for KA-C3-003 (2026-08-24), IN-C3-005 (2013-10-07) and IN-C3-004 (2021-06-29).
  - KA-C5-002 to KA-C5-005 and several DL guideline nodes are UNKNOWN.
- **Coexistence, not repeal:** RJ 2015 → 2021 (prospective, with a saving to 30.06.2021). The Phase-II → PMSG links are subsumption, not repeal. TNERC Order 3/2019 → Order 8/2021 is low confidence with no express words.
- **Possible misnumbering:** DL-C3-015 prints the substituted GNM/VNM 3(2) as "(3)". DL-C3-011's new 11(4)(i) is missing sub-clause (c).
- **Instruments outside the corpus:** several DISCOM circulars amend documents that are not in the corpus (CC/258, JPR5-1073, JPD6-540, the KA standard PPA). They are nodes only and have no edges.
