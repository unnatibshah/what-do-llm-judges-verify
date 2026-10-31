#!/usr/bin/env bash
# T4 (D37): the dev pilot of the ladder rungs, per model, each configuration on the conditions where its rung is
# defined (vp.rung): R0 validity-metaoff/S-swap, R1-R2 validity, R3 amendquote/S-both, R4 and R4' regstatus,
# can't-confirm variants, R5 reg-real; condition C for every false-alarm control. Engineering only: no prompt is
# tuned on these numbers. The dev reply cache is copied in first, so unchanged prompts replay and the saved
# probe_v2 results are never written to. Usage (repository root): bash 30_code/scripts/run_probe_v3_dev.sh [models...]
set -euo pipefail
OUT=50_analysis/results/probe_v3_dev
export PYTHONPATH=30_code/src:30_code/scripts SURYABENCH_LLM_CACHE="$OUT/llm_cache"
mkdir -p "$OUT"
[ -d "$OUT/llm_cache" ] || cp -R 50_analysis/results/probe_v2/llm_cache "$OUT/llm_cache"
run() { .venv/bin/python 30_code/scripts/run_verifier_probe.py --model "$1" --out "$OUT" --configs "${@:3}" --conditions $2; }
for m in "${@:-qwen2.5:14b llama3.1:8b}"; do
  for model in $m; do
    run "$model" "S-both S-swap C" validity validity-regstatus validity-cc reg-real
    run "$model" "S-swap C" validity-metaoff validity-cc-metaoff
    run "$model" "S-both C" validity-amendquote
  done
done
echo "T4 probe done"
