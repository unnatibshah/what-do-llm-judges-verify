# Provenance

This release is a snapshot of a private development repository. Its history is not included; the commits below
(hash, time with UTC offset, message) record when the analysis plan, its amendments and each block of results were
committed there. Every result block also carries its own model version and a hash of the harness code (13b235179f49).

## Analysis plan (`00_tracking/final/FINAL-EXECUTION-PLAN.md`)

- `87bd2c7c` 2026-10-30T09:31:44-04:00 — Final program: decoy items and caveat-damaged context in evalkit (old prompts byte-identical); execution plan with hypotheses before any run
- `2d3478cb` 2026-10-30T09:43:11-04:00 — Lock v2 approved with amendments A1-A6 (v1 kept); plan v2 (decoy balance, framing arms, essential vs optional); Kaggle notebook
- `7e8119b9` 2026-10-30T14:25:23-04:00 — Plan amendment v3: damage seed 1 for H2a only, analysis fixed before any seed-1 call (seed-specific McNemar + Holm; overlap; pooled over unique links)

## Final results (`50_analysis/results/evalkit_rfc_v2*/`), first commit of each block

- `b664e09f` 2026-10-30T10:24:06-04:00 — E1-E3: Claude Opus 4.5 imported from Kaggle (6 contexts, 48 links + decoys, hash 13b235179f49, 0 invalid; archive kept); analysis script (rescoring check, H1/H
- `300e24ee` 2026-10-30T11:16:30-04:00 — E1-E3: GPT-5.5 partial import (4 of 6 contexts; Kaggle quota ran out at caveat-damaged); Gemma both-texts block; analysis handles partial runs
- `ecc865dd` 2026-10-30T13:36:43-04:00 — E1-E3: Gemma norecord-damaged block; analysis outputs regenerated (pilot overlap, abstract-overlap split)
- `d56ebddb` 2026-10-30T14:10:34-04:00 — E1-E3: Gemma caveat-damaged block; analysis regenerated
- `859f8b65` 2026-10-30T14:28:29-04:00 — Damage seed 1 (amendment v3): Gemma both-texts + status-damaged (17 -> 0 on 24 gap faults; 12 shared links with identical replies); seed-1 analysis, link-level
- `fbb9e62f` 2026-10-30T15:05:03-04:00 — E1-E3: Gemma lowauth-damaged block; Gemma's six contexts complete
- `6c52cbb1` 2026-10-30T20:05:07-04:00 — Damage seed 1: Claude Opus 4.5 both-texts + status-damaged from Kaggle (code 13b235179f49; 20 -> 13 on 24 gap faults, 7 lost, 0 gained; 12 shared links with id
- `baddba7e` 2026-10-30T20:28:52-04:00 — E2 + damage seed 1: GPT-5.5 lowauth-damaged and caveat-damaged (seed 0) and both-texts + status-damaged (seed 1) from Kaggle (code 13b235179f49; four earlier b
- `c3005d13` 2026-10-30T21:40:50-04:00 — E1-E3: Gemini 3.1 Pro five of six seed-0 contexts and seed-1 both-texts from Kaggle (quota stopped the run; code 13b235179f49; 0 invalid). Gap faults: texts 22
- `065236a1` 2026-10-30T23:09:31-04:00 — E2 + damage seed 1 complete: Gemini 3.1 Pro lowauth-damaged (seed 0) and status-damaged (seed 1) from Kaggle (code 13b235179f49; 0 invalid; earlier blocks byte

## Changes made for this release

- Local absolute paths in `40_data/registries/blind_inputs/AGENT_BRIEF.txt` and
  `40_data/corpus_r3/provenance/retrieval_audit_2026-09-23/*.json` are replaced by `<development repository>` or
  `<home>`, and a host name in `50_analysis/results/probe_test_v3/RUN_START_*.txt` by `<host>`. None of these files is
  covered by a hash list, and no result depends on them.
- `50_analysis/results/evalkit_rfc/repeat/kbench-gemini-3-1-pro/cite-only.json` is the re-run block of the pilot,
  extracted unchanged from a Kaggle archive of the development repository (`evalkit_results_gpt55_damaged.tgz`).
- Not released: reply caches, Kaggle archives, document files and their extracted text, machine translations, the
  annotators' personal records, internal planning and correspondence.
- Paper sources (`60_paper_drafts/paper_v6/`) and `30_code/scripts/make_arxiv.py` synced from development commit `40311ca2` (2026-10-31T01:26:00-04:00): editorial pass, case study moved to supplementary material (`supplement*.tex`, `main_full.tex`), corrected AI-use statement, 1-inch preprint layout. No number, table, reference or result changed.
