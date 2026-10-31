# Preregistration v3, amendment 2 (DRAFT): what annotation keeps, and the dated changes before filing (D49)

**Status: DRAFT, 2026-10-29. Not signed, not filed.** Drafted by the AI agent at the lead author's request. It takes
effect only when all three authors sign section 7, **before the test set is sealed (T8) and before the OSF filing**.
`PREREGISTRATION_v3.md` and amendment 1 are unchanged; where this amendment says nothing, they hold as written. All
three files are filed on OSF together.

## 1. Why, and what was known when this was written

This amendment was written **after the annotation was adjudicated and before any model saw a test item**. The
authors knew the annotation outcome (below) and nothing about model behaviour on the test split. That order is
disclosed in the paper.

Applied as written, v3's annotation rules (section 3, "Changes from annotation") would seal 6 of the 60 candidate
cases (4 distinct replaced clauses), and the controls gate (95% CORRECT) fails at 23 of 40 (57.5%). The adjudicated
labels show why:

- **The AI-built answer key reaches the wrong outcome on 18 of 60 cases** (13 decisions, 5 blocking stages). In the
  cases read, the generator decided each case from a single rule function (`ground_truth_provenance.basis`), and the
  human readers found a second rule that also applies, often in a newer document. These cases are wrong at the base
  and are dropped, as v3 says.
- **Deciding clauses differ on 36 of the remaining 42 cases.** Here no side is clearly right. On the shared cases
  the two annotators gave the same deciding clauses 15% of the time (kappa 0.14), and each matched the key at kappa
  0.05 (`50_analysis/results/annotation_d45/cases/agreement.json`). Part is notation (`cl-4.2` against `cl-4(2)`)
  and part is that several reasonable clause sets support the same outcome. v3 dropped these cases. The test items do not depend on them: a fault plants the replaced clause into an
  answer, and catching it is scored on that planted clause alone.
- **Controls judged not CORRECT (17 of 40) have the same cause**: the correct answers cite the one rule the generator
  checked (INCOMPLETE 8, WRONG_CITATION 5, WRONG_DECISION 3, UNCLEAR 1). A control that misses a deciding clause
  can be flagged rightly, so it biases false alarms upwards. It does not touch catches or deference.

## 2. Annotation rules (replaces the first and fourth bullets of v3 section 3, "Changes from annotation")

- A case is dropped when its adjudicated decision differs from the key, or, for a rejected case, its blocking stage
  differs. A case is never relabelled.
- A case whose deciding clauses alone differ is **kept**, and listed in the seal manifest (`clause_disputed`).
- The controls check is **reported, not a gate**: the CORRECT rate, and the kept cases whose checked control was
  judged anything else (`controls_flagged`).
- The other bullets (links, R3 quotes, clauses whose links are all rejected, stop rule 1, the fingerprint) stand.

At adjudication this keeps 42 cases on 14 distinct replaced clauses (`seal_test_v3.py`, preview on 2026-10-29).

## 3. Sensitivity analyses (added to v3 section 6)

Both are run on the same blocks, with the same tests, and reported next to every primary result. Neither replaces
it, and neither enters the Holm family.

- **S1, without flagged controls:** every item of the cases in `controls_flagged` removed.
- **S2, v3's strict rule:** every item of the cases v3 would have dropped (`strict_dropped`) removed. With fewer than
  10 clauses it is descriptive only (stop rule 1).

Reading, written now: "If a primary result keeps its sign under S1, it does not depend on the flawed controls. If it
changes sign, we report it as dependent on them." Q2 (deference) reads no control and is reported under S1 only to
show it is unchanged.

## 4. Annotation audit as a reported result (added to v3 section 6, descriptive)

The paper reports the audit: cases the key got wrong at the base (decision, blocking stage), deciding-clause
disputes, controls CORRECT rate and its reasons, link changes, and annotator agreement. No test; per case and pooled.

## 5. Dated changes to the signed procedure

- **Annotator meeting dropped (Samruddhi Kakade's proposal, 2026-10-28).** Unnati Shah adjudicated every disagreement
  directly, from the sheets and the source documents, without the answer keys, on 2026-10-29. The disclosure in v3
  section 3 reads: "Disagreements were adjudicated by a third author, without a meeting of the annotators, ..."
- **Human scorer check (H-16): 35 of 50 (70%), below the 95% gate.** In all 15 disagreements the mechanical facts give the
  scorer's label under the written rule (`50_analysis/results/scorer_check/scorer_check_disagreement_facts.csv`;
  Unnati Shah confirms each row before signing). The scorer is not changed. 10 of the 15 lie on the boundary between
  "wrong clause" and "wrong reason", 3 between "right catch" and "wrong reason", 2 between "invalid" and "no flag". The paper reports the raw 70% as a failed gate, agreement after the
  rule check, and E5 (amendment 1), which shows each result under the looser scoring rules.
- **Analysis cutoff.** v3's "Sat 17 October 2026, 18:00 IST" has passed. See section 5d.

## 5b. The no-record arm, R4n (added to amendment 1, section 2 and 3)

**Why.** In the registry, a clause with no outgoing link reads `in_force` on R4's status line
(`verify_independent.execute_registry_llm`). The registry records amendments; it cannot tell an unamended clause
from a dropped link, so "in force" asserts more than it knows. Q2 asks whether reviewers follow that line. R4n asks
whether stating only what the registry knows changes that.

**Arm.** R4n is R4 with one word changed: a status value `in_force` reads `no_amendment_recorded`. Evidence, prompt,
model, items, damage functions and seeds are identical (unit test `test_no_record_changes_only_the_in_force_word`).
It runs intact and at drop25 and drop50, seeds 0–4, on S-both and C, for the capable models (seed 0 for the others).

**Outcomes.**
- **NoRec (primary, per capable model):** on the dropped-link faults that define Defer (intact registry catches,
  damaged one misses; any drop, any seed), the item's R4n-damage catch minus its R4-damage catch, averaged within
  clause; bootstrap and sign-flip over clauses. The primary family becomes 10 tests (amendment 1's 8 plus NoRec for
  each capable model), Holm.
- **Cost (descriptive):** false alarms on matched controls and on C, R4n against R4, intact and drop50.
- Reading, written now: "If NoRec is positive and the false-alarm cost is small, telling the reviewer that no
  amendment is recorded, instead of that the clause is in force, recovers catches the damaged record loses. If
  NoRec is not significant, we report no evidence that the wording matters, not its absence. If the cost exceeds
  the gain, we report the trade-off, with both numbers."

## 5c. Reporting (added to v3 section 6)

- **Headline measure:** discrimination (catch minus matched false alarm), never catch alone. Every rate is reported
  with its counts (k/n) and the number of clauses, and each main cell with its confusion counts: caught faults,
  missed faults, flagged controls, passed controls.
- **Reference rows are labelled as such.** R5 recovers the registry's own links by construction (faults are planted
  on registry links), and R4 at the intact registry is told the answer. Both are reported as reference points,
  not findings.
- **Descriptive splits, no test:** explicit against implicit amendment wording, outcome-changing against basis-only
  faults, and cost per arm (prompt and completion tokens, seconds per call, from the saved rows).
- **Registry audit:** of the 34 randomly sampled links (seeded 20% of the links not used by test items), the share
  adjudicated NO_CHANGE or a different relation, with a Wilson interval; the 18 test-item links reported separately.
  It describes links the registry asserts, not links it misses (`40_data/link_audit_v1/`).

## 5d. Run order and cutoff (replaces v3 stop rule 9 for this run)

Blocks run in priority order (`run_test_v3.sh`): the capable models' R2, R4, R4n, R5, R5-damage, then R4-damage and
R4n-drop seed by seed; then the secondary rungs; then the other models. The analysis cutoff is 24 hours after the
local run starts. A block not finished by then is reported as not run, and the analysis uses only finished blocks;
a contrast whose blocks are incomplete is reported as not run, never estimated from part of a block.

## 6. Code (agent; done before signing, inert until the seal)

- `seal_test_v3.py`: the rules of section 2; manifest fields `clause_disputed`, `controls_flagged`,
  `controls_checked`, `strict_dropped`.
- `suryabench.analysis.ladder`: `--sealed TEST_MANIFEST_v3.json --sensitivity S1|S2`.
- `verifier_probe` and `verify_independent`: the R4n configurations (`validity-regnorec`, `validity-regnorec-<damage>-s<seed>`).
- `suryabench.analysis.ladder`: `NoRec` in the primary family, R4n discrimination by state.
- `build_link_audit.py`: the link-audit table.
- `make_numbers_v3.py`: audit macros (`NCandidateCases`, `NDroppedDecision`, `NClauseDisputed`, `NStrictKept`,
  `NControlsChecked`, `NControlsFlagged`, `PctControlsCorrect`) from the seal manifest.

## 7. Signatures

Each author adds a dated line. Signing means: this amendment was agreed after adjudication, before the seal, and
before any model saw a test item. On 2026-10-29 the lead author instructed that the seal and run proceed on her
approval, stating that the co-authors agree; lines below are added only by each author.

- Unnati Shah:
- Samruddhi Kakade:
- Aum Patel:
