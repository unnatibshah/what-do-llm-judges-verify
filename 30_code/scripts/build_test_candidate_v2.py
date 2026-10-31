"""Generate the candidate v2 test split from the corpus-r3 clusters, guard it, and record its baselines.

1. 40_data/benchmark/test_cases_v2_CANDIDATE.json (+ .sha256): opaque ids, cluster_id set. NOT sealed:
   labels are provisional until the human annotation (20_method/ANNOTATION-PACKET.md).
2. 40_data/benchmark/TEST_CANDIDATE_HASHES.json: content hashes read by core/guard.py, so no model run
   can read these cases without --allow-test (hashes are only ever added).
3. 50_analysis/results/baselines_v2/test_candidate_baselines.json: trivial baselines (no model is run).

Usage (repository root): PYTHONPATH=30_code/src python 30_code/scripts/build_test_candidate_v2.py
"""

import json
from collections import Counter, defaultdict

import trivial_baselines as tb

from suryabench.cases.generator_v3 import CANDIDATE_FILE, save_candidate
from suryabench.core.guard import TEST_CANDIDATE_HASHES_FILE, case_content_hash
from suryabench.paths import BENCHMARK_DIR, RESULTS_DIR

if __name__ == "__main__":
    digest = save_candidate()
    cases = json.loads((BENCHMARK_DIR / CANDIDATE_FILE).read_text(encoding="utf-8"))
    old = json.loads(TEST_CANDIDATE_HASHES_FILE.read_text(encoding="utf-8")) if TEST_CANDIDATE_HASHES_FILE.exists() else []
    hashes = sorted(set(old) | {case_content_hash(c) for c in cases})
    TEST_CANDIDATE_HASHES_FILE.write_text(json.dumps(hashes, indent=1) + "\n", encoding="utf-8", newline="\n")

    result = tb.analyse(cases)
    by: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for c in cases:
        by[c["cluster_id"]].append((tb.capacity_heuristic(c), tb.gold(c)))
    result["capacity_heuristic_by_cluster"] = {
        k: {"n": len(v), "accuracy": round(sum(h == g for h, g in v) / len(v), 4), "gold": dict(Counter(g for _, g in v))}
        for k, v in sorted(by.items())}
    maj = max(result["gold_counts"].values()) / result["n"]
    result["criterion"] = {"majority_class_accuracy": round(maj, 4),
                           "capacity_heuristic_accuracy": result["accuracy"]["capacity_heuristic"],
                           "limit_majority_plus_10": round(maj + 0.10, 4),
                           "met": result["accuracy"]["capacity_heuristic"] <= maj + 0.10}
    result["file"] = f"40_data/benchmark/{CANDIDATE_FILE}"
    result["sha256"] = digest
    result["status"] = "CANDIDATE: labels provisional until human annotation; not sealed"
    out = RESULTS_DIR / "baselines_v2" / "test_candidate_baselines.json"
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"n": result["n"], "gold": result["gold_counts"], "accuracy": result["accuracy"],
                      "criterion": result["criterion"], "hashes": len(hashes)}, indent=1))
