"""Run the experimental matrix (task 2.3) on the sealed test split.

Arms: arm0, arm1, arm2, arm2o, and every verifier arm in ``runner.VERIFIER_ARMS`` (110/111 retired
2026-10-01; the registries replace them). For each
(model, seed), Arm 2 is generated once and cached; every verifier arm checks that same output,
so the verifier comparisons are paired by case.

Fail-fast (task 2.4): as soon as arm3 completes, if its verifier sensitivity is 0.0 with a
non-empty committed fault-event denominator, the run halts before the remaining verifier arms.

Usage:
    python 30_code/scripts/run_matrix.py --model qwen/qwen3.8-27b --seeds 42 43 44 --allow-test
"""

import argparse
import json

from suryabench.eval.runner import VERIFIER_ARMS, BenchmarkRunConfig, BenchmarkRunner
from suryabench.paths import CORPORA, corpus_dir, display, resolve, same_file

ARMS = ["arm0", "arm2", "arm3", "arm1", "arm2o", *[a for a in VERIFIER_ARMS if a != "arm3"]]
CUTOFFS = {"qwen2.5:7b": "UNKNOWN (released 2024-09)", "openai/gpt-oss-120b": "2024-06 (model card)",
           "qwen/qwen3.8-27b": "UNKNOWN", "llama3.1:8b": "2023-12 (model card)"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--seeds", nargs="+", type=int, default=[42])
    ap.add_argument("--cases", default="40_data/benchmark/test_cases_100.json")
    # The natural-retrieval matrix on test_cases_100 is retired (D1): it defaults to r2 to reproduce it.
    ap.add_argument("--corpus", default="r2", choices=sorted(CORPORA))
    ap.add_argument("--arms", nargs="+", default=ARMS)
    ap.add_argument("--out", default="50_analysis/results/runs")
    ap.add_argument("--allow-test", action="store_true")
    ap.add_argument("--max-cases", type=int, default=None)
    ap.add_argument("--no-fail-fast", action="store_true", help="pipeline tests only (e.g. the mock model)")
    args = ap.parse_args()

    out = resolve(args.out)
    index_path = out / "matrix_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else []
    slug = args.model.replace("/", "_").replace(":", "_")
    for seed in args.seeds:
        cache = out / "generator_cache" / f"{slug}-seed{seed}{'' if args.corpus == 'r2' else '-' + args.corpus}.json"
        for arm in args.arms:
            model = "none" if arm == "arm0" else args.model
            if arm == "arm0" and seed != args.seeds[0]:
                continue  # deterministic, no model: once
            done = [r for r in index if r["arm"] == arm and r["model"] == model and r["seed"] == seed
                    and r.get("corpus", "r2") == args.corpus and same_file(r["cases"], args.cases)]
            if done:
                print(f"skip {arm} {model} seed {seed}: {done[0]['run_id']}")
                continue
            cfg = BenchmarkRunConfig(
                arm_id=arm, model_id=model, seed=seed, cases_path=resolve(args.cases), corpus_dir=corpus_dir(args.corpus),
                output_dir=out, allow_test_split=args.allow_test,
                model_training_cutoff=CUTOFFS.get(model), generator_cache=cache, max_cases=args.max_cases,
            )
            print(f"== {arm} {model} seed {seed}", flush=True)
            result = BenchmarkRunner(cfg).run()
            sc = result.scorecard
            sens = sc.verifier_overall_sensitivity_ci.formatted if sc.verifier_overall_sensitivity_ci else "n/a"
            print(f"   acc {sc.accuracy_ci.formatted if sc.accuracy_ci else sc.accuracy} | sens {sens}", flush=True)
            index.append({"arm": arm, "model": model, "seed": seed, "corpus": args.corpus, "cases": display(args.cases), "run_id": result.run_id})
            index_path.parent.mkdir(parents=True, exist_ok=True)
            index_path.write_text(json.dumps(index, indent=2), encoding="utf-8", newline="\n")
            if arm == "arm3" and not args.no_fail_fast:
                ci = sc.verifier_overall_sensitivity_ci
                if ci is not None and ci.total_opportunities > 0 and ci.event_count == 0:
                    raise SystemExit(
                        f"FAIL-FAST: arm3 sensitivity 0/{ci.total_opportunities} with a non-empty denominator "
                        f"({args.model}, seed {seed}); halting before the remaining verifier arms.")


if __name__ == "__main__":
    main()
