"""T1 (P3-2): the candidate v3 test split, built per distinct replaced clause (D37, D38). No model is run.

From the candidate pool (the 20 v2 rule groups, ids unchanged, plus the groups added in D38) it keeps, for every
planted superseded clause with at least 3 S-both pairs (``count_ladder_items``), PAIRS_PER_CLAUSE applications that
carry an S-both pair: round robin over (outcome-changing or basis-only) x (gold approve or reject), applications
that also carry an S-swap pair first, seeded order otherwise. Each kept application also gives one clean correct
answer (condition C) and its J/A pairs where they exist, so C spans every kept group.

1. 40_data/benchmark/test_cases_v3_CANDIDATE.json (+ .sha256): NOT sealed, labels provisional until annotation (U2).
2. 40_data/benchmark/TEST_CANDIDATE_HASHES.json: content hashes read by core/guard.py (only ever added to).
3. 50_analysis/results/ladder_design/candidate_v3_manifest.json: clauses, states, pairs per clause and condition.

Usage (repository root): PYTHONPATH=30_code/src:30_code/scripts python 30_code/scripts/build_test_candidate_v3.py
"""

import hashlib
import json
import random
from collections import Counter, defaultdict
from typing import Any

from count_ladder_items import MIN_PAIRS, OUT_DIR, S_CONDITIONS, ProbeWorld, count

from suryabench.arms import verifier_probe as vp
from suryabench.cases.generator_v3 import generate_v3_pool
from suryabench.cases.schema import BenchmarkCase
from suryabench.core.guard import TEST_CANDIDATE_HASHES_FILE, case_content_hash
from suryabench.paths import BENCHMARK_DIR

CANDIDATE_V3 = "test_cases_v3_CANDIDATE.json"
SEED = "SuryaBench-v3-test-candidate-2026-10"
PAIRS_PER_CLAUSE = 4  # D37: 3-6 pairs per distinct replaced clause; 4 keeps C near the ~50 clean answers asked for
CAP = 6
BUCKETS = [(True, "APPROVED"), (False, "REJECTED"), (True, "REJECTED"), (False, "APPROVED")]


def select(available: dict[str, Any], cases: list[BenchmarkCase]) -> dict[str, list[str]]:
    """Planted clause -> the case ids kept for it."""
    by_id = {c.case_id: c for c in cases}
    rng = random.Random(SEED)
    chosen: dict[str, list[str]] = {}
    for g in available["groups"]:
        for r in g["replaced_clauses"]:
            if r["S-both"]["pairs"] < MIN_PAIRS:
                continue
            swap = set(r["S-swap"]["cases"])
            pools: dict[tuple[bool, str], list[str]] = defaultdict(list)
            for cid in sorted(r["S-both"]["cases"]):
                pools[(cid in r["oc_cases"], vp.gold_outcome(by_id[cid])[0])].append(cid)
            for p in pools.values():
                rng.shuffle(p)
                p.sort(key=lambda cid: cid not in swap)  # stable: S-swap carriers first, seeded order within
            taken: list[str] = []
            while len(taken) < PAIRS_PER_CLAUSE and any(pools.values()):
                for b in BUCKETS:
                    if pools.get(b) and len(taken) < PAIRS_PER_CLAUSE:
                        taken.append(pools[b].pop(0))
            chosen[r["clause"]] = taken
    return chosen


def main() -> None:
    world = ProbeWorld()
    pool = generate_v3_pool(world.graph)
    available = count(world, pool)
    items, _ = vp.build_items(pool, world.graph, world.predicates, world.retriever)
    oc = {(i.planted, i.case_id) for i in items if i.condition == "S-both" and i.role == "fault" and i.outcome_changing}
    for g in available["groups"]:
        for r in g["replaced_clauses"]:
            r["oc_cases"] = {cid for p, cid in oc if p == r["clause"]}
    chosen = select(available, pool)
    keep = {cid for ids in chosen.values() for cid in ids}
    cases = [c for c in pool if c.case_id in keep]
    random.Random(SEED + "|order").shuffle(cases)

    # the manifest: what the kept cases yield, rebuilt from the kept cases alone
    kept_items, _ = vp.build_items(cases, world.graph, world.predicates, world.retriever)
    faults = [i for i in kept_items if i.role == "fault"]
    per_clause: dict[str, Counter[str]] = defaultdict(Counter)
    for i in faults:
        if i.condition not in S_CONDITIONS:
            continue
        per_clause[str(i.planted)][i.condition] += 1
        per_clause[str(i.planted)][f"{i.condition}:outcome_changing"] += i.outcome_changing
    info = {r["clause"]: r for g in available["groups"] for r in g["replaced_clauses"]}
    replaced = [{"clause": k, "state": info[k]["state"], "successor": info[k]["successor"],
                 "explicit_implicit": info[k]["registry"]["explicit_implicit"],
                 "registry_flags_superseded": info[k]["registry"]["flags_superseded_at_case_date"],
                 "cases": sorted(chosen[k]), **dict(sorted(per_clause[k].items()))} for k in sorted(chosen)]
    by_cond = Counter(i.condition for i in faults)
    clauses_by_cond = {c: len({i.planted for i in faults if i.condition == c}) for c in vp.PLANT_CONDITIONS}
    max_pairs = max(n for r in per_clause.values() for k, n in r.items() if ":" not in k)
    assert max_pairs <= CAP, f"a replaced clause has {max_pairs} pairs in one condition (cap {CAP})"
    assert set(per_clause) == set(chosen), "a kept case lost its S-both pair"

    text = json.dumps([c.model_dump(mode="json") for c in cases], indent=2)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    manifest = {
        "file": CANDIDATE_V3, "sha256": digest, "sealed": False, "n_cases": len(cases),
        "distinct_replaced_clauses": len(replaced),
        "states": dict(sorted(Counter(r["state"] for r in replaced).items())),
        "explicit_implicit": dict(sorted(Counter(r["explicit_implicit"] for r in replaced).items())),
        "pairs_per_clause_target": PAIRS_PER_CLAUSE, "pairs_per_clause_cap": CAP, "max_pairs_one_clause_one_condition": max_pairs,
        "fault_items_by_condition": dict(sorted(by_cond.items())),
        "control_items_by_condition": dict(sorted(Counter(i.condition for i in kept_items if i.role == "control").items())),
        "clean_correct_answers_C": sum(i.role == "c-control" for i in kept_items),
        "distinct_planted_clauses_by_condition": clauses_by_cond,
        "replaced_clauses": replaced,
    }
    (BENCHMARK_DIR / CANDIDATE_V3).write_text(text, encoding="utf-8", newline="\n")
    (BENCHMARK_DIR / CANDIDATE_V3.replace(".json", ".sha256")).write_text(f"{digest}  {CANDIDATE_V3}\n", encoding="utf-8",
                                                                         newline="\n")
    old = json.loads(TEST_CANDIDATE_HASHES_FILE.read_text(encoding="utf-8")) if TEST_CANDIDATE_HASHES_FILE.exists() else []
    hashes = sorted(set(old) | {case_content_hash(c.model_dump(mode="json")) for c in cases})
    TEST_CANDIDATE_HASHES_FILE.write_text(json.dumps(hashes, indent=1) + "\n", encoding="utf-8", newline="\n")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "candidate_v3_manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8",
                                                        newline="\n")
    print(f"{CANDIDATE_V3}: {len(cases)} cases, {len(replaced)} distinct replaced clauses from {manifest['states']}; "
          f"faults {manifest['fault_items_by_condition']}; C {manifest['clean_correct_answers_C']}; "
          f"clauses by condition {clauses_by_cond}; sha256 {digest[:12]}")


if __name__ == "__main__":
    main()
