#!/usr/bin/env bash
# D52: E1-E3 (decoys, record-framing arms, 48 links) for one Kaggle-hosted model, in a Kaggle notebook whose AI quota
# serves kaggle_benchmarks. Replies already in the attached cache (the D51 runs, same prompts) are reused, not re-asked.
#
#   bash 30_code/scripts/kaggle/run_final_e123.sh kbench-claude-opus-4-5 anthropic/claude-opus-4-5@20251101
#
# Resumable: a finished context is skipped, and every reply is cached. After each context the results are packed into
# /kaggle/working/final_e123_<alias>.tgz; download that file (or attach it as input to resume in a new session).
set -euo pipefail
cd "$(dirname "$0")/../../.."
ALIAS=$1 REAL=$2
SEED=${DAMAGE_SEED:-0}  # a second draw of dropped links: DAMAGE_SEED=1 (own results folder; cache shared)
OUT=50_analysis/results/evalkit_rfc_v2$([ "$SEED" = 0 ] || echo "_seed$SEED")
CACHE=50_analysis/results/evalkit_rfc_v2/llm_cache  # shared: unchanged prompts are never asked twice
PACK=${PACK:-/kaggle/working/final_e123_${ALIAS}$([ "$SEED" = 0 ] || echo "_seed$SEED").tgz}
export SURYABENCH_LLM_CACHE=$CACHE PYTHONPATH=30_code/src:30_code/scripts PYTHONUNBUFFERED=1 KBENCH_MODEL=$REAL
CONTEXTS=${CONTEXTS:-both-texts status status-damaged norecord-damaged caveat-damaged lowauth-damaged}
for ctx in $CONTEXTS; do
  python 30_code/scripts/run_evalkit.py --model "$ALIAS" --links 48 --decoys --damage-seed "$SEED" --contexts "$ctx" --out "$OUT"
  tar czf "$PACK" "$OUT/$ALIAS" "$CACHE/$(echo "$ALIAS" | tr -- '-.:/' '____')"
  echo "== packed $PACK after $ctx"
done
echo "== done: download $PACK"
