# 40_data

`corpus/` (46 authentic documents, frozen; `MANIFEST.sha256`) and `benchmark/` (160 cases, sealed; `BENCHMARK.sha256`). Neither is edited after its freeze.

`corpus_r3/` is the staging corpus `SuryaBench-Corpus-2026.10-r3` (r2 + 65 staged documents, all UNVERIFIED; not frozen; built by `30_code/scripts/build_corpus_r3.py` from `corpus_staging/`). `benchmark/test_cases_v2_CANDIDATE.json` is the candidate v2 test split (labels provisional, not sealed; guarded by `TEST_CANDIDATE_HASHES.json`).
