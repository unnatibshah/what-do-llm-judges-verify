# Preregistration v3, amendment 1 (DRAFT): registry or reviewer (D48)

**Status: DRAFT, 2026-10-28. Not signed, not filed.** Drafted by the AI agent at the lead author's request. It takes
effect only when all three authors sign section 7 below, **before the test set is sealed (T8) and before the OSF
filing**. `PREREGISTRATION_v3.md` is locked and unchanged; where this amendment says nothing, v3 holds as written.
Both files are filed on OSF together.

## 1. Why

The dev pilot (`00_tracking/status/T4-PILOT-STATUS.md`; `50_analysis/results/probe_v2/summary.md`) suggests that
the v3 primary contrast, R4 − R2, will come out large and in the expected direction: a reviewer told that a clause is
not in force flags it. That result is close to known (Stale-Document Poisoning, for answer-writing models) and does
not answer what a pipeline builder needs to know. Real amendment records are incomplete and sometimes wrong. The
questions that matter are whether an LLM reviewer adds anything over a lookup in the record it is given, and whether
it corrects a wrong record from the text or follows it. v3 already contains the instrument for both (E3, damaged
registries, D31); this amendment makes those comparisons primary, restores the seeds they need, and adds the outcome
that shows how scoring choices change a reviewer's apparent skill (E5).

No test item has been shown to any model. The test set is not sealed. The amendment is decided on dev evidence only.

## 2. Questions (replaces v3 section 1, E1 to E4, as to which are primary)

- **Q1, net value over the record (primary).** For each capable model and registry state (intact, drop25, drop50,
  spurious10), discrimination at R4 (R4-damage for damaged states) minus discrimination at R5 (R5-damage).
  Expected: R5 ≥ R4 on the intact registry; the gap narrows or reverses as links are dropped.
- **Q2, deference (primary).** On faults whose replaced clause the intact registry flags and a drop-damaged registry
  does not (so the status line reads "in force"), the capable model's catch at R2 minus its catch at R4-damage.
  Expected: positive (the reviewer follows the registry over the text).
- **E1, the reference ladder (secondary; was primary in v3).** Unchanged in content.
- **E2, can't confirm (secondary).** Unchanged.
- **E3′, spurious links (secondary; replaces the false-alarm half of v3 E3).** On correct decisions citing a clause a
  spurious link marks as replaced, false alarms at R4-spurious10 minus false alarms at R2.
- **E4, misnamed alarms (secondary).** Unchanged.
- **E5, scoring rules (descriptive, new).** For each model and rung: catch under "any finding" and "clause named"
  beside the right-reason catch; on matched controls, any finding beside a validity-reason finding
  (`not_in_force`, `wrong_jurisdiction`, `not_applicable`; the saved `validity_reason` field). No test.

## 3. Outcomes and analysis (adds to v3 sections 5 and 6)

- **Discrimination (Q1).** Per replaced clause: right-reason catch rate on its S-both faults minus the any-finding
  false-alarm rate on their matched S-both controls (invalid counts as in v3). For a damaged registry, each rate is
  first averaged over the seeds run, within the clause. Then averaged over clauses. Condition C false alarms are
  reported beside it, not inside it.
- **Deference (Q2).** Unit: the (clause, damage level, seed) combinations where the replaced clause is flagged by the
  intact registry (`registry_real_v2_r3.json`, or the sealed registry if T8 writes one) and not by the damaged one,
  over drop25 and drop50 and every seed run; "flagged" means the R5 lookup on that registry catches the item. Per
  clause, the mean over its (item, damage, seed) combinations of (the item's R2 catch − its R4-damage catch). Then
  averaged over clauses.
- **Primary family:** for each capable model, R4 − R5 at intact, drop50 and spurious10 (Q1) and deference (Q2):
  **8 tests**, sign-flip over clauses as in v3, Holm at α = 0.05. drop25 is reported beside them, uncorrected. Under
  the API fallback the family keeps the four `qwen2.5:14b` tests. A contrast with fewer than 10 clauses is reported
  descriptively and enters the family with p = 1.
- **Secondary (uncorrected, labelled):** everything v3 lists as secondary, plus v3's former primaries R4 − R2 and
  R2 − R0, and E3′.
- **E5:** clause-averaged rates for each scoring rule, no test, no interval required.

## 4. Pre-written readings (added before v3 section 7; v3's rules keep their wording)

1. R4 − R5 not positive after Holm at any registry state, for a capable model: "For this model, the reviewer did not
   discriminate better than a lookup in the registry it was given, even when the registry was damaged."
2. R4 − R5 positive after Holm at a damaged state but not intact: "The reviewer added value over the registry only once
   the registry was damaged, from [the first such state]."
3. R4 − R5 negative after Holm on the intact registry: "Adding the reviewer to a correct registry made review worse than
   the registry alone."
4. Deference positive after Holm: "A wrong 'in force' line removed catches this reviewer makes without any registry: it
   followed the registry over the text." Not significant: "We found no evidence of deference" (never "the reviewer
   does not defer").
5. Any-finding catch above right-reason catch by more than 10 points for a capable model at R0 to R2: "Scoring by flags
   alone would have credited this reviewer with [the gap] points of catches it made for the wrong reason."

v3 rule 1 (fewer than 10 distinct replaced clauses: no primary claim) applies to Q1 and Q2. v3 rules 2 to 5 now
read on the secondary ladder; rule 3's "after Holm" becomes "uncorrected".

## 5. What runs (changes the v3 section 4 table)

| block set | change | extra calls |
|---|---|---|
| E3, R4-damage | seeds 0–4 for `qwen2.5:14b` and `gemma-4-26b-a4b-it` (seed 0 only for `qwen2.5:7b`, `llama3.1:8b`) | about 720 per capable model (4 seeds × 180) |
| E3, R5-damage | unchanged (all 5 seeds, deterministic) | 0 |

- **Cost.** v3 estimates all five seeds at about 16 h of `qwen2.5:14b` on the lead's Mac; the GPU server is faster.
  Gemma's seeds are API calls, subject to the v3 API fallback.
- **Run order.** Within each capable model: R2, R4 and their C; R4-damage seeds 0–4; R0; then the rest in v3 order. The
  primary blocks finish first.
- **Unchanged:** items, prompts and their hashes, models and digests, scoring of a catch and a false alarm, invalid
  rule, damage functions and seeds, bootstrap and sign-flip settings, minimum-clause rules.

## 6. Code before the run (agent, after signing)

- `suryabench.analysis.ladder`: discrimination per rung and registry state, the deference set and contrast, the
  E5 rates, and the new primary family with Holm (one unit test each).
- `make_numbers_v3.py`: emit every macro in `60_paper_drafts/paper_v3/numbers_pending.tex`.
- `make_figures_v3.py`: `fig_registry_damage.pdf` (discrimination by registry state; R4, R5, R2; one panel per
  capable model).
- `make_claims_v3.py`: readings 1 to 5 above, one unit test per rule.
- `run_test_v3.sh`: R4-damage seeds 0–4 for the capable models, in the order of section 5.

## 7. Signatures

Each author adds a dated line. Signing means: the amendment was agreed before the seal and before any model saw a
test item.

- Unnati Shah: I approve this amendment before the seal, Unnati Shah, Oct 29, 2026
- Samruddhi Kakade:
- Aum Patel: I approve this amendment before the seal, Aum Patel, Oct 29, 2026
