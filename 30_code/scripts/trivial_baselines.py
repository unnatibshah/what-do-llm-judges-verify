"""Trivial baselines and leakage probes for a case file (D13). No model is run.

Baselines (3-way gold: approve / reject / abstain, from expected_decision and blocking_stage):
  always-approve, majority class, and the capacity heuristic (abstain if the facsimiles show an
  unreadable field; reject if proposed capacity > sanctioned load; else approve).
Leakage probes: leave-one-out lookup classifiers that see only id / order features (slot parsed
from a v1 id, file position, id hash bucket), the best single magnitude threshold for F5, and (N19,
2026-10-01) a bag-of-lines probe per probed class: does a facsimile line (numbers masked) that other cases
of that class carry give the class away? At chance means the feature carries no label information.

Usage: python trivial_baselines.py [out_dir]   (default 50_analysis/results/baselines_v2)
"""

import json
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from suryabench.paths import BENCHMARK_DIR, RESULTS_DIR

FILES = ["dev_cases_60.json", "dev_cases_v2.json"]
MISSING = re.compile(r"UNREADABLE|NOT RECORDED|CORRUPTED", re.I)
KW = r"([\d.]+)\s*kWp?"


def gold(c: dict[str, Any]) -> str:
    if c["expected_decision"] == "ABSTAIN":
        return "abstain"
    return "reject" if c["expected_answer"]["blocking_stage"] else "approve"


def capacity_heuristic(c: dict[str, Any]) -> str:
    text = "\n".join(c["inputs"].values())
    if MISSING.search(text):
        return "abstain"
    sl = re.search(r"Sanctioned Load / Contract Demand: " + KW, c["inputs"]["bill"])
    pc = re.search(r"Proposed DC Capacity: " + KW, c["inputs"]["proposal"])
    if sl and pc and float(pc.group(1)) > float(sl.group(1)):
        return "reject"
    return "approve"


def acc(pred: list[str], y: list[str]) -> float:
    return round(sum(p == t for p, t in zip(pred, y, strict=True)) / len(y), 4)


def loo_lookup(keys: list[Any], y: list[str]) -> float:
    """Leave-one-out accuracy of predicting the label by the majority among other cases with the same key."""
    by: dict[Any, Counter[str]] = defaultdict(Counter)
    for k, t in zip(keys, y, strict=True):
        by[k][t] += 1
    glob = Counter(y)
    hits = 0
    for k, t in zip(keys, y, strict=True):
        votes = by[k] - Counter({t: 1}) if by[k][t] else by[k]
        votes = votes if sum(votes.values()) else glob - Counter({t: 1})
        hits += votes.most_common(1)[0][0] == t
    return round(hits / len(y), 4)


def best_threshold(x: list[float], is_pos: list[bool]) -> float:
    """Accuracy of the best single 'x > t' rule for the positive class (in-sample, so optimistic)."""
    return round(max(sum((v > t) == p for v, p in zip(x, is_pos, strict=True)) for t in [0.0, *x]) / len(x), 4)


def line_keys(c: dict[str, Any]) -> set[str]:
    """Facsimile lines with digits masked: the surface a lexical shortcut could use."""
    return {re.sub(r"\d+(\.\d+)?", "#", ln.strip()) for v in c["inputs"].values() for ln in v.splitlines() if ln.strip()}


def bag_of_lines_probe(cases: list[dict[str, Any]], cls: str) -> dict[str, float]:
    """Leave-one-out: predict ``cls`` when some line of the case is, among the other cases carrying it (at least
    two), mostly of class ``cls``. Compared with always predicting the majority (not ``cls``)."""
    keys = [line_keys(c) for c in cases]
    pos = [c["failure_class_probed"] == cls for c in cases]
    seen: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # line -> [cases, cases of cls]
    for ks, p in zip(keys, pos, strict=True):
        for k in ks:
            seen[k][0] += 1
            seen[k][1] += p
    hits = 0
    for ks, p in zip(keys, pos, strict=True):
        pred = any(seen[k][0] - 1 >= 2 and (seen[k][1] - p) / (seen[k][0] - 1) > 0.5 for k in ks)
        hits += pred == p
    return {"accuracy": round(hits / len(cases), 4), "majority": round(1 - sum(pos) / len(pos), 4)}


def analyse(cases: list[dict[str, Any]]) -> dict[str, Any]:
    y = [gold(c) for c in cases]
    probed = [c["failure_class_probed"] for c in cases]
    trap = ["clean" if p == "CLEAN" else "trap" for p in probed]
    maj = Counter(y).most_common(1)[0][0]
    heur = [capacity_heuristic(c) for c in cases]
    non_clean = [i for i, p in enumerate(probed) if p != "CLEAN"]
    parsed = [re.match(r"(.+)-(\d{3})$", c["case_id"]) for c in cases]
    slot = [int(m.group(2)) if m else None for m in parsed]
    id_bucket = [int(re.sub(r"\D", "", c["case_id"]) or 0) % 8 for c in cases]
    f5 = [p == "F5" for p in probed]
    kw = [float(c["facts"]["proposed_capacity_kw"]) for c in cases]
    probes: dict[str, Callable[[list[str]], float]] = {
        "slot number parsed from id (v1)": lambda t: loo_lookup(slot, t),
        "file position (mod 20)": lambda t: loo_lookup([i % 20 for i in range(len(cases))], t),
        "id digits bucket (mod 8)": lambda t: loo_lookup(id_bucket, t),
    }
    return {
        "n": len(cases),
        "gold_counts": dict(Counter(y)),
        "accuracy": {
            "always_approve": acc(["approve"] * len(y), y),
            f"majority_class({maj})": acc([maj] * len(y), y),
            "capacity_heuristic": acc(heur, y),
            "capacity_heuristic_on_non_clean": acc([heur[i] for i in non_clean], [y[i] for i in non_clean]),
            "capacity_heuristic_on_trap_slots_F5": acc([h for h, p in zip(heur, probed, strict=True) if p == "F5"],
                                                       [t for t, p in zip(y, probed, strict=True) if p == "F5"]),
        },
        "heuristic_by_probed_class": {
            p: acc([h for h, q in zip(heur, probed, strict=True) if q == p],
                   [t for t, q in zip(y, probed, strict=True) if q == p]) for p in sorted(set(probed))},
        "leakage_probes": {
            name: {"decision_label": f(y), "decision_majority": round(Counter(y).most_common(1)[0][1] / len(y), 4),
                   "clean_vs_trap": f(trap), "clean_vs_trap_majority": round(Counter(trap).most_common(1)[0][1] / len(y), 4)}
            for name, f in probes.items()
        },
        "bag_of_lines_probe": {p: bag_of_lines_probe(cases, p) for p in sorted(set(probed)) if p != "CLEAN"},
        "f5_magnitude_threshold_accuracy": best_threshold(kw, f5),
        "f5_majority_accuracy": round(1 - sum(f5) / len(f5), 4),
        "proposed_kw_range_by_probed": {p: [min(k for k, q in zip(kw, probed, strict=True) if q == p),
                                            max(k for k, q in zip(kw, probed, strict=True) if q == p)]
                                        for p in sorted(set(probed))},
    }


def main(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    result = {name: analyse(json.loads((BENCHMARK_DIR / name).read_text(encoding="utf-8"))) for name in FILES}
    (out_dir / "baselines.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else RESULTS_DIR / "baselines_v2")
