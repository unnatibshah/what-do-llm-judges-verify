# Datasheet: SuryaBench (Paper A, information ladder)

DRAFT, 2026-10-07 (T7). Written by the implementation agent from the files cited in each answer. Format: Gebru et al.,
"Datasheets for Datasets". Every count is taken from the file named beside it. Counts for the test candidate may change
after annotation and sealing (T8); the sealed counts replace them. Licences, language and annotators are in
`40_data/DATA-STATEMENT.md`.

## Components

| Component | File | State |
|---|---|---|
| Corpus r3 | `40_data/corpus_r3/MANIFEST.json` (`SuryaBench-Corpus-2026.10-r3`) | 111 documents, hashed (`MANIFEST.sha256`) |
| Gold supersession graph | `40_data/corpus_r3/graph/supersession.json` | 145 nodes, 51 edges; first pass by AI, under human check |
| Applicability graph | `40_data/corpus_r3/graph/applicability.json` | 48 entries |
| Non-gold registry | `40_data/registries/registry_real_v2_r3.json` | 683 nodes, 186 edges, 17 document supersessions; hashed (`REGISTRY.sha256`) |
| Dev split | `40_data/benchmark/dev_cases_v2.json` | 60 cases; hashed (`dev_cases_v2.sha256`) |
| Test candidate v3 | `40_data/benchmark/test_cases_v3_CANDIDATE.json` | 60 cases on 15 replaced clauses; **not sealed** |

Older files in `40_data/` (`corpus/` r2, `benchmark_cases_160.json`, `dev_cases_60.json`, `test_cases_100.json`,
`test_cases_v2_CANDIDATE.json`, `registry_real_v1.json`) belong to retired designs. Paper A does not use them, except
that corpus r3 contains the 46 r2 documents.

## Motivation

**Why was the dataset created?** To ask what an AI reviewer must be told before it catches a rule that a later
instrument has replaced (D37). Fixed answers are reviewed at rising levels of information, from the old clause alone
(R0) to a deterministic registry lookup (R5). Indian rooftop-solar rules were chosen because they are amended often,
by many issuers, and the amendments are not linked in one place.

**Who created it, and for whom?** The three authors of Paper A. Names are withheld here for anonymous review. An AI
agent (Claude Opus, in Claude Code) did the first pass of collection, labelling and code; see "Labelling" below.

**Funding.** None. The study runs on a zero budget (D42 item 9).

## Composition

**What are the instances?** Four kinds:
1. Government documents (PDFs and their extracted text).
2. Clause nodes and supersession edges between them (the graph and the registry).
3. Synthetic rooftop-solar applications ("cases"), each with an expected decision and the clauses that decide it.
4. Verifier items built from cases at run time: a FAULT answer that cites a replaced clause, and a matched CONTROL.
   Items are not stored as a dataset file; the probe code builds them (`30_code/src/suryabench/arms/verifier_probe.py`).

**Corpus r3** (`MANIFEST.json`):
- 111 documents, 2,585 pages in total.
- By jurisdiction (doc-id prefix): IN (central) 30, DL 16, MH 16, KA 15, GJ 12, RJ 11, UP 6, TN 5.
- By class: C1 central scheme 12, C2 central technical 13, C3 state regulatory 49, C4 state orders 6,
  C5 DISCOM procedural 30, C6 nodal agency 1. Class definitions: `20_method/SURYA-BENCH-PROTOCOL.md`, "Source classes".
- Status field: presumed_current 77, presumed_superseded 13, unknown 10, context 9, draft_not_in_force 2.
- Text layer: native 68, OCR 43.
- Printed document dates (100 of 111 parseable) run from 2013-09-30 to 2026-08-25.
- Effective-date confidence: high 45, medium 40, low 26.
- 46 documents come from the earlier corpus r2 (IN, MH, RJ). 65 were added in r3 (DL, GJ, KA, TN, UP and some IN).

**Gold supersession graph** (`graph/supersession.json`):
- 145 clause nodes and 51 edges: 49 `superseded_by`, 1 `amended_by`, 1 `consolidated_into`.
- Evidence type: 18 explicit, 33 implicit.
- 5 whole documents are marked superseded (`superseded_documents`).
- Known issues from the first human-facing review (D41, `20_method/annotation/OPEN_ITEMS_RESOLVED.md`): of the 33
  implicit edges, 22 are in fact explicit substitutions and 11 are overrides. One edge points the wrong way, one has
  the wrong successor, two cover less than claimed, and four restate the same value. None of these is among the 15
  test clauses. Nothing is applied before the annotators confirm (T8).

**Non-gold registry** (`registries/registry_real_v2_r3.json`; method in `registries/REGISTRY-NOTES-v2-r3.md`):
- 683 nodes and 186 edges: 90 `supersedes`, 38 `amends`, 58 `partially_supersedes`.
- Edge confidence: 109 high, 40 medium, 37 low. Every low edge is an implicit supersession with a note.
- 17 document supersessions.
- `generated_by`: "Claude Opus (Claude Code agent), blind to gold graph, from corpus text r3".
- It is the registry that the R3, R4 and R5 rungs consult. Damaged copies (25% or 50% of links dropped, 10% spurious
  links added, seeds 0–4) are made at run time by code, not stored.

**Dev split** (`benchmark/dev_cases_v2.json`):
- 60 cases: 54 ANSWER, 6 ABSTAIN.
- 3 rule groups (`cluster_id`): `IN-C1-001#cl-4.1`, `MH-C3-001#cl-6.2`, `RJ-C3-003#cl-2`, 20 cases each.
- Probed failure classes: CLEAN 14, F3 8, F5 8, F6 8, MULTI 6, F4 6, F9 6, F2 4.
- Only 2 distinct replaced clauses (`IN-C1-002#cl-2`, `RJ-C3-002#cl-6.1`; D37). Dev numbers are pilot evidence only.

**Test candidate v3** (`benchmark/test_cases_v3_CANDIDATE.json`; summary in
`50_analysis/results/ladder_design/candidate_v3_manifest.json`):
- 60 cases, all ANSWER, on 15 distinct replaced clauses, 4 cases per clause.
- Clauses by state: DL 4, GJ 4, IN 2, KA 2, TN 1, UP 2.
- Supersession type: EXPLICIT 11, IMPLICIT 2, NONE 2.
- Probed failure classes: CLEAN 30, F3 13, F2 6, F4 3, MULTI 3, F6 3, F5 2.
- Verifier items: S-both 60 faults / 60 controls (15 clauses); S-swap 56 / 9 (14 clauses); J 32 / 32 (7 clauses);
  A 0; condition C 60 clean correct answers.
- sha256 `028bc75b47e642b43a3ba91c6c8bdc3c297681d9b49447fe926e38f17abc4519` (`test_cases_v3_CANDIDATE.sha256`).
- The three `DL-C3-015` successor clauses come from one amending instrument, so those test clauses are not independent
  (`20_method/PREREGISTRATION_v3.md`, section 2).
- No dev replaced clause is in the test candidate.

**Is it a sample?** Yes. The corpus is a purposive sample of rooftop-solar instruments from the central government and
seven states, not every such document. The test clauses were chosen per distinct replaced clause from those the graph
links (D38).

**Is anything missing?** Some predecessor texts are not in the corpus, so their edges were skipped
(`corpus_r3/BUILD_REPORT.json`, `skipped_edges`, 5 entries). One document (IN-C2-007) has no source URL.

**Personal or sensitive data?** No. The documents are public government instruments. The cases are synthetic: their
facts are fields such as state, DISCOM, consumer category, loads and dates. They name no person.

**Errors and noise.**
- OCR text (43 documents) has errors. One text layer is unusable: TN-C5-004 is legacy-font garbage (D41).
- Machine translations of Hindi passages (`corpus_r3/translation_cache.json`, 29 entries) are of poor quality. No label
  depends on them (D41).
- Four manifest corrections are known and wait for T8, because the manifest is hashed (D41).

## Collection process

**How was the corpus collected?** The AI agent found documents on issuer websites and by search, saved each file, and
recorded its URL, retrieval time and sha256 (`MANIFEST.json`, `provenance/`). Retrieval route: site navigation 82,
web search 13, site search 11, orphan 5. Retrieval times run from 2026-09-21 to 2026-10-01. The procedure is
`20_method/COLLECTION-PROCEDURE.md`; the build script is `30_code/scripts/build_corpus_r3.py`.

**Source checks** (`corpus_r3/SOURCE_CHECK.csv`, made by `30_code/scripts/check_corpus_sources.py`; D41):
- All 111 saved files hash to the manifest.
- URL status: 107 return 200, 2 return 404, 1 returns 429, 1 has no URL.
- The same bytes are still at the source for 107 documents; not for 4 (the four without a 200).

**Authentication** (`corpus_r3/SOURCE_VERIFICATION.csv` and `SOURCE_VERIFICATION_FOLLOWUP.csv`; D41):
- The 65 documents added in r3 were checked for an official domain, the same bytes at the source, and the recorded
  title, number and date in the text.
- 59 are AGENT_VERIFIED. 6 need a human: KA-C3-001, KA-C3-002, KA-C3-003, KA-C3-004, KA-C4-001, TN-C5-005
  (USER-TASKS U1). None of the six is used by a test case.
- IN-C1-010 is verified against a Government of Goa copy, not MNRE's own copy.
- The 46 r2 documents carry no `verification_status` in the manifest. Three of them were saved from non-issuer hosts:
  RJ-C3-001 and RJ-C3-002 (cbip.org), RJ-C3-003 (uncomplycate.com). IN-C3-002 was saved from web.archive.org.
- People check the 20 documents behind the test items in annotation (`20_method/annotation/sources_to_check.csv`,
  H-02).

**Who collected it?** The AI agent, supervised by the lead author. No crowd workers were used.

**Ethical review.** None was sought. The study uses public documents and synthetic cases, and has no human subjects
other than the authors.

## Preprocessing, cleaning, labelling

- **Text extraction.** Native text layers where present, OCR otherwise (`text/<doc_id>.txt`, `text/<doc_id>.meta.json`;
  code in `30_code/src/suryabench/corpus/`). The raw PDFs are kept in `corpus_r3/raw/`.
- **Translation.** Hindi passages were machine-translated by a local model (`translator.py` default `qwen2.5:7b`; the
  cache does not record the model). Languages per document are in `SOURCE_CHECK.csv` (`language`).
- **Gold graph.** Written by the AI agent from the corpus text. Each node snippet and each explicit evidence quote is
  checked to occur verbatim in the text (`30_code/scripts/build_supersession_graph.py`).
- **Registry.** Built offline by Claude Opus agents from the corpus text alone, without the gold graph or the web
  (`registries/REGISTRY-NOTES-v2-r3.md`; inputs hashed in `registries/blind_inputs/`). The build fails if a snippet or
  quote is not verbatim in its document.
- **Cases.** Generated backward from per-clause rule functions written by the AI agent. Each case records the clauses
  that decide it and its provenance (`ground_truth_provenance`, e.g. `rule_function:<clause ids>`). The test
  candidate is built by `30_code/scripts/build_test_candidate_v3.py` (D38).
- **Human checks before sealing** (D42, D45, `20_method/ANNOTATION-PACKET.md` v3): two annotators label, blind and
  independently, the 60 test cases, 40 controls and 52 links, each item by at least one of them; a seeded shared
  subset (15 links, 20 cases) by both. One annotator checks the 18 R3 quotes; the third author checks the 20 source
  documents and the open items that touch test items, and adjudicates without the answer keys. Raw agreement, Cohen's
  kappa and PABAK are reported on the shared subset (`30_code/scripts/annotation_agreement.py`). Status on
  2026-10-14: not yet done (USER-TASKS U2).
- **Sealing** (T8, D44, `30_code/scripts/seal_test_v3.py`). A case whose adjudicated decision or deciding clauses
  differ from the AI label is dropped, never relabelled. A rejected registry link is removed, giving
  `registry_real_v3.json`. A replaced clause is dropped when every link tied to it is rejected. The sealed file is
  `40_data/benchmark/test_cases_v3.json` with its `.sha256`; a test run refuses any other bytes.
- **Raw data kept?** Yes: PDFs, extracted text, per-document provenance and every saved run.

## Uses

**Intended use.** Measuring whether AI reviewers catch citations of replaced rules, and what information they need to
do so, under `20_method/PREREGISTRATION_v3.md`.

**Other possible uses.** Retrieval and amendment-tracking studies on Indian solar regulation; registry-building
methods.

**Uses to avoid.**
- Legal or regulatory advice. The labels are research labels, the annotators are not legal professionals, and the
  rules change after the snapshot.
- Claims about all Indian states or all regulation. The corpus covers seven states and the central layer.
- Tuning on the test split. Engineering uses dev only. The probe refuses to read a test split without `--allow-test`.
- Training or scoring Claude models on it. Claude helped build it, so Claude is excluded from scoring
  (`PREREGISTRATION_v3.md`, section 4).

**Known biases.** Labels, cases and registry were all first written by the same AI family. Cases use one answer
template. Most test clauses are EXPLICIT supersessions (11 of 15).

## Distribution

- **Where.** The repository; an anonymised mirror for review. A Zenodo or OSF deposit is planned with the release
  (T12).
- **When.** After the test run and submission. The test split is released after the sealed run.
- **Licences.** See `40_data/DATA-STATEMENT.md`. In short: code Apache-2.0; cases, labels, graph and registry
  CC BY 4.0; government documents as URL plus sha256 unless redistribution is clearly allowed.

## Maintenance

- **Who maintains it.** The lead author (corresponding author). Contact details are withheld for anonymous review.
- **Errata.** Every change is a dated entry in `00_tracking/decisions/DECISIONS.md`. Hashed files are never edited in
  place; a correction is a new versioned file with a new hash.
- **Updates.** Regulations keep changing. A new snapshot is a new corpus version (`corpus_version`), not an edit.
- **Contributions.** By pull request; data changes need a source document and a `DECISIONS.md` entry.
