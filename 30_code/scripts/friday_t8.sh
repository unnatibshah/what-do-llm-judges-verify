#!/usr/bin/env bash
# T8 on Friday (D45), after both annotators submit: agreement on the shared links and cases, then the adjudication
# draft. It never seals; the seal is a separate command after Unnati adjudicates.
# Usage (repository root): bash 30_code/scripts/friday_t8.sh
set -euo pipefail
ANN=${ANN:-20_method/annotation}  # ANN, OUT and ADJ may be overridden for a scratch rehearsal
OUT=${OUT:-50_analysis/results/annotation_d45}
ADJ=${ADJ:-$ANN/adjudication}
export PYTHONPATH=30_code/src:30_code/scripts
PY=.venv/bin/python
[ -e "$OUT" ] && { echo "$OUT exists; saved results are immutable. Move it aside first." >&2; exit 1; }
for w in A B; do for s in links cases controls; do
  [ -s "$ANN/sheets_$w/${s}_$w.csv" ] || { echo "missing $ANN/sheets_$w/${s}_$w.csv" >&2; exit 1; }
done; done
[ -s "$ANN/sheets_B/r3_quotes_B.csv" ] || { echo "missing $ANN/sheets_B/r3_quotes_B.csv" >&2; exit 1; }

# agreement: the script scores the items both annotators have, i.e. the shared 15 links and 20 cases
$PY 30_code/scripts/annotation_agreement.py --a $ANN/sheets_A/links_A.csv --b $ANN/sheets_B/links_B.csv \
  --key $ANN/LINKS_KEY_DO_NOT_SHARE.csv --out $OUT/links
$PY 30_code/scripts/annotation_agreement.py --a $ANN/sheets_A/cases_A.csv --b $ANN/sheets_B/cases_B.csv \
  --key $ANN/ANSWER_KEY_DO_NOT_SHARE.csv --out $OUT/cases

$PY 30_code/scripts/annotation_split.py merge --dir $ANN --out $ADJ

echo
echo "== Unnati adjudicates these rows in $ADJ (fill the answer columns, set decided_by to your name) =="
grep -H ADJUDICATE $ADJ/*.csv | cut -d, -f1 || echo "(none)"
echo
echo "Then: .venv/bin/python 30_code/scripts/seal_test_v3.py --adjudicated $ADJ"
echo "(it refuses while any row is still marked ADJUDICATE). Commit, git tag test-seal-v3, push the tag."
