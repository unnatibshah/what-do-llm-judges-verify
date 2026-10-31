#!/usr/bin/env bash
# D49: regenerate every result file, number, table, figure and the number trace of paper_v3 from the saved replies,
# then build the PDF. No model is called. Run from the repository root.
set -euo pipefail
export PYTHONPATH=30_code/src:30_code/scripts
R=50_analysis/results; P=60_paper_drafts/paper_v3; PY=.venv/bin/python; S=40_data/benchmark/TEST_MANIFEST_v3.json
$PY -m suryabench.analysis.ladder --blocks $R/probe_test_v3 --out $R/ladder_test_v3
for s in S1 S2; do $PY -m suryabench.analysis.ladder --blocks $R/probe_test_v3 --sealed $S --sensitivity $s --out $R/ladder_test_v3_$s; done
[ -d $R/probe_test_v3_exploratory ] && $PY -m suryabench.analysis.ladder --blocks $R/probe_test_v3 $R/probe_test_v3_exploratory --out $R/ladder_test_v3_exploratory
[ -d $R/probe_test_v3_repeat ] && $PY 30_code/scripts/compare_repeat.py
L="--ladder $R/ladder_test_v3/ladder.json --ladder-s1 $R/ladder_test_v3_S1/ladder.json --ladder-s2 $R/ladder_test_v3_S2/ladder.json"
$PY 30_code/scripts/make_numbers_v3.py --stage test $L --ladder-all $R/ladder_test_v3_exploratory/ladder.json --sealed $S --items $R/probe_test_v3/items.json --out $P/numbers.tex
$PY 30_code/scripts/make_tables_v3.py $L --ladder-exploratory $R/ladder_test_v3_exploratory/ladder.json --out $P/generated
$PY 30_code/scripts/make_figures_v3.py --stage test --ladder $R/ladder_test_v3/ladder.json --out $P/generated
$PY 30_code/scripts/make_number_trace.py --manifest $R/ladder_design/candidate_v3_manifest.json --items $R/probe_test_v3/items.json
$PY 30_code/scripts/make_claims_v3.py --ladder $R/ladder_test_v3/ladder.json --scorer-agreement 0.70 --out 80_review/CLAIMS-APPROVED.md
TECTONIC=${TECTONIC:-tectonic}
if command -v "$TECTONIC" >/dev/null; then (cd $P && "$TECTONIC" -X compile main.tex); else (cd $P && latexmk -pdf main.tex); fi
echo "paper_v3 regenerated"
