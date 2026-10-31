"""T3 scorer check (replaces H-16 by a blind second labeller): does the D32 scoring code label verifier replies the way
a reader of the raw reply would?

    build:   python 30_code/scripts/scorer_check.py build --key <hidden key.json>
    compare: python 30_code/scripts/scorer_check.py compare --key <hidden key.json> [--sheet <filled sheet>]

D42: the H-16 check is done by a person (Samruddhi) on 20_method/annotation/scorer_check.csv (blank labels); the
agent labeller's sheet of D40 is kept as scorer_check_agent.csv, an extra check.

``build`` draws 50 fault replies from the dev probe (50_analysis/results/probe_v2, every model and LLM configuration
except 100-neutral; seeded, stratified by the code's label so every label occurs), recovers each reply's raw text from
the reply cache (an invalid reply is never cached: its saved error text is used) and writes the blind sheet
20_method/annotation/scorer_check.csv: the planted clause, its fault class, the reason that counts as right, the ids
that count as naming it, the raw reply, and an empty ``label`` column. The code's labels go to ``--key`` only, kept
away from the labeller. ``compare`` reads the filled sheet and writes
50_analysis/results/scorer_check/scorer_check_report.json (agreement and every disagreement).

Labels (the D32 rule): INVALID (no usable JSON object with a PASS/FLAG verdict); RIGHT_CATCH (a finding names the
planted clause with the right reason); WRONG_REASON (names it, never with the right reason); CANT_CONFIRM (its only
findings say currency_unconfirmed); WRONG_CLAUSE (flags, but never names it); NO_FLAG (PASS with no findings).
"""

import argparse
import csv
import hashlib
import json
import os
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from suryabench.arms import llm_client
from suryabench.arms import verifier_probe as vp
from suryabench.core.enums import FaultClass
from suryabench.eval.failure_classifier import CLASS_REASON
from suryabench.eval.runner import BenchmarkRunConfig, BenchmarkRunner
from suryabench.paths import ANNOTATION_DIR, RESULTS_DIR, corpus_dir, resolve

SHEET = ANNOTATION_DIR / "scorer_check.csv"
REPORT = RESULTS_DIR / "scorer_check" / "scorer_check_report.json"
PROBE = RESULTS_DIR / "probe_v2"
SEED = "SuryaBench-scorer-check-2026-10"
N = 50
QUOTA = {"RIGHT_CATCH": 10, "WRONG_REASON": 12, "WRONG_CLAUSE": 12, "NO_FLAG": 10, "INVALID": 6}
COLS = ["check_id", "planted_clause", "fault_class", "right_reason", "also_names_it", "reply", "label", "note"]


def code_label(r: dict[str, Any]) -> str:
    """The scoring code's label of a saved fault row."""
    if r["invalid"]:
        return "INVALID"
    if r["right"]:
        return "RIGHT_CATCH"
    if r["clause"]:
        return "WRONG_REASON"
    if r.get("cant_confirm") and not r["any"]:
        return "CANT_CONFIRM"
    return "WRONG_CLAUSE" if r["any"] else "NO_FLAG"


def sample() -> list[dict[str, Any]]:
    rows = [r for f in sorted(PROBE.glob("*/blocks/*.json")) for r in json.loads(f.read_text(encoding="utf-8"))["rows"]
            if r["role"] == "fault" and r["config"] in vp.LLM_CONFIGS and r["config"] != "100-neutral"]
    pools: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        pools[code_label(r)].append(r)
    rng = random.Random(SEED)
    chosen = []
    for label, k in QUOTA.items():
        pool = sorted(pools[label], key=lambda r: (r["model"], r["config"], r["item_id"]))
        chosen += rng.sample(pool, min(k, len(pool)))
    rng.shuffle(chosen)
    return chosen[:N]


def raw_replies(rows: list[dict[str, Any]]) -> list[str]:
    """Each row's raw reply text, replayed from the dev reply cache (no model call is allowed)."""
    os.environ["SURYABENCH_LLM_CACHE"] = str(PROBE / "llm_cache")

    def no_call(*_: Any, **__: Any) -> Any:
        raise RuntimeError("a scorer-check reply is not in the cache")

    for name in ("_call_local_ollama", "_call_gemini_api", "_call_groq_api"):
        setattr(llm_client, name, no_call)
    seen: list[str] = []
    parse = llm_client.parse_json_reply

    def record(raw: str) -> dict[str, Any]:
        seen.append(raw)
        return parse(raw)

    llm_client.parse_json_reply = record
    runner = BenchmarkRunner(BenchmarkRunConfig(arm_id="arm3", cases_path=resolve("40_data/benchmark/dev_cases_v2.json"),
                                                corpus_dir=corpus_dir("r3"), metadata=True))
    items, _ = vp.build_items(runner.cases, runner.graph, runner.predicates, runner.retriever)
    by = {i.item_id: i for i in items}
    out = []
    for r in rows:
        if r["invalid"]:
            out.append(str(r.get("invalid_output") or ""))
            continue
        it = by[r["item_id"]]
        ctx = vp.ProbeContext(
            cases={c.case_id: BenchmarkRunner._unlabelled(c) for c in runner.cases},
            texts=vp.evidence_texts([it], runner.graph, runner.retriever), retriever=runner.retriever,
            registries={n: runner._registry(n) for n in ("reg-oracle", "reg-real")},
            labels={d.doc_id: "SRC-" + hashlib.sha256(f"probe|{r['model']}|{d.doc_id}".encode()).hexdigest()[:6].upper()
                    for d in runner.corpus_manifest.documents})
        seen.clear()
        res = vp.verify_item(it, r["config"], r["model"], ctx)
        assert res.verdict != "INVALID" and res.flagged_faults == r["flags"], r["item_id"]  # the very reply scored
        out.append(seen[-1])
    return out


def build(key: Path) -> None:
    rows = sample()
    replies = raw_replies(rows)
    world_chunks = BenchmarkRunner(BenchmarkRunConfig(
        arm_id="arm3", cases_path=resolve("40_data/benchmark/dev_cases_v2.json"), corpus_dir=corpus_dir("r3"),
        metadata=True)).retriever.chunk_clauses
    sheet, hidden = [], []
    for n, (r, raw) in enumerate(zip(rows, replies, strict=True), start=1):
        plant = r["planted"]
        chunks = sorted(c for c, cl in world_chunks.items() if plant in cl)
        also = ("any clause or chunk of document " + plant.split("#")[0]) if r["fault_class"] == "F3" else "; ".join(chunks)
        if not vp.CONFIGS[r["config"]][2]:  # metadata off: the reply saw document ids as opaque source labels
            doc = plant.split("#")[0]
            label = "SRC-" + hashlib.sha256(f"probe|{r['model']}|{doc}".encode()).hexdigest()[:6].upper()
            also += f" (this reply saw document {doc} as {label}, so {label}#... names the same clause)"
        sheet.append([f"SC{n:02d}", plant, r["fault_class"], CLASS_REASON[FaultClass(r["fault_class"])], also, raw, "", ""])
        hidden.append({"check_id": f"SC{n:02d}", "item_id": r["item_id"], "model": r["model"], "config": r["config"],
                       "code_label": code_label(r)})
    with open(SHEET, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLS)
        w.writerows(sheet)
    key.parent.mkdir(parents=True, exist_ok=True)
    key.write_text(json.dumps(hidden, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{SHEET}: {len(sheet)} replies; code labels {dict(Counter(h['code_label'] for h in hidden))} (in the key only)")


def compare(key: Path, sheet: Path = SHEET) -> dict[str, Any]:
    hidden = {h["check_id"]: h for h in json.loads(key.read_text(encoding="utf-8"))}
    with open(sheet, encoding="utf-8", newline="") as f:
        filled = {r["check_id"]: r for r in csv.DictReader(f)}
    assert set(filled) == set(hidden) and all(r["label"].strip() for r in filled.values()), "sheet incomplete"
    pairs = [(hidden[k]["code_label"], filled[k]["label"].strip().upper(), k) for k in sorted(hidden)]
    agree = sum(a == b for a, b, _ in pairs)
    res = {"n": len(pairs), "agree": agree, "agreement": round(agree / len(pairs), 4),
           "confusion": dict(sorted(Counter(f"{a} -> {b}" for a, b, _ in pairs).items())),
           "disagreements": [{**hidden[k], "labeller": b, "note": filled[k]["note"], "planted": filled[k]["planted_clause"],
                              "reply": filled[k]["reply"][:800]} for a, b, k in pairs if a != b]}
    # the agent labeller's report (D40) keeps its name; the human check (D42) gets its own
    report = REPORT if sheet.name == "scorer_check_agent.csv" else REPORT.with_name("scorer_check_report_human.json")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"agreement {agree}/{len(pairs)} = {res['agreement']}")
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["build", "compare"])
    ap.add_argument("--key", type=Path, required=True, help="the hidden code labels (never shown to the labeller)")
    ap.add_argument("--sheet", type=Path, default=SHEET, help="the filled sheet to compare (default: the human one)")
    args = ap.parse_args()
    build(args.key) if args.mode == "build" else compare(args.key, args.sheet)


if __name__ == "__main__":
    main()
