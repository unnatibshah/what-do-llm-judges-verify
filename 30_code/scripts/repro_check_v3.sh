#!/usr/bin/env bash
# T11 / U6: rebuild the ladder table and figure 1 from saved replies, with no model call, and compare sha256 with the
# reference outputs. The ladder files must match byte for byte (exit 1 otherwise). Figures are compared too, but their
# bytes depend on the matplotlib and FreeType build, so a figure difference is a warning, not a failure.
#
#   bash 30_code/scripts/repro_check_v3.sh <blocks dir> [reference ladder dir] [stage]
#   bash 30_code/scripts/repro_check_v3.sh 50_analysis/results/probe_test_v3      # U6 on the rented server
#
# Defaults: reference 50_analysis/results/ladder_test_v3 (the T10 ladder output), stage test; figures are compared with
# 60_paper_drafts/paper_v3/generated/. Run from the repository root.
set -euo pipefail
BLOCKS=${1:?usage: $0 <blocks dir> [reference ladder dir] [stage]}
REF=${2:-50_analysis/results/ladder_test_v3}
STAGE=${3:-test}
FIGS=60_paper_drafts/paper_v3/generated
export PYTHONPATH=30_code/src:30_code/scripts
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

.venv/bin/python -m suryabench.analysis.ladder --blocks "$BLOCKS" --out "$TMP"
.venv/bin/python 30_code/scripts/make_figures_v3.py --stage "$STAGE" --ladder "$TMP/ladder.json" --out "$TMP"

h() { shasum -a 256 "$1" 2>/dev/null | cut -c1-64; }
fail=0
for f in ladder.json ladder_per_clause.csv summary.md; do
  if [ "$(h "$TMP/$f")" = "$(h "$REF/$f")" ]; then echo "ok    $f  $(h "$TMP/$f")"
  else echo "DIFF  $f  rebuilt $(h "$TMP/$f")  reference $(h "$REF/$f" || true)"; fail=1; fi
done
for f in fig_ladder.pdf fig_ladder.png; do
  if [ "$(h "$TMP/$f")" = "$(h "$FIGS/$f")" ]; then echo "ok    $f  $(h "$TMP/$f")"
  else echo "warn  $f  differs from $FIGS (check the matplotlib version, or compare the images by eye)"; fi
done
[ "$fail" = 0 ] && echo "REPRODUCED: ladder table from $BLOCKS" || { echo "NOT REPRODUCED" >&2; exit 1; }
