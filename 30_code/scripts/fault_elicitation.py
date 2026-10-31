"""Gate 2 fault elicitation on dev (tasks 1.7 / 1.8 / 1.9).

For each candidate model, runs the two generator arms over the dev split:
- arm2 (tool-augmented agent; the generator the verifier arms check)
- arm1 (single-call RAG; the only arm where the LLM binds input values itself)

Reports, per model and arm: committed / available gold fault events per class and the clause
clusters they span; schema validity; the share of outputs emitting a syntactically well-formed
clause id; the share of cited ids that resolve to a graph node; case accuracy beside Arm 0
(a ceiling: it reproduces every label) and a naive always-approve baseline.

DEV SPLIT ONLY.
"""

import argparse
import json
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from suryabench.eval.runner import BenchmarkRunConfig, BenchmarkRunner
from suryabench.paths import CORPUS_DIR, RESULTS_DIR, resolve

OUT = RESULTS_DIR / "diagnostics"
CLASSES = ["F1", "F2", "F3", "F4-R", "F4-C", "F5", "F6", "F7", "F8", "F9"]
CLAUSE_RE = re.compile(r"^[A-Z]{2}-C\d-\d{3}#cl-[A-Za-z0-9._()-]+$")


def run(model: str, arm: str, cases: str, n: int | None) -> dict[str, Any]:
    runner = BenchmarkRunner(BenchmarkRunConfig(
        arm_id=arm, model_id=model, cases_path=resolve(cases), corpus_dir=CORPUS_DIR,
        output_dir=OUT / "runs", max_cases=n,
    ))
    result = runner.run()
    cases_by = {c.case_id: c for c in runner.cases}
    known = set(runner.graph.nodes)
    available: dict[str, int] = defaultdict(int)
    committed: dict[str, int] = defaultdict(int)
    clusters: dict[str, set[str]] = defaultdict(set)
    detected: dict[str, int] = defaultdict(int)
    for ev in result.evaluations:
        for fe in cases_by[ev.case_id].fault_events:
            k = fe.fault_subtype.value if fe.fault_subtype and fe.fault_class.value == "F4" else fe.fault_class.value
            available[k] += 1
            if ev.fault_event_committed.get(fe.fault_event_id):
                committed[k] += 1
                clusters[k].add(ev.cluster_clause_id)
        for f in ev.detected_faults:  # classifier-detected faults (F1, F4, F7 have no seeded events)
            detected[f.fault_subtype.value if f.fault_subtype else f.fault_class.value] += 1
    schema_ok = well_formed = cited_total = resolving = 0
    for ro in result.raw_outputs:
        out = ro.get("output", {})
        raw = out.get("raw_output") or {}
        schema_ok += isinstance(raw, dict) and "error" not in raw and "decision" in raw
        cites = [str(c).strip() for c in out.get("cited_rules") or []]
        well_formed += any(CLAUSE_RE.match(c) for c in cites)
        cited_total += len(cites)
        resolving += sum(c in known for c in cites)
    n_cases = len(result.evaluations)
    return {
        "model": model, "arm": arm, "n": n_cases, "run_id": result.run_id,
        "correct": sum(e.is_correct for e in result.evaluations),
        "acc_ci": result.scorecard.accuracy_ci.formatted if result.scorecard.accuracy_ci else None,
        "available": dict(available), "committed": dict(committed),
        "clusters": {k: len(v) for k, v in clusters.items()}, "detected": dict(detected),
        "schema_ok": schema_ok, "well_formed": well_formed, "cited_total": cited_total, "resolving": resolving,
        "tokens": sum((ro.get("output") or {}).get("prompt_tokens", 0) + (ro.get("output") or {}).get(
            "completion_tokens", 0) for ro in result.raw_outputs),
    }


def cell(r: dict[str, Any], cls: str) -> str:
    avail = r["available"].get(cls, 0)
    if not avail:
        return f"— ({r['detected'].get(cls, 0)} det.)" if r["detected"].get(cls) else "—"
    return f"{r['committed'].get(cls, 0)}/{avail} ({r['clusters'].get(cls, 0)}c)"


def pct(k: int, n: int) -> str:
    return f"{k}/{n} ({100.0 * k / n:.1f}%)" if n else "0/0"


def gate2(r: dict[str, Any], arm0_acc: float, naive_acc: float) -> list[str]:
    fails = []
    acc = r["correct"] / r["n"]
    if acc <= arm0_acc:
        fails.append(f"accuracy {acc:.1%} not above Arm 0 ({arm0_acc:.1%}); Arm 0 is a label ceiling, "
                     f"so this criterion is unattainable by construction (naive baseline {naive_acc:.1%})")
    for cls in ("F5", "F6"):
        if r["committed"].get(cls, 0) < 5 or r["clusters"].get(cls, 0) < 3:
            fails.append(f"{cls}: {r['committed'].get(cls, 0)} committed over {r['clusters'].get(cls, 0)} "
                         "clusters (need >=5 over >=3)")
    if r["schema_ok"] / r["n"] < 0.80:
        fails.append(f"schema-valid {pct(r['schema_ok'], r['n'])} (need >=80%)")
    return fails


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="40_data/benchmark/dev_cases_60.json")
    ap.add_argument("--n", type=int, default=None)
    ap.add_argument("--models", nargs="+", default=["qwen2.5:7b", "qwen/qwen3.8-27b", "openai/gpt-oss-120b"])
    ap.add_argument("--out", default="FAULT_ELICITATION")
    args = ap.parse_args()
    if "test_cases" in args.cases:
        raise SystemExit("Refusing to run elicitation against a test split. Dev only.")

    base = run("none", "arm0", args.cases, args.n)
    runner = BenchmarkRunner(BenchmarkRunConfig(arm_id="arm0", cases_path=resolve(args.cases),
                                                corpus_dir=CORPUS_DIR, max_cases=args.n))
    naive = sum(c.expected_decision.value == "ANSWER" and c.expected_answer.blocking_stage is None
                for c in runner.cases)
    arm0_acc, naive_acc = base["correct"] / base["n"], naive / base["n"]

    def one_model(m: str) -> list[dict[str, Any]]:
        rows = []
        for arm in ("arm2", "arm1"):
            try:
                rows.append(run(m, arm, args.cases, args.n))
            except Exception as e:  # keep partial results; failures are retained under 50_analysis/results/failed/
                rows.append({"model": m, "arm": arm, "error": f"{type(e).__name__}: {e}"})
        return rows

    with ThreadPoolExecutor(max_workers=len(args.models)) as pool:  # one worker per provider/model
        results = [r for rows in pool.map(one_model, args.models) for r in rows]
    ok = [r for r in results if "error" not in r]

    n = base["n"]
    lines = [
        f"# Gate 2 — fault elicitation on dev ({args.out})", "",
        f"- **Cases:** `{args.cases}`, n = {n} (dev split only), seed 42, temperature 0.0",
        f"- **Arm 0 (hand-coded rules, facsimiles only):** {pct(base['correct'], n)}. Arm 0 reproduces "
        "the rule-derived labels, so it is a ceiling, not a weak baseline.",
        f"- **Naive always-approve baseline:** {pct(naive, n)}", "",
        "Cells: **committed / available** seeded fault events (clause clusters spanned). Classes with no "
        "seeded events show classifier-detected counts instead (`det.`).", "",
        "| Model | Arm | Case acc. | " + " | ".join(CLASSES) + " |",
        "|---|---|---|" + "---|" * len(CLASSES),
    ]
    for r in ok:
        lines.append(f"| `{r['model']}` | {r['arm']} | {pct(r['correct'], r['n'])} | "
                     + " | ".join(cell(r, c) for c in CLASSES) + " |")
    lines += ["", "## Output contract", "",
              "| Model | Arm | Schema-valid | >=1 well-formed clause id | Cited ids resolving in graph | Tokens |",
              "|---|---|---|---|---|---|"]
    for r in ok:
        lines.append(f"| `{r['model']}` | {r['arm']} | {pct(r['schema_ok'], r['n'])} | "
                     f"{pct(r['well_formed'], r['n'])} | {pct(r['resolving'], r['cited_total'])} | {r['tokens']:,} |")
    lines += ["", "## Gate 2 eligibility (evaluated on arm2, the generator the verifier arms check)", ""]
    for r in [r for r in ok if r["arm"] == "arm2"]:
        fails = gate2(r, arm0_acc, naive_acc)
        lines.append(f"- **`{r['model']}`** — {'ELIGIBLE' if not fails else 'NOT ELIGIBLE'}")
        lines += [f"  - {f}" for f in fails]
    for r in results:
        if "error" in r:
            lines.append(f"- **`{r['model']}` {r['arm']}** — RUN FAILED: {r['error'][:300]}")
    lines += ["", "## Run ids", ""] + [f"- `{r['model']}` {r['arm']} → `{r['run_id']}`" for r in ok]
    lines.append(f"- arm0 → `{base['run_id']}`")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{args.out}.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    (OUT / f"{args.out.lower()}.json").write_text(json.dumps({"arm0": base, "naive_correct": naive,
                                                             "results": results}, indent=2, default=str), encoding="utf-8", newline="\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
