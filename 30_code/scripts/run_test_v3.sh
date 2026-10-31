#!/usr/bin/env bash
# T9: the final test run of PREREGISTRATION_v3 (section 4) as amended by D48 (amendment 1 section 5), in that order. Run only after the seal (T8)
# and all three signatures. Each group can run on its own; the API group needs no local memory, so it can run beside
# the local one. Blocks are saved as they finish and replies are cached, so any group resumes where it stopped.
#
#   bash 30_code/scripts/run_test_v3.sh local    # qwen2.5:14b (primary blocks first, R4-damage seeds 0-4), then
#                                                # llama3.1:8b and qwen2.5:7b (all rungs, E2, R4-damage seed 0)
#   bash 30_code/scripts/run_test_v3.sh api      # gemma-4-26b-a4b-it as qwen2.5:14b; gemini-3.5-flash-lite R0, R2, R4
#   bash 30_code/scripts/run_test_v3.sh model llama3.1:8b no   # one local model alone (each model runs on one machine)
#
# J is not run (D45). R4-damage seeds 1-4 run for the capable models only (D48). D49 (amendment 2): R4n (a clause the
# registry links to nothing reads "no_amendment_recorded") runs intact and at drop25/drop50 beside R4, seed by seed, so
# a run cut at the analysis cutoff still leaves R4 and R4n paired on the same seeds. Order = priority.
#
# REGISTRY=40_data/registries/registry_real_v3.json if the seal wrote one. The run refuses a cases file that does not
# match its .sha256 (--allow-test). Local models are unloaded between models so only one is in memory.
set -euo pipefail
OUT=${OUT:-50_analysis/results/probe_test_v3}  # D49: a repeat run writes elsewhere, with its own cache
CASES=40_data/benchmark/test_cases_v3.json
export PYTHONPATH=30_code/src:30_code/scripts SURYABENCH_LLM_CACHE="$OUT/llm_cache"
REG=(); [ -n "${REGISTRY:-}" ] && REG=(--registry "$REGISTRY")
DAMAGE="drop25 drop50 spurious10"
PROBE=${PROBE:-30_code/scripts/run_verifier_probe.py}  # D49: the Kaggle-hosted wrapper for exploratory models
run() { .venv/bin/python "$PROBE" --allow-test --cases "$CASES" --out "$OUT" ${REG[@]+"${REG[@]}"} \
          --model "$1" --conditions $2 --configs "${@:3}"; }
unload() { curl -s localhost:11434/api/generate -d "{\"model\":\"$1\",\"keep_alive\":0}" >/dev/null || true; }
seed() { for d in $DAMAGE; do echo "validity-regstatus-$d-s$1"; done; for d in drop25 drop50; do echo "validity-regnorec-$d-s$1"; done; }

r5_damage() { run "$1" "S-both S-swap C" $(for d in $DAMAGE; do for k in 0 1 2 3 4; do echo "reg-$d-s$k"; done; done); }

panel() {  # one panel model; capable models run the D48 primary blocks first and all five damage seeds
  local m=$1 capable=$2
  run "$m" "S-both C" validity validity-regstatus      # R2, R4
  [ "$capable" = yes ] && run "$m" "S-both C" validity-regnorec   # R4n (D49)
  run "$m" "S-both S-swap C" reg-real                  # R5 (deterministic)
  if [ "$capable" = yes ]; then
    r5_damage "$m"                                     # R5-damage, all seeds (deterministic; needed for deference)
    for k in 0 1 2 3 4; do run "$m" "S-both C" $(seed $k); done   # R4-damage and R4n-drop, seeds 0-4
  fi
  run "$m" "S-swap C" validity-metaoff                 # R0
  run "$m" "S-swap" validity validity-regstatus        # R1, R4'
  run "$m" "S-both C" validity-amendquote              # R3
  run "$m" "S-both S-swap C" validity-cc               # R1-cc, R2-cc
  run "$m" "S-swap C" validity-cc-metaoff              # R0-cc
  [ "$capable" = yes ] || run "$m" "S-both C" $(seed 0)  # R4-damage, seed 0
}

mkdir -p "$OUT"
case "${1:-}" in
  local)
    panel qwen2.5:14b yes; unload qwen2.5:14b
    for m in llama3.1:8b qwen2.5:7b; do panel "$m" no; unload "$m"; done
    ;;
  api)
    panel gemma-4-26b-a4b-it yes
    run gemini-3.5-flash-lite "S-swap C" validity-metaoff          # R0
    run gemini-3.5-flash-lite "S-both C" validity validity-regstatus  # R2, R4
    ;;
  model)  # one local model on its own, e.g. on another machine (D49): run_test_v3.sh model llama3.1:8b no
    panel "$2" "${3:-no}"; unload "$2"
    ;;
  repeat)  # D49, exploratory: the same model's R2, R4, R4n blocks again on the same machine, fresh cache, other OUT
    [ "$OUT" != 50_analysis/results/probe_test_v3 ] || { echo "repeat needs OUT set to another folder" >&2; exit 2; }
    run "$2" "S-both C" validity validity-regstatus validity-regnorec; unload "$2"
    ;;
  explore)  # D49, exploratory, not preregistered (a model added after filing): main blocks only, own OUT
    [ "$OUT" != 50_analysis/results/probe_test_v3 ] || { echo "explore needs OUT set to another folder" >&2; exit 2; }
    m=$2; seeds=${SEEDS:-"0 1 2"}
    run "$m" "S-both C" validity validity-regstatus validity-regnorec                   # R2, R4, R4n
    for k in $seeds; do run "$m" "S-both C" validity-regstatus-drop50-s$k validity-regnorec-drop50-s$k; done
    run "$m" "S-both C" validity-regstatus-spurious10-s0                               # R4-spurious10
    unload "$m"
    ;;
  *) echo "usage: $0 local|api|model <name> [yes|no]|repeat <name>|explore <name>" >&2; exit 2 ;;
esac
echo "T9 $1 done"
