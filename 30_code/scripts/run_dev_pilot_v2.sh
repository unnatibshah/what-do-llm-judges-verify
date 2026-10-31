#!/usr/bin/env bash
# Dev pilot for Paper A v2 (plan WP7). Dev split only; never --allow-test.
# Usage: run_dev_pilot_v2.sh <generator-model> <cross-model-verifier>
# Resumable: finished runs are skipped (index keyed by code hash), model calls are cached.
# A failing step is logged as FAIL and the queue continues; see <out>/STATUS.
set -u
cd "$(dirname "$0")/../.."
source .venv/bin/activate
GEN="$1"; XVER="$2"
SLUG=$(echo "$GEN" | tr ':/.' '___')
OUT="50_analysis/results/pilot_v2/$SLUG"
mkdir -p "$OUT"
CASES=40_data/benchmark/dev_cases_v2.json
CORPUS=r3  # v2 runs use corpus r3 (2026-10-01); r2 only to reproduce retired results
ALL="N C S-swap S-both J A O"
OFF="C S-swap S-both J A"  # P3 and the metadata contrast of the validity prompt (D29)
NOISE="reg_noisy25_s0 reg_noisy25_s1 reg_noisy25_s2 reg_noisy25_s3 reg_noisy25_s4 reg_noisy50_s0 reg_noisy50_s1 reg_noisy50_s2 reg_noisy50_s3 reg_noisy50_s4 reg_spurious10_s0 reg_spurious10_s1 reg_spurious10_s2 reg_spurious10_s3 reg_spurious10_s4"
# Every configuration analysis/prereg.py needs (EXPECTED_LABELS at metadata on, EXPECTED_META_OFF at off);
# tests/unit/test_prereg.py parses the run lines below and checks the two agree. One generator pass per
# condition (metadata on, D27) is shared by every line.
run() {  # name, args...  (steps named in $SKIP are left for a later invocation)
  local name="$1"; shift
  case " ${SKIP:-} " in *" $name "*) echo "== $(date -u +%FT%TZ) DEFER $name" >> "$OUT/STATUS"; return;; esac
  echo "== $(date -u +%FT%TZ) START $name" >> "$OUT/STATUS"
  python 30_code/scripts/run_exposure_matrix.py --model "$GEN" --cases "$CASES" --corpus "$CORPUS" --out "$OUT" "$@" >> "$OUT/pilot.log" 2>&1
  local rc=$?
  if [ $rc -eq 0 ]; then echo "== $(date -u +%FT%TZ) DONE $name" >> "$OUT/STATUS"
  else echo "== $(date -u +%FT%TZ) FAIL $name (exit $rc)" >> "$OUT/STATUS"; fi
}
run main       --conditions $ALL --meta on --arms arm3 arm3_reflect arm4_100n reg_oracle reg_real reg_real_llm $NOISE --recovery arm3 reg_oracle
run validity   --conditions $ALL --meta on --arms arm3 --variant validity
run para1      --conditions $ALL --meta on --arms arm3 --variant support-p1
run para2      --conditions $ALL --meta on --arms arm3 --variant support-p2
run tax        --conditions $ALL --meta on --arms arm3 --taxonomy
run tax_v      --conditions $ALL --meta on --arms arm3 --variant validity --taxonomy
run xmodel     --conditions $ALL --meta on --arms arm3 --verifier-model "$XVER"
run metaoff    --conditions $OFF --meta off --arms arm3
run metaoff_v  --conditions $OFF --meta off --arms arm3 --variant validity
echo "== $(date -u +%FT%TZ) PILOT_DONE" >> "$OUT/STATUS"
