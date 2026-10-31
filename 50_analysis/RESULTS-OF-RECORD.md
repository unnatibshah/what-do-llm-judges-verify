# Results of record

Every number in the paper (`60_paper_drafts/paper_v6/`) comes from one of these files. Commands: `REPRODUCE.md`.

## Final runs and damage seed 1 (main text, Appendices B–D)

| What | File |
|---|---|
| RFC index (gold for links and decoys) | `40_data/corpus_staging/rfc/rfc-index.xml` (+ `.sha256`) |
| Replies, seed 0 (4 judges × 6 contexts) | `50_analysis/results/evalkit_rfc_v2/<judge>/<context>.json` |
| Replies, damage seed 1 (4 judges × 2 contexts) | `50_analysis/results/evalkit_rfc_v2_seed1/<judge>/<context>.json` |
| Analysis (rescoring check, H1, H2a, H2b, Holm, seed 1, pooled) | `50_analysis/results/evalkit_rfc_v2/analysis/` (`e123.json`, `e123.md`, `items.csv`, `seed1_links.csv`) |
| Macros and tables | `60_paper_drafts/paper_v6/generated/numbers_e123.tex`, `tab_e123_*.tex`, `prompt_example.tex` |
| Plan and amendments | `00_tracking/final/FINAL-EXECUTION-PLAN.md`; commit times in `PROVENANCE.md` |

Judges: gemma-4-26b-a4b-it (Google API), kbench-gpt-5-5, kbench-gemini-3-1-pro, kbench-claude-opus-4-5 (Kaggle Benchmarks
proxy). Every block records the harness code hash 13b235179f49 and the model version string the provider reported
(for Gemma the API model name; for Gemini a "preview" identifier). Blocks written before the damage-seed option existed
have no `damage_seed` field; they are seed 0.

## Pilot (Appendix A)

| What | File |
|---|---|
| Replies | `50_analysis/results/evalkit_rfc/<model>/<context>.json` |
| Repeated block (Limitations: 30 of 72 replies differ) | `50_analysis/results/evalkit_rfc/repeat/kbench-gemini-3-1-pro/cite-only.json` |
| Macros and tables | `60_paper_drafts/paper_v6/generated/numbers_rfc.tex`, `tab_rfc_*.tex` |

## Case study (Appendices E–L, descriptive)

| What | File |
|---|---|
| Documents (URL and SHA-256 per document, 111) | `40_data/corpus_r3/MANIFEST.json`, `provenance/` |
| Supersession graph | `40_data/corpus_r3/graph/` |
| Sealed test set: cases, clauses, drops, disputes, flagged controls | `40_data/benchmark/TEST_MANIFEST_v3.json` and the files it lists |
| Record as given to the judges; per link, the record's relation, each annotator's and the adjudicated relation | `40_data/registries/registry_real_v3.json`, `40_data/link_audit_v1/links.csv` |
| Annotation: sheets as sent, keys, assignment, adjudicated sheets with each annotator's answers | `20_method/annotation/` |
| Annotator agreement; human scorer check | `50_analysis/results/annotation_d45/`, `50_analysis/results/scorer_check/` |
| Raw replies per block | `50_analysis/results/probe_test_v3/<model>/blocks/*.json`; exploratory `probe_test_v3_exploratory/`; repeat `probe_test_v3_repeat/`; dev check `probe_v3_dev_norec/` |
| Rates, contrasts, Holm, sensitivity | `50_analysis/results/ladder_test_v3{,_S1,_S2,_exploratory}/` |
| Macros, tables, figures | `60_paper_drafts/paper_v6/numbers.tex`, `generated/tab_*.tex`, `generated/fig_*.png` |
| Plan | `20_method/PREREGISTRATION_v3*.md` |
