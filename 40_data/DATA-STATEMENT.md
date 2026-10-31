# Data statement: SuryaBench (Paper A, information ladder)

Written 2026-10-07 (T7) for the case study; the paper reports it descriptively. Format: Bender and Friedman, "Data Statements for Natural Language Processing". Counts and
component details are in `40_data/DATASHEET.md`, with the file behind each number. Identities are coded for anonymous
review.

## Licences, per component (D42, "Both"; correspondence of 2026-10-04, section 8.3 item 2)

| Component | Licence or form of release |
|---|---|
| Code (`30_code/`) | Apache-2.0 (`LICENSE`) |
| Cases and labels (`40_data/benchmark/`, adjudicated annotation sheets) | CC BY 4.0 |
| Supersession graph and registry (`40_data/corpus_r3/graph/`, `40_data/registries/`) | CC BY 4.0 (labels written by the authors and the AI agent) |
| Verbatim regulatory text inside those files (clause snippets, evidence quotes) | Short quotes with their source URL only, until redistribution is confirmed |
| Government documents (`40_data/corpus_r3/raw/`) and their extracted text (`text/`) | Not redistributed. Released as URL plus sha256 (`corpus_r3/MANIFEST.json`), unless redistribution is clearly allowed |
| Run outputs (`50_analysis/results/`) | CC BY 4.0 |

Notes:
- Redistribution rights for the government documents are not established (`80_review/PUBLICATION-READINESS-CHECKLIST.md`,
  C9 and R5). No document in the manifest records a licence. A document moves to the redistributed set only if its
  issuer clearly allows it; that change is a dated `DECISIONS.md` entry.
- Users rebuild the corpus by fetching each URL and checking the sha256. Four URLs no longer serve the saved file
  (`corpus_r3/SOURCE_CHECK.csv`: two 404, one 429, one without a URL).
- The run-outputs row is a proposal: D42 names code, cases and labels, and documents only. To be confirmed by the
  authors.

## A. Curation rationale

The corpus holds rooftop-solar rules in force in India, together with the instruments that amended or replaced them.
It was built to test whether an AI reviewer catches an answer that cites a replaced clause. Documents were chosen
where one instrument changes another: regulations and their amendments, tariff orders, scheme guidelines and DISCOM
procedures. Coverage: the central layer and seven states (DL, GJ, KA, MH, RJ, TN, UP). Test cases were chosen per
distinct replaced clause (D38).

## B. Language variety

- Written English as used in Indian official documents (en-IN), formal legal and administrative register.
- Per `corpus_r3/SOURCE_CHECK.csv` (`language`): 105 documents English only, 6 English plus Hindi (hi-IN, Devanagari):
  IN-C3-001, IN-C3-003, IN-C3-004, MH-C3-003, RJ-C3-005, RJ-C5-005.
- Hindi passages were machine-translated into English by a local model for retrieval
  (`corpus_r3/translation_cache.json`, 29 entries). The translations are poor in places. No label depends on them
  (D41).
- Cases, answers, prompts and labels are in English.

## C. Speaker (author) demographic

The texts are written by Indian public bodies, not individuals: the Ministry of New and Renewable Energy, the Ministry
of Power, the Central Electricity Authority, state electricity regulatory commissions (DERC, GERC, KERC, MERC, RERC,
UPERC), distribution companies (BESCOM, MSEDCL, JVVNL, JdVVNL, TANGEDCO) and one state nodal agency (MEDA). Issuers per
document are in `corpus_r3/MANIFEST.json` (`issuer`). Individual drafters are not identified.

The synthetic cases and fixed answers were written by code that the AI agent wrote (see section H).

## D. Annotator demographic

| Code | Role | Description |
|---|---|---|
| A1 | Annotator | An author. Not a legal professional. Blind to the v3 labels; had reviewed parts of an earlier version of the graph. Also does the human scorer check (H-16). |
| A2 | Annotator | An author. Not a legal professional. Blind to the v3 labels. |
| ADJ | Adjudicator | The third author, who led the pipeline that produced the first-pass labels. Adjudicates from the two sheets and the source documents, without opening the answer keys. |

- A1 and A2 work alone and do not discuss items until both have submitted (`20_method/ANNOTATION-PACKET.md` v3).
- Age, gender, first language, background, hours and payment are recorded in `20_method/annotation/ANNOTATORS.md`
  when the annotators fill it. As of 2026-10-07 those fields are blank.
- Disclosure (D45, `20_method/PREREGISTRATION_v3.md` section 3): "Two authors, blind to the v3 labels (one had
  reviewed parts of an earlier version of the graph), checked every link, case and correct answer, each item by at
  least one of them; a seeded shared subset (15 links, 20 cases) was labelled by both, and raw agreement, kappa and
  PABAK are reported on it. Disagreements were adjudicated by a third author, who led the pipeline that produced the
  first-pass labels, working from the annotators' sheets and the source documents. The same author checked the source
  documents and the open data items. The annotators are not legal professionals."

## E. Speech situation

Written, edited, published instruments: regulations and amendments in official gazettes, commission orders, ministry
guidelines and office memoranda, and DISCOM circulars and procedures. Printed dates run from 2013 to 2026 (100 of 111
documents have a parseable date; `MANIFEST.json`, `doc_date`). The intended audience is regulated utilities,
installers and consumers. Retrieval took place from 21 September to 1 October 2026.

## F. Text characteristics

Legal and procedural text with numbered clauses, provisos, tables and schedules. Amendments often substitute words or
clauses by reference ("for the words ... the following shall be substituted"). Many documents are scans: 43 of 111
needed OCR (`MANIFEST.json`, `text_layer`). Cases are structured records (state, DISCOM, consumer category, loads,
capacity, metering mode, dates), not prose.

## G. Recording quality

PDFs as published by the issuer or a host. Native text layers for 68 documents, OCR for 43. TN-C5-004's text layer is
unusable (legacy font; D41). Every saved file hashes to the manifest (`SOURCE_CHECK.csv`, `sha256_ok`).

## H. Other: AI involvement

- **Collection.** An AI agent (Claude Opus, in Claude Code) found, saved and hashed the documents and did the first
  authentication pass (59 of 65 new documents agent-verified; 6 left to a human; D41).
- **Labels.** The same agent wrote the gold supersession graph, the per-clause rule functions, the cases and their
  labels.
- **Registry.** Built offline by Claude Opus agents from the corpus text only, blind to the gold graph
  (`registries/REGISTRY-NOTES-v2-r3.md`).
- **Translation.** A local open model translated the Hindi passages.
- **Code and drafts.** The agent wrote the code and the first drafts of the documents, including this one. The
  authors rewrite and approve.
- **Human checks.** Two authors check the test labels, links, quotes, controls and sources blind; a third adjudicates
  (section D). A human checks the automatic scorer on 50 dev replies at a 95% threshold (H-16). Before sealing, any
  test case whose adjudicated label differs from the AI label is dropped, and any rejected link is removed (D44).
- **Consequence for evaluation.** Claude models are not scored on this benchmark (`20_method/PREREGISTRATION_v3.md`,
  section 4).

## I. Provenance appendix

Per-document provenance: `corpus_r3/provenance/r3/<doc_id>.provenance.json` and the `retrieved_url`,
`retrieved_at` and `sha256` fields of `corpus_r3/MANIFEST.json`. The 46 documents carried over from corpus r2 have
their records in `40_data/corpus/`. Decisions about the data are dated entries in
`00_tracking/decisions/DECISIONS.md` (D37–D43 for this paper).
