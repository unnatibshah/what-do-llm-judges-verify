#!/usr/bin/env bash
# D49: run local panel models of the sealed v3 test on a Kaggle GPU notebook (or any Linux GPU machine), with the
# preregistered Ollama files. Each model runs on one machine only: never run here a model that has blocks elsewhere.
#
#   bash 30_code/scripts/kaggle/kaggle_run.sh llama3.1:8b qwen2.5:7b        # weak models (seed 0 damage)
#   bash 30_code/scripts/kaggle/kaggle_run.sh --capable qwen2.5:14b          # a capable model (all seeds, R4n)
#   bash 30_code/scripts/kaggle/kaggle_run.sh --explore qwen2.5:32b          # exploratory, not preregistered
#   KBENCH_MODEL=<name> bash 30_code/scripts/kaggle/kaggle_run.sh --explore kbench-<slug>   # Kaggle-hosted model
#
# Steps: install and start Ollama (one model in memory), pull each model and bge-m3 and refuse any digest that differs
# from PREREGISTRATION_v3 section 4, install the package, check the sealed test file's sha256, record the machine,
# restore results from an earlier session if one is attached as input, run, and pack the results after every model
# into /kaggle/working/kaggle_results.tgz (download it, or attach it as input to resume in a new session).
set -euo pipefail
cd "$(dirname "$0")/../../.."
CAPABLE=no REPEAT=no EXPLORE=no
[ "${1:-}" = "--capable" ] && { CAPABLE=yes; shift; }
[ "${1:-}" = "--repeat" ] && { REPEAT=yes; shift; }  # exploratory determinism check: R2, R4, R4n again, fresh cache
[ "${1:-}" = "--explore" ] && { EXPLORE=yes; shift; }  # exploratory models (D49): main blocks, own folder
[ $# -ge 1 ] || { echo "usage: $0 [--capable] <model> ..." >&2; exit 2; }
OUT=50_analysis/results/probe_test_v3
[ "${EXPLORE:-no}" = yes ] && OUT=50_analysis/results/probe_test_v3_exploratory
PACK=${PACK:-/kaggle/working/kaggle_results.tgz}
BGE=sha256:7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab

# 1. Ollama, one model in memory
echo "== kaggle_run: install Ollama (if missing)"
command -v zstd >/dev/null || { DEBIAN_FRONTEND=noninteractive apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq zstd < /dev/null; }
command -v ollama >/dev/null || curl -fsSL https://ollama.com/install.sh | sh
if ! curl -s -m 2 localhost:11434/api/tags >/dev/null; then
  OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_NUM_PARALLEL=1 nohup ollama serve > /kaggle/working/ollama.log 2>&1 &
  for _ in $(seq 60); do curl -s -m 2 localhost:11434/api/tags >/dev/null && break; sleep 2; done
fi

digest() { curl -s localhost:11434/api/tags | python3 -c "import json,sys; print(next((m['digest'] for m in json.load(sys.stdin)['models'] if m['name'] in ('$1', '$1:latest')), ''))"; }
want() { grep -F "\`$1\`" 20_method/PREREGISTRATION_v3.md | grep -o 'sha256:[0-9a-f]\{64\}' | head -1; }
check_model() {
  echo "== kaggle_run: pull $1"; ollama pull "$1"
  local got="sha256:$(digest "$1" | sed 's/^sha256://')" exp="$2"
  [ "$got" = "$exp" ] || { echo "REFUSED: $1 digest $got, preregistered $exp" >&2; exit 1; }
  echo "digest ok: $1"
}
check_model bge-m3 "$BGE"
for m in "$@"; do
  case "$m" in
    kbench-*) [ -n "${KBENCH_MODEL:-}" ] || { echo "set KBENCH_MODEL for $m" >&2; exit 1; } ;;
    *) if [ "$EXPLORE" = yes ]; then ollama pull "$m"; echo "exploratory $m digest $(digest "$m")"
       else check_model "$m" "$(want "$m")"; fi ;;
  esac
done

echo "== kaggle_run: install the package and check the sealed file"
# 2. package and sealed file
python3 -c 'import sys; assert sys.version_info >= (3, 11), sys.version'
# Kaggle's Python cannot build a venv (no ensurepip) and already has numpy, pydantic and matplotlib: use it directly
if ! .venv/bin/python -c "import numpy, pydantic, pypdf" 2>/dev/null; then
  rm -rf .venv && mkdir -p .venv/bin && ln -s "$(command -v python3)" .venv/bin/python
  python3 -m pip install -q pypdf pydantic
fi
(cd 40_data/benchmark && sha256sum -c test_cases_v3.sha256)

# 3. results from an earlier session (attached as input, packed or unpacked by Kaggle), then the machine record
mkdir -p "$OUT"
prev=$(ls /kaggle/input/*/kaggle_results*.tgz /kaggle/input/*/*/kaggle_results*.tgz 2>/dev/null | head -1 || true)
prev_dir=$(ls -d /kaggle/input/*/50_analysis/results/probe_test_v3 2>/dev/null | head -1 || true)
if [ -n "$prev" ]; then echo "restoring $prev"; tar xzf "$prev"
elif [ -n "$prev_dir" ]; then echo "restoring $prev_dir"; cp -R "$prev_dir/." "$OUT/"; fi
{ echo "--- session"; date -u +%Y-%m-%dT%H:%M:%SZ; uname -a
  nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader || true
  ollama --version; python3 --version; echo "models: $*"; } >> "$OUT/MACHINE_kaggle.txt"

echo "== kaggle_run: running; a line prints as each block finishes (15-30 min each)"
# 4. run, packing every 15 minutes (a timed-out session loses at most that) and after every model
( while sleep 900; do tar czf "$PACK.part" "$OUT" && mv "$PACK.part" "$PACK"; done ) &
PACKER=$!
trap 'kill $PACKER 2>/dev/null || true' EXIT
for m in "$@"; do
  if [ "$EXPLORE" = yes ]; then
    probe=30_code/scripts/run_verifier_probe.py; [ "${m#kbench-}" != "$m" ] && probe=30_code/scripts/kaggle/run_kbench_probe.py
    OUT=$OUT PROBE=$probe REGISTRY=40_data/registries/registry_real_v3.json bash 30_code/scripts/run_test_v3.sh explore "$m"
    tar czf "$PACK" "$OUT"; echo "packed exploratory $m -> $PACK"; continue
  fi
  REGISTRY=40_data/registries/registry_real_v3.json bash 30_code/scripts/run_test_v3.sh model "$m" "$CAPABLE"
  tar czf "$PACK" "$OUT"
  echo "packed after $m -> $PACK"
  if [ "$REPEAT" = yes ]; then
    OUT=50_analysis/results/probe_test_v3_repeat SURYABENCH_LLM_CACHE=50_analysis/results/probe_test_v3_repeat/llm_cache \
      REGISTRY=40_data/registries/registry_real_v3.json bash 30_code/scripts/run_test_v3.sh repeat "$m"
    tar czf "$PACK" "$OUT" 50_analysis/results/probe_test_v3_repeat
    echo "packed repeat of $m -> $PACK"
  fi
done
echo "kaggle run done: $*"
