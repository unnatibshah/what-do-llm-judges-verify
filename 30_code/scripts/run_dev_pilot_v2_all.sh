#!/usr/bin/env bash
# Dev pilot (cut 2026-10-02): two models only, enough for the kill gate and pipeline checks.
#   qwen2.5:7b (local, full schedule; cross verifier gemma-4-26b-a4b-it, API)
#   gemma-4-26b-a4b-it (API, full schedule; cross verifier qwen2.5:7b, local, so no second local model loads)
# llama3.1:8b, qwen2.5:14b and gemini-3.5-flash-lite run on the test split only (D4 panel, D31 pairs there).
cd "$(dirname "$0")/../.."
export SURYABENCH_MAX_RETRIES=60 SURYABENCH_MIN_INTERVAL=4
S=30_code/scripts/run_dev_pilot_v2.sh
( SKIP=xmodel $S gemma-4-26b-a4b-it qwen2.5:7b ) &
( $S qwen2.5:7b gemma-4-26b-a4b-it ) &
wait
( $S gemma-4-26b-a4b-it qwen2.5:7b )
echo "ALL_PILOTS_DONE $(date -u +%FT%TZ)" > 50_analysis/results/pilot_v2/ALL_DONE
