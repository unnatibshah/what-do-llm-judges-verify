"""Run the controlled-exposure matrix (Paper A v2): conditions x metadata x verifier configurations.

For each (generator model, seed, condition) the Arm 2 agent runs once, always with evidence metadata on, and
is cached; every verifier configuration, at either metadata level, checks that same output (D27), so
contrasts are paired by case. Conditions without
material for a case skip it (logged in each run's exposure_skips.json).

A run is skipped only if the index already holds one with the same configuration AND the same code hash
(``runner.code_hash``): any change to a prompt or scoring module re-runs it. LLM replies are cached on
disk (``<out>/llm_cache``), so an interrupted run resumes without repeating finished calls.

Dev examples (the default split; no test access):
    python 30_code/scripts/run_exposure_matrix.py --model qwen2.5:7b --out 50_analysis/results/exposure_v2_dev
    python 30_code/scripts/run_exposure_matrix.py --model qwen2.5:7b --verifier-model gemma-4-26b-a4b-it \\
        --arms arm3 --out 50_analysis/results/exposure_v2_dev           # cross-model verifier
    python 30_code/scripts/run_exposure_matrix.py --model qwen2.5:7b --variant validity --arms arm3

The test split needs --allow-test, which must not be used before the preregistration is filed.
"""

import argparse
import json
import os

from suryabench.arms.controlled_exposure import CONDITIONS
from suryabench.arms.verify_shared import VARIANTS
from suryabench.eval.runner import VERIFIER_ARMS, BenchmarkRunConfig, BenchmarkRunner, code_hash
from suryabench.paths import CORPORA, DEFAULT_CORPUS, corpus_dir, display, resolve, same_file

ARMS = list(VERIFIER_ARMS)


def slug(model: str) -> str:
    return model.replace("/", "_").replace(":", "_")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="generator model")
    ap.add_argument("--verifier-model", default=None, help="verifier model (default: the generator's)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--cases", default="40_data/benchmark/dev_cases_60.json")
    ap.add_argument("--corpus", default=DEFAULT_CORPUS, choices=sorted(CORPORA),
                    help="r3 for v2 runs (default); r2 only to reproduce retired results")
    ap.add_argument("--conditions", nargs="+", default=CONDITIONS, choices=CONDITIONS)
    ap.add_argument("--meta", nargs="+", default=["off", "on"], choices=["off", "on"])
    ap.add_argument("--arms", nargs="+", default=ARMS, choices=ARMS)
    ap.add_argument("--variant", default="support", choices=VARIANTS)
    ap.add_argument("--taxonomy", action="store_true", help="ablation (D26): add the fault-class list to the prompt")
    ap.add_argument("--recovery", nargs="*", default=[], choices=ARMS, help="arms that also run Arm 5 recovery")
    ap.add_argument("--out", default="50_analysis/results/exposure_v2_dev")
    ap.add_argument("--allow-test", action="store_true")
    ap.add_argument("--max-cases", type=int, default=None)
    args = ap.parse_args()

    out = resolve(args.out)
    os.environ.setdefault("SURYABENCH_LLM_CACHE", str(out / "llm_cache"))
    index_path = out / "exposure_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else []
    chash = code_hash()
    vmodel = args.verifier_model or args.model
    taxonomy = args.taxonomy
    gs = slug(args.model)
    vtag = "" if vmodel == args.model else f"-v-{slug(vmodel)}"
    for meta in args.meta:
        for arm in args.arms:
            for cond in args.conditions:
                key = {"arm": arm, "condition": cond, "model": args.model, "verifier_model": vmodel,
                       "variant": args.variant, "taxonomy": taxonomy, "metadata": meta == "on", "seed": args.seed,
                       "code_hash": chash, "max_cases": args.max_cases, "corpus": args.corpus}
                # index entries written before --corpus existed are r2 runs
                done = [r for r in index if all({"corpus": "r2", **r}.get(k) == v for k, v in key.items()) and same_file(r["cases"], args.cases)
                        and (out / r["run_id"]).exists()]
                if done:
                    print(f"skip {arm} {cond} meta={meta}: {done[0]['run_id']}", flush=True)
                    continue
                run_id = (f"{arm}-{cond}-meta{meta}-{args.variant}{'-tax' if taxonomy else ''}-{gs}{vtag}-"
                          f"{args.seed}-{chash[:8]}" + ("" if args.corpus == "r2" else f"-{args.corpus}") + (f"-n{args.max_cases}" if args.max_cases else ""))
                cfg = BenchmarkRunConfig(
                    run_id=run_id, arm_id=arm, model_id=args.model, verifier_model_id=vmodel, seed=args.seed,
                    prompt_variant=args.variant, taxonomy=taxonomy, metadata=meta == "on",
                    cases_path=resolve(args.cases), corpus_dir=corpus_dir(args.corpus), output_dir=out,
                    allow_test_split=args.allow_test, exposure_condition=cond, recovery=arm in args.recovery,
                    # D27: one generator pass per condition (always metadata on), shared by every verifier config
                    generator_cache=out / "generator_cache" / (f"{gs}-seed{args.seed}-{cond}-{chash[:10]}"
                                                                + ("" if args.corpus == "r2" else f"-{args.corpus}") + ".json"),
                    max_cases=args.max_cases,
                )
                print(f"== {arm} {cond} meta={meta} corpus={args.corpus} gen={args.model} ver={vmodel} {args.variant}", flush=True)
                result = BenchmarkRunner(cfg).run()
                print(f"   {len(result.evaluations)} cases | acc {result.scorecard.accuracy:.3f}", flush=True)
                index.append({**key, "cases": display(args.cases), "run_id": result.run_id, "recovery": cfg.recovery})
                index_path.parent.mkdir(parents=True, exist_ok=True)
                index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
