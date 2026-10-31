# FINAL-EXECUTION-PLAN (written 2026-10-30, before any run below; commit hash records the time)

Scope: the minimum experiments that close the confounds in the central claim (FINAL-RESEARCH-DECISION.md §5).
Everything else is excluded (FINAL-RESEARCH-LOCK.md §12). All runs write to `50_analysis/results/evalkit_rfc_v2/`;
`evalkit_rfc/` stays as is. Unit of analysis: the RFC link (never the call or the model×item cell).

## Code change (done before any run)

- `evalkit.rfc_decoys` + `decoy_items`: one decoy per test link, matched on `same_title` (33 same / 15 different over
  48 links, 18/6 over the 24-link prefix). A decoy is an RFC pair where the newer RFC *Updates* the older one and the
  older one was never obsoleted, so an answer citing the older one as of 2026-10-01 is **correct**. Sampled with seed 0
  from 1,466 such pairs (69 same-title), disjoint from the test and few-shot documents.
- Context `caveat-damaged`: `status-damaged` with the record header adding "(this record is incomplete: it omits some
  replacements, so a document it lists as in force may have been replaced)".
- Prompts of every existing context are byte-identical before and after (sha256 over all 1,296 prompts:
  `02d675e84b58aecb` both ways). Tests: `test_decoys_*`, `test_caveat_*`.

## Experiments

| | E1 Shortcut (decoys) | E2 Authority vs information (caveat) | E3 Power (48 links) |
|---|---|---|---|
| Question | Are text-only catches replacement detection, or "older doc beside a newer same-topic doc"? Is gap deference partly rational? | Is gap deference caused by the record's implied authority, fixable by saying the record is incomplete? | Do the 12-link deference contrasts hold on 24 dropped links? |
| Conditions | decoys in `both-texts`, `status`, `status-damaged`, `caveat-damaged` | `caveat-damaged` vs `status-damaged` vs `both-texts`, same dropped faults | all four contexts on 48 links |
| H (confirmatory) | H1: decoy validity false-alarm rate with `both-texts` is lower than the fault catch rate (discrimination > 0, bootstrap CI over links excludes 0) for each frontier model | H2a: on dropped faults, catch(`status-damaged`) < catch(`both-texts`) (replicates D51; exact McNemar, Holm over models). H2b (two-sided, no direction assumed): catch(`caveat-damaged`) vs catch(`status-damaged`) | sample is the design of E1/E2 |
| Exploratory | decoy FA by same/different title; decoy FA under `caveat-damaged` (does caution cost false alarms?) | bare-pass share; rationale kind | per-link heterogeneity |
| n | 48 decoys, 48 faults | 24 dropped-link faults per model (damage seed 0 over 48 links) | |
| Power | detects decoy FA ≥ 25 pts below catch at α=.05 with >.9 (binomial, independent sets) | 24 pairs: 7 one-sided discordant pairs give p=.016; a 40-pt restoration expected → power >.9; a 15-pt one is not detectable and would be reported as "no evidence of change", not "no change" | |
| Acceptance | H1 holds → text catches are not a title shortcut; H1 fails → the deference result is reframed as "evaluators trade one heuristic for another" and the shortcut becomes a finding | H2b restores ≥ half of own catches → the paper says deference is prompt-authority and fixable by labelling the record (practical advice); no restoration → deference is robust to an explicit caveat (stronger claim) | |

Either outcome of every hypothesis is publishable; the paper's claims follow the acceptance column, written before the runs.

## Models (minimum set, one per family that showed the effect or its absence)

| Model | Why | Where | Cost |
|---|---|---|---|
| Gemma 4 26B | full deference (10→0), open weights | Google API, free tier (`GEMINI_API_KEY`) | $0, ~2 h |
| Gemini 3.1 Pro | full deference (12→0), best reader | Kaggle Benchmarks proxy (user's Kaggle session) | $0 on Kaggle quota |
| GPT-5.5 | partial deference (11→4) | Kaggle Benchmarks proxy | $0 on Kaggle quota |
| Claude Opus 4.5 | no deference (11→10) | Kaggle Benchmarks proxy | $0 on Kaggle quota |
| Qwen 2.5 32B | date-blind reviewer; 48-link baseline already exists | Kaggle 2×T4 (co-author) | $0, optional |

Calls per model: 4 contexts × (48×3 + 48) = 768, minus cached replies. If run on paid APIs instead of Kaggle:
~0.8M input and ~0.2M visible output tokens per model; with reasoning tokens, budget **≤ $75 total for the three
frontier models**. Paid use needs the lead author's authorisation; Kaggle quota does not, but needs her session.

## Statistics

Per model: exact McNemar on paired dropped faults (H2a, H2b), Holm across the models in each family of tests.
Decoys: right-reason catch minus decoy validity FA, bootstrap over links (2,000 resamples), Wilson intervals for
rates. Pooled across models only as a mixed-effects logit with link random intercepts (exploratory). No claim of
significance is read as size; every result is reported as k/n.

## Timeline (from lock approval)

- Week 1 (by 2026-11-06): lock signed; Gemma E1–E3 done locally; Kaggle notebook for the three frontier models
  handed over and run; novelty audit; verification report.
- Week 2 (by 2026-11-13): import frontier blocks (hash check), analysis, tables, figures.
- Week 3 (by 2026-11-20): paper_v5 manuscript (new directory; paper_v4 kept), evalkit README + example.
- Week 4 (by 2026-11-27): four hostile reviews, fixes, final review, submission package, checklist.

## Amendment v2 (2026-10-30, lock v2, before any E1–E3 result)

- **Decoys (A2):** nearest-neighbour matching replaces stratified random sampling (`rfc_decoys`, `decoy_cost`).
  Balance over 48 (`decoy_balance`): same IETF area 37/48; standardised mean differences title similarity −0.22, old
  date 0.04, new date 0.02, gap −0.02, old abstract length −0.19, new abstract length −0.55 (updating RFCs have
  shorter abstracts; reported as a limitation).
- **Framing arms (A3):** `norecord-damaged` (wording) and the new `lowauth-damaged` (authority) join `caveat-damaged`
  (warning). H2b covers all three against `status-damaged`, Holm over arms × models. Power as for E2: 24 pairs per
  model; a restoration of ≥ 40 points is detectable, smaller ones are reported as inconclusive.
- **Runs:** six contexts × (48 × 3 + 48 decoys) = 1,152 items per model; for the three frontier models about 760 are
  new (D51 replies to identical prompts are reused from the cache). Gemma: free API, restarted with all six contexts.
  Frontier: `30_code/scripts/kaggle/run_final_e123.sh` via `final_e123.ipynb`, package `surya-final-kaggle.zip`
  (commit a1e50136), dry-run with a stub model: all six contexts, cache hits as expected, packing after each context.

## Essential vs optional

| Essential (submission blocked without it) | Optional (future work; does not block) |
|---|---|
| E1–E3 for Gemma + three frontier judges | Qwen 32B / GPT-OSS on the framing arms |
| Import with hash check, independent recompute | More prompt paraphrases, more seeds |
| paper_v5 with per-model, per-item results | New corpora (legal, standards) |
| evalkit README, worked example, tests | Title/ID masking variants |
| Four hostile reviews + final review | Re-keying Study 1 |
| Anonymised link, sign-off, declarations (human) | Packaging as a CLI |

## Amendment v3: damage seed 1 (2026-10-30, approved by the lead author; written before any seed-1 call)

**Why.** All gap-fault results rest on one random choice of dropped links (seed 0); the pilot showed that a different
choice can change a judge's result (METHODS-RISK-REPORT row 1).

**What runs.** The primary comparison only: `both-texts` (identical prompts, served from the cache) and
`status-damaged` with `--damage-seed 1`, for every judge that has seed-0 results (Gemma 4 26B, GPT-5.5, Claude
Opus 4.5, and Gemini 3.1 Pro once its seed-0 runs exist). No presentation conditions. Results in
`50_analysis/results/evalkit_rfc_v2_seed1/`.

**Items.** Seed 1 drops 24 links; 12 are also dropped by seed 0, 12 are new. Only fault prompts whose drop status
changes are new requests (24 per judge).

**Analysis, fixed now.**
1. *Seed-specific (primary).* H2a on seed 1 exactly as on seed 0: per judge, exact two-sided McNemar on the 24 paired
   gap faults (`both-texts` vs `status-damaged`), Holm across the judges of seed 1. Same threshold (.05). Seed 0 and
   seed 1 are reported side by side; neither replaces the other.
2. *Overlap.* For each judge: the 12 shared gap links (outcomes under both seeds), the 12 seed-0-only and 12
   seed-1-only links. On shared links the `status-damaged` prompt is identical across seeds, so replies are the same
   cached replies; they are not independent observations and are counted once.
3. *Pooled (secondary, descriptive).* Unit = unique link in the union of the two gap sets (36 links per judge). Per
   link, d = (caught with no record) − (caught with the damaged record); a link in both gap sets contributes one value
   (its reply is identical). Report the mean of d with a 95% bootstrap interval over links (2,000 resamples) and an
   exact sign test on the links with d ≠ 0. No pooling across judges.
4. *Reading.* If seed 1 shows a smaller or reversed drop for a judge, that is reported as such for that judge; the
   pooled estimate does not replace the seed-specific result.
