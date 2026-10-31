# Reproduce

From the repository root after `pip install -e .` (Python ≥ 3.11). Nothing here calls a model.

## Final runs (Results, Appendices B–D)

    PYTHONPATH=30_code/src python 30_code/scripts/analyse_final_e123.py --tex 60_paper_drafts/paper_v6/generated

Rescores every stored reply from its raw text (stops on any mismatch), then writes
`50_analysis/results/evalkit_rfc_v2/analysis/` and `60_paper_drafts/paper_v6/generated/{numbers_e123.tex,tab_e123_*.tex,prompt_example.tex}`.
These reproduce byte for byte.

## Pilot (Appendix A)

    PYTHONPATH=30_code/src python -m suryabench.evalkit --tex 60_paper_drafts/paper_v6/generated

`evalkit.py` is kept exactly as run (code hash 13b235179f49, recorded in every block). With it, this command also writes
two empty rows (`caveat-damaged`, `lowauth-damaged`, contexts the pilot never ran) into `tab_rfc_disc_*.tex` and sets
`\RfcNContexts` to 12; the committed tables omit those rows and say 10. No number differs. The repeated Gemini 3.1 Pro
`cite-only` block cited in the Limitations (30 of 72 replies differ; 12 against 11 catches) is
`50_analysis/results/evalkit_rfc/repeat/kbench-gemini-3-1-pro/cite-only.json`, to be compared with
`50_analysis/results/evalkit_rfc/kbench-gemini-3-1-pro/cite-only.json`.

## Case study (Appendices E–L, descriptive)

    export PYTHONPATH=30_code/src:30_code/scripts
    R=50_analysis/results
    python -m suryabench.analysis.ladder --blocks $R/probe_test_v3 --out $R/ladder_test_v3
    for s in S1 S2; do python -m suryabench.analysis.ladder --blocks $R/probe_test_v3 \
        --sealed 40_data/benchmark/TEST_MANIFEST_v3.json --sensitivity $s --out $R/ladder_test_v3_$s; done
    python -m suryabench.analysis.ladder --blocks $R/probe_test_v3 $R/probe_test_v3_exploratory --out $R/ladder_test_v3_exploratory
    python 30_code/scripts/make_numbers_v3.py --stage test --ladder $R/ladder_test_v3/ladder.json \
        --ladder-s1 $R/ladder_test_v3_S1/ladder.json --ladder-s2 $R/ladder_test_v3_S2/ladder.json \
        --ladder-all $R/ladder_test_v3_exploratory/ladder.json --sealed 40_data/benchmark/TEST_MANIFEST_v3.json \
        --items $R/probe_test_v3/items.json --out 60_paper_drafts/paper_v6/numbers.tex
    python 30_code/scripts/make_tables_v3.py --ladder $R/ladder_test_v3/ladder.json \
        --ladder-s1 $R/ladder_test_v3_S1/ladder.json --ladder-s2 $R/ladder_test_v3_S2/ladder.json \
        --ladder-exploratory $R/ladder_test_v3_exploratory/ladder.json --out 60_paper_drafts/paper_v6/generated
    python 30_code/scripts/make_figures_v3.py --stage test --ladder $R/ladder_test_v3/ladder.json --out 60_paper_drafts/paper_v6/generated

The ladder files, `numbers.tex`, the case-study tables and the PNG figures reproduce byte for byte (the figure script
also writes PDF copies, which the paper does not use).

## Paper

    cd 60_paper_drafts/paper_v6 && tectonic -X compile main.tex      # also main_2col.tex, main_anon.tex

## Running judges (makes model calls)

`30_code/scripts/run_evalkit.py` (local or API judges; `--decoys`, `--damage-seed`) and
`30_code/scripts/kaggle/run_final_e123.sh` with the notebooks in `30_code/scripts/kaggle/` (Kaggle Benchmarks proxy).
Reply caches are not released, so a re-run makes new calls and, for hosted judges, may not reproduce replies exactly.

## Tests

`python -m pip install pytest && python -m pytest -q 30_code/tests/unit/test_evalkit.py` tests the RFC harness. Other
tests in `30_code/tests/` exercise the case-study pipeline and need files that are not released (document texts,
raw PDFs, earlier paper versions, a local Ollama server); they fail or error in this snapshot.
