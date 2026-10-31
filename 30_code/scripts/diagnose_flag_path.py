"""STEP 1 diagnostic: is the verifier emitting no flags, or flags that fail to parse?

Runs arm3 (I=000) on the first N dev cases, persists every verifier completion
string *before any parsing*, and classifies the flag path failure mode.

DEV SPLIT ONLY. Never point this at benchmark/test_cases_*.json.
"""

import argparse
import json
from collections import Counter

from suryabench.arms import llm_client, verify_shared
from suryabench.eval.runner import BenchmarkRunConfig, BenchmarkRunner
from suryabench.paths import CORPUS_DIR, RESULTS_DIR, resolve

RAW_DIR = RESULTS_DIR / "diagnostics" / "verifier_raw"
OUT_MD = RESULTS_DIR / "diagnostics" / "FLAG_PATH_DIAGNOSIS.md"

# Captured in verifier-call order; arm3 issues exactly one verifier call per case.
_raws: list[str] = []


def _wrapped_call(*args, **kwargs):
    llm_client.LAST_RAW = None
    out = llm_client.call_llm_json(*args, **kwargs)
    _raws.append(llm_client.LAST_RAW if llm_client.LAST_RAW is not None else "")
    return out


def classify_raw(raw: str) -> tuple[str, dict | None]:
    """Return (bucket, parsed_json_or_None) for one raw verifier completion."""
    if not raw or not raw.strip():
        return "empty", None
    if "{" not in raw:
        return "prose_no_json", None
    try:
        data = json.loads(raw)
    except Exception:
        return "json_parse_failed", None
    if not isinstance(data, dict):
        return "schema_failed", None
    if "verdict" not in data or "flagged_faults" not in data:
        return "schema_failed", data
    flags = data.get("flagged_faults")
    if not isinstance(flags, list):
        return "schema_failed", data
    return ("valid_with_flags" if flags else "valid_empty_flags"), data


def flag_matches_event(flag: str, fe) -> bool:
    """Mirror of the matching rule in FailureClassifier.classify_case."""
    return (
        fe.fault_event_id in flag
        or fe.fault_class.value in flag
        or any(ev in flag for ev in fe.gold_evidence)
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="40_data/benchmark/dev_cases_60.json")
    ap.add_argument("--model", default="qwen2.5:7b")
    ap.add_argument("--n", type=int, default=20)
    args = ap.parse_args()

    if "test_cases" in args.cases:
        raise SystemExit("Refusing to diagnose against a test split. Dev only.")

    verify_shared.call_llm_json = _wrapped_call

    cfg = BenchmarkRunConfig(
        arm_id="arm3",
        model_id=args.model,
        cases_path=resolve(args.cases),
        corpus_dir=CORPUS_DIR,
        output_dir=RESULTS_DIR / "diagnostics" / "runs",
        max_cases=args.n,
    )
    runner = BenchmarkRunner(cfg)
    result = runner.run()

    cases = {c.case_id: c for c in runner.cases}
    order = [r["case_id"] for r in result.raw_outputs]
    assert len(_raws) == len(order), f"raw capture desync: {len(_raws)} vs {len(order)}"

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    buckets: Counter[str] = Counter()
    unmatched_rows: list[tuple[str, str, str]] = []
    total_flags = 0
    matched_flags = 0

    for case_id, raw, rawout in zip(order, _raws, result.raw_outputs, strict=True):
        (RAW_DIR / f"{case_id}.txt").write_text(raw, encoding="utf-8", newline="\n")
        bucket, _ = classify_raw(raw)
        buckets[bucket] += 1

        flags = rawout["verifier"]["flagged_faults"] or []
        fes = cases[case_id].fault_events
        for flag in flags:
            total_flags += 1
            hit = [fe for fe in fes if flag_matches_event(str(flag), fe)]
            if hit:
                matched_flags += 1
            else:
                expected = "; ".join(
                    f"{fe.fault_event_id} ({fe.fault_class.value}"
                    + (f"/{fe.fault_subtype.value}" if fe.fault_subtype else "")
                    + f", gold_evidence={fe.gold_evidence})"
                    for fe in fes
                ) or "(case has no gold fault events)"
                unmatched_rows.append((case_id, str(flag), expected))

    # Commitment opportunities: a flag can only count toward sensitivity if the
    # generator actually committed the seeded fault.
    gold_events = sum(len(cases[cid].fault_events) for cid in order)
    committed = 0
    for e in result.evaluations:
        committed += sum(1 for v in e.fault_event_committed.values() if v)

    n = len(order)
    parse_fail = buckets["empty"] + buckets["prose_no_json"] + buckets["json_parse_failed"]
    schema_fail = buckets["schema_failed"]
    parse_or_schema_pct = 100.0 * (parse_fail + schema_fail) / n if n else 0.0

    if parse_or_schema_pct >= 25.0:
        verdict = (
            "**OUTPUT-CONTRACT BUG (verifier side).** "
            f"{parse_fail + schema_fail}/{n} ({parse_or_schema_pct:.1f}%) of verifier completions "
            "failed to parse or failed schema validation. Per Gate 1 this is a contract bug, "
            "not a model limitation: fix the verifier prompt and parser, re-run this step, "
            "do not proceed until under 10%."
        )
    elif committed == 0:
        verdict = (
            "**DENOMINATOR COLLAPSE — sensitivity is 0/0, not 0/n.** "
            f"The verifier parsed cleanly ({100 - parse_or_schema_pct:.1f}% valid) and emitted "
            f"{total_flags} flags across {n} cases, so it is neither silent nor unparseable. "
            f"But the generator committed **0 of the {gold_events} gold fault events** in these "
            "cases, so there were no detection opportunities at all. Sensitivity has no "
            "denominator; it cannot be 'low' or 'high', it is undefined. The cause lies "
            "upstream of the verifier."
        )
    elif total_flags > 0 and matched_flags == 0:
        verdict = (
            "**MATCHING BUG.** "
            f"{total_flags} flags were emitted across {n} cases, {committed} fault events were "
            "committed, and no flag matched any gold fault event. Per Gate 1 the matching logic "
            "between `flagged_faults` and `fault_event_id` is broken: fix it and re-run."
        )
    elif buckets["valid_empty_flags"] > n / 2:
        verdict = (
            "**VERIFIER GENUINELY SILENT.** "
            f"{buckets['valid_empty_flags']}/{n} completions were valid JSON with an empty "
            "`flagged_faults` list, and parse/schema failures are below the Gate 1 threshold. "
            "Per Gate 1, proceed to Step 2; the cause is generator or verifier capability."
        )
    else:
        verdict = (
            "**FLAG PATH FUNCTIONAL.** "
            f"{total_flags} flags emitted, {matched_flags} matched a gold fault event, "
            f"{committed}/{gold_events} gold fault events committed by the generator. "
            "The flag path is carrying signal; interpret sensitivity on its merits."
        )

    lines = [
        "# Step 1 — Flag-path diagnosis (arm3, I=000)",
        "",
        f"- **Model:** `{args.model}`",
        f"- **Cases:** `{args.cases}`, first {n} (dev split only)",
        "- **Raw completions:** `50_analysis/results/diagnostics/verifier_raw/<case_id>.txt`, "
        "written before any parsing",
        "",
        "## Flag-path census",
        "",
        "| Quantity | Count / % |",
        "|---|---|",
        f"| Verifier returned empty or whitespace output | {buckets['empty']}/{n} ({100*buckets['empty']/n:.1f}%) |",
        f"| Verifier returned prose with no JSON block | {buckets['prose_no_json']}/{n} ({100*buckets['prose_no_json']/n:.1f}%) |",
        f"| Verifier returned JSON that failed to parse | {buckets['json_parse_failed']}/{n} ({100*buckets['json_parse_failed']/n:.1f}%) |",
        f"| Verifier returned JSON that failed schema validation | {schema_fail}/{n} ({100*schema_fail/n:.1f}%) |",
        f"| Verifier returned valid JSON with `flagged_faults: []` | {buckets['valid_empty_flags']}/{n} ({100*buckets['valid_empty_flags']/n:.1f}%) |",
        f"| Verifier returned valid JSON with >=1 flag | {buckets['valid_with_flags']}/{n} ({100*buckets['valid_with_flags']/n:.1f}%) |",
        f"| Flags emitted that the classifier matched to no fault event | {len(unmatched_rows)}/{total_flags} |",
        "",
        "## Detection opportunities",
        "",
        "| Quantity | Count |",
        "|---|---|",
        f"| Gold fault events available across the {n} cases | {gold_events} |",
        f"| Gold fault events the generator actually committed | {committed} |",
        f"| Sensitivity denominator (committed events) | {committed} |",
        "",
        f"Total flags emitted: {total_flags}. Matched to a gold fault event: {matched_flags}.",
        "",
        "## Verdict",
        "",
        verdict,
        "",
        "## Unmatched flags",
        "",
    ]

    if unmatched_rows:
        lines += [
            "| Case | Flag emitted | Gold fault events available in that case |",
            "|---|---|---|",
        ]
        lines += [f"| {c} | `{f}` | {e} |" for c, f, e in unmatched_rows]
    else:
        lines.append("None — every emitted flag matched a gold fault event.")
    lines.append("")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("\n".join(lines[:30]))
    print(f"\nWrote {OUT_MD} and {n} raw completions to {RAW_DIR}")


if __name__ == "__main__":
    main()
