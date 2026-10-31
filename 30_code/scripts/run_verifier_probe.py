"""D33 verifier probe on dev: fixed fault/control answers, every verifier configuration, one verifier model per call.

Blocks run in priority order (support and validity on S-both and C first) and each (configuration, condition)
block is saved, and the summary recomputed, as soon as it finishes, so numbers stream. A block saved with the
same code hash is skipped; LLM replies are cached (``SURYABENCH_LLM_CACHE``, default ``<out>/llm_cache``).
Every verifier call is capped at 1024 output tokens (``SURYABENCH_MAX_OUTPUT_TOKENS``, D33), reflect at 2048 (D35).
A saved block made at another cap is re-run.

    python 30_code/scripts/run_verifier_probe.py --model qwen2.5:7b --out 50_analysis/results/<new folder>
    python 30_code/scripts/run_verifier_probe.py --model gemma-4-26b-a4b-it --workers 4 --out 50_analysis/results/<new folder>
    python 30_code/scripts/run_verifier_probe.py --model llama3.1:8b --out 50_analysis/results/<new folder> --configs support validity support-metaoff \\
        validity-metaoff reg-real-llm

The cases file must not be a test split (core/guard.py TestSplitGuard), unless --allow-test is given; then the
guard authorises the read, and --out must not be the dev results folder. Every block records its manifest (D37, T2):
model and version, configuration, rung, condition, prompt hash, code hash, output cap, temperature, seed, dataset
fingerprint, timestamp, and whether the test split was read.
"""

import argparse
import hashlib
import inspect
import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

from suryabench.analysis import probe
from suryabench.arms import llm_client
from suryabench.arms import verifier_probe as vp
from suryabench.core.guard import verify_fingerprint
from suryabench.corpus.manifest import compute_file_sha256
from suryabench.eval.runner import BenchmarkRunConfig, BenchmarkRunner, code_hash
from suryabench.paths import corpus_dir, resolve, same_file

os.environ.setdefault("SURYABENCH_MAX_OUTPUT_TOKENS", "1024")
CAPS = {"reflect": "2048"}  # D35: the two-pass critique needs room; every other configuration keeps the D33 cap
DEV_OUT = "50_analysis/results/probe_v2"
TEMPERATURE = 0.0  # every verifier call (verify_shared.llm_verdict, verify_reflect)


def ollama_digest(model: str) -> str | None:
    """The local model's Ollama digest (its exact weights), or None for an API model or when Ollama is down."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5) as resp:
            tags = json.loads(resp.read().decode("utf-8"))["models"]
    except (OSError, ValueError, KeyError):
        return None
    return next((m.get("digest") for m in tags if m.get("name") == model), None)


def block_manifest(config: str, cond: str, model: str, rows: list[dict[str, Any]], **fields: Any) -> dict[str, Any]:
    """The provenance a saved block carries. ``prompt_hash``: sha256 over its rows' prompt hashes in row order
    (None for a deterministic registry block, which sends no prompt)."""
    hashes = [r["prompt_sha256"] for r in rows if r.get("prompt_sha256")]
    return {"model": model, "model_version": llm_client.MODEL_INFO.get(model, {}).get("model_version"),
            "config": config, "rung": vp.rung(config, cond), "condition": cond,
            "prompt_hash": hashlib.sha256("".join(hashes).encode()).hexdigest() if hashes else None,
            "temperature": TEMPERATURE, "seed": llm_client.RUN_SEED,
            "timestamp": datetime.now(UTC).isoformat(timespec="seconds"), **fields}


def blocks(configs: list[str], conditions: list[str]) -> list[tuple[str, str]]:
    """Priority order: support and validity on S-both and C, then their other conditions, then the rest."""
    first = [(c, k) for c in ("support", "validity") for k in ("S-both", "C")]
    second = [(c, k) for c in ("support", "validity") for k in ("S-swap", "J", "A")]
    rest = [(c, k) for c in vp.CONFIGS for k in ("S-both", "C", "S-swap", "J", "A")]
    order = list(dict.fromkeys(first + second + rest))
    return [(c, k) for c, k in order if c in configs and k in conditions]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="verifier model")
    ap.add_argument("--workers", type=int, default=None, help="default 4 for API models, 1 for local Ollama")
    ap.add_argument("--configs", nargs="+", default=list(vp.CONFIGS), choices=list(vp.CONFIGS))
    ap.add_argument("--conditions", nargs="+", default=list(vp.CONDITIONS), choices=list(vp.CONDITIONS))
    ap.add_argument("--cases", default="40_data/benchmark/dev_cases_v2.json")
    ap.add_argument("--out", required=True, help="a new results folder; saved results are immutable")
    ap.add_argument("--max-items", type=int, default=None, help="per block (smoke runs)")
    ap.add_argument("--allow-test", action="store_true", help="read a test split (the final run only, after sealing)")
    ap.add_argument("--registry", default=None, help="reg-real registry file (default by corpus; T8 may seal a v3)")
    args = ap.parse_args()

    out = resolve(args.out)
    if args.allow_test and same_file(out, resolve(DEV_OUT)):
        ap.error("--allow-test writes test results; give an --out other than the dev folder")
    if args.allow_test:
        verify_fingerprint(resolve(args.cases))  # the sealed file, byte for byte, or no run
    os.environ.setdefault("SURYABENCH_LLM_CACHE", str(out / "llm_cache"))
    api = args.model.startswith(("gemini-", "gemma-"))
    workers = args.workers or (4 if api else 1)
    runner = BenchmarkRunner(BenchmarkRunConfig(arm_id="arm3", cases_path=resolve(args.cases), corpus_dir=corpus_dir("r3"),
                                                metadata=True, allow_test_split=args.allow_test,
                                                registry_path=resolve(args.registry) if args.registry else None))
    dataset = compute_file_sha256(resolve(args.cases))
    digest = ollama_digest(args.model)
    items, skips = vp.build_items(runner.cases, runner.graph, runner.predicates, runner.retriever)
    texts = vp.evidence_texts(items, runner.graph, runner.retriever)
    ctx = vp.ProbeContext(
        cases={c.case_id: BenchmarkRunner._unlabelled(c) for c in runner.cases}, texts=texts, retriever=runner.retriever,
        registries={**{n: runner._registry(n) for n in ("reg-oracle", "reg-real")},
                    **vp.damaged_registries(runner._registry("reg-real"))},
        labels={d.doc_id: "SRC-" + hashlib.sha256(f"probe|{args.model}|{d.doc_id}".encode()).hexdigest()[:6].upper()
                for d in runner.corpus_manifest.documents})
    runner.retriever.meta = True  # 100-neutral renders its own retrieval at metadata on; nothing toggles it below
    chash = hashlib.sha256((code_hash() + inspect.getsource(vp)).encode()).hexdigest()[:12]
    mdir = out / args.model.replace("/", "_").replace(":", "_")
    (mdir / "blocks").mkdir(parents=True, exist_ok=True)
    (out / "items.json").write_text(json.dumps({"n_items": len(items), "skips": skips, "items": [
        {"item_id": i.item_id, "role": i.role, "condition": i.condition, "cluster": i.cluster, "planted": i.planted,
         "outcome_changing": i.outcome_changing, "decision": i.answer.decision, "blocking_stage": i.answer.blocking_stage,
         "cited": i.answer.cited_rules, "root_cause": i.answer.root_cause, "evidence_ids": i.evidence_ids}
        for i in items]}, indent=1) + "\n", encoding="utf-8", newline="\n")
    base_cap = os.environ["SURYABENCH_MAX_OUTPUT_TOKENS"]
    tfile = mdir / "timings.json"
    timings = json.loads(tfile.read_text(encoding="utf-8")) if tfile.exists() else {}

    for config, cond in blocks(args.configs, args.conditions):
        bfile = mdir / "blocks" / f"{config}__{cond}.json"
        cap = os.environ["SURYABENCH_MAX_OUTPUT_TOKENS"] = CAPS.get(config, base_cap)
        saved = json.loads(bfile.read_text(encoding="utf-8")) if bfile.exists() else {}
        if saved.get("code_hash") == chash and saved.get("max_output_tokens") == cap:
            print(f"skip {config} {cond}", flush=True)
            continue
        todo = [i for i in items if i.condition == cond][: args.max_items]
        t0 = time.time()
        with ThreadPoolExecutor(workers if config in vp.LLM_CONFIGS else 1) as pool:
            results = list(pool.map(lambda it, c=config: vp.verify_item(it, c, args.model, ctx), todo))
        secs = round(time.time() - t0, 1)
        rows = [vp.record(it, config, args.model, res, runner.classifier) for it, res in zip(todo, results, strict=True)]
        calls = len(todo) * (2 if config == "reflect" else 1) if config in vp.LLM_CONFIGS else 0
        # the first measured run only: a re-run after a code change may replay the cache
        timings.setdefault(f"{config}__{cond}", {"items": len(todo), "calls": calls, "seconds": secs, "workers": workers,
                                                 "calls_per_min": round(calls / secs * 60, 2) if calls and secs else None})
        bfile.write_text(json.dumps({"code_hash": chash, "max_output_tokens": cap,
                                     **block_manifest(config, cond, args.model, rows, dataset_sha256=dataset,
                                                      cases=args.cases, allow_test=args.allow_test,
                                                      max_items=args.max_items, model_digest=digest),
                                     "rows": rows},
                                    indent=1) + "\n", encoding="utf-8", newline="\n")
        tfile.write_text(json.dumps(timings, indent=2) + "\n", encoding="utf-8", newline="\n")
        probe.write_summary(out)
        inval = sum(r["invalid"] for r in rows)
        print(f"{config} {cond}: {len(rows)} items {secs}s right {sum(r['right'] for r in rows if r['role'] == 'fault')}"
              f" any-ctrl {sum(r['any'] for r in rows if r['role'] != 'fault')} invalid {inval}", flush=True)


if __name__ == "__main__":
    main()
