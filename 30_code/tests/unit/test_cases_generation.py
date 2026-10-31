"""Unit tests for the rule-driven SuryaBench benchmark (160 cases, 8 clusters) and its seal."""

import hashlib
import json
from pathlib import Path

import pytest

from suryabench.cases.generator import DEV_RULE_NODES, TEST_RULE_NODES
from suryabench.cases.schema import BenchmarkCase
from suryabench.cases.validator import validate_benchmark_suite
from suryabench.core.exceptions import TestSplitAccessViolation
from suryabench.core.guard import TestSplitGuard
from suryabench.paths import BENCHMARK_DIR, CORPUS_DIR

ALL_CASES_PATH = BENCHMARK_DIR / "benchmark_cases_160.json"
DEV_CASES_PATH = BENCHMARK_DIR / "dev_cases_60.json"
TEST_CASES_PATH = BENCHMARK_DIR / "test_cases_100.json"
SHA256_PATH = BENCHMARK_DIR / "BENCHMARK.sha256"


def test_benchmark_files_exist() -> None:
    """Verify all benchmark files and manifest exist."""
    assert ALL_CASES_PATH.exists(), f"Missing {ALL_CASES_PATH}"
    assert DEV_CASES_PATH.exists(), f"Missing {DEV_CASES_PATH}"
    assert TEST_CASES_PATH.exists(), f"Missing {TEST_CASES_PATH}"
    assert SHA256_PATH.exists(), f"Missing {SHA256_PATH}"


def test_sha256_manifest_integrity() -> None:
    """Verify cryptographic sealing integrity against BENCHMARK.sha256."""
    sha_lines = SHA256_PATH.read_text(encoding="utf-8").strip().splitlines()
    manifest_hashes = {}
    for line in sha_lines:
        parts = line.split()
        if len(parts) == 2:
            manifest_hashes[parts[1]] = parts[0]

    for path in (ALL_CASES_PATH, DEV_CASES_PATH, TEST_CASES_PATH):
        content = path.read_bytes()
        actual_hash = hashlib.sha256(content).hexdigest()
        assert (
            actual_hash == manifest_hashes[path.name]
        ), f"Hash mismatch for {path.name}: expected {manifest_hashes[path.name]}, got {actual_hash}"


def _load(path: Path) -> list[BenchmarkCase]:
    with open(path, encoding="utf-8") as f:
        return [BenchmarkCase.model_validate(c) for c in json.load(f)]


def _cluster(case: BenchmarkCase) -> str:
    return case.case_id.rsplit("-", 1)[0]


def test_case_counts_and_partition_disjointness() -> None:
    """160 cases = 60 dev (3 clusters) + 100 test (5 clusters), 20 per cluster, disjoint."""
    all_cases, dev, test = _load(ALL_CASES_PATH), _load(DEV_CASES_PATH), _load(TEST_CASES_PATH)
    assert (len(all_cases), len(dev), len(test)) == (160, 60, 100)
    dev_ids, test_ids = {c.case_id for c in dev}, {c.case_id for c in test}
    assert dev_ids.isdisjoint(test_ids)
    assert dev_ids | test_ids == {c.case_id for c in all_cases}


def test_zero_cross_split_cluster_leakage() -> None:
    """Clusters are disjoint across the split; each has exactly 20 cases."""
    assert set(DEV_RULE_NODES).isdisjoint(TEST_RULE_NODES)
    for path, nodes in ((DEV_CASES_PATH, DEV_RULE_NODES), (TEST_CASES_PATH, TEST_RULE_NODES)):
        cases = _load(path)
        prefixes = {n.replace("#", "-").replace(".", "_") for n in nodes}
        counts: dict[str, int] = {}
        for c in cases:
            counts[_cluster(c)] = counts.get(_cluster(c), 0) + 1
        assert set(counts) == prefixes
        assert all(v == 20 for v in counts.values()), counts


def test_jurisdiction_stratification() -> None:
    """Both splits contain central, Maharashtra and Rajasthan clusters; cases are set in MH and RJ."""
    for nodes in (DEV_RULE_NODES, TEST_RULE_NODES):
        assert {n[:2] for n in nodes} == {"IN", "MH", "RJ"}
    for path in (DEV_CASES_PATH, TEST_CASES_PATH):
        assert {c.facts.state.value for c in _load(path)} == {"MH", "RJ"}


def test_validate_all_benchmark_cases_programmatic_integrity() -> None:
    validate_benchmark_suite(_load(ALL_CASES_PATH))


def test_every_cluster_covers_the_core_partitions() -> None:
    """Every cluster has clean, omission (F4), abstention (F9) and multi-fault cases."""
    by: dict[str, set[str]] = {}
    for c in _load(ALL_CASES_PATH):
        by.setdefault(_cluster(c), set()).add(c.failure_class_probed)
    for cluster, probed in by.items():
        assert {"CLEAN", "F4", "F9", "MULTI"} <= probed, (cluster, probed)


def test_dev_split_can_elicit_f5_and_f6() -> None:
    """Gate 2 needs >=5 F5 and >=5 F6 events spanning >=3 clusters to be attainable on dev."""
    for cls in ("F5", "F6"):
        events = [(c.case_id, fe) for c in _load(DEV_CASES_PATH) for fe in c.fault_events if fe.fault_class == cls]
        assert len(events) >= 5 and len({_cluster_of(cid) for cid, _ in events}) >= 3, cls


def _cluster_of(case_id: str) -> str:
    return case_id.rsplit("-", 1)[0]


def test_decisive_rules_exist_in_graph() -> None:
    """Every applicable (decisive) rule and every clause-valued fault evidence is a graph node."""
    from suryabench.graph.schema import SupersessionGraph

    graph_path = CORPUS_DIR / "graph" / "supersession.json"
    graph = SupersessionGraph.model_validate(json.loads(graph_path.read_text(encoding="utf-8")))
    for c in _load(ALL_CASES_PATH):
        for r in c.applicable_rules:
            assert r.rule_id in graph.nodes, (c.case_id, r.rule_id)
        for fe in c.fault_events:
            for ev in fe.gold_evidence:
                if "#" in ev:
                    assert ev in graph.nodes, (c.case_id, ev)


def test_surface_facsimiles_populated() -> None:
    """Verify every case contains non-trivial surface facsimiles."""
    with open(ALL_CASES_PATH, encoding="utf-8") as f:
        all_cases = [BenchmarkCase.model_validate(c) for c in json.load(f)]

    for c in all_cases:
        assert len(c.inputs.bill.strip()) > 20, f"Case {c.case_id} has empty/short bill"
        assert len(c.inputs.proposal.strip()) > 20, f"Case {c.case_id} has empty/short proposal"
        assert len(c.inputs.portal_state.strip()) > 20, f"Case {c.case_id} has empty/short portal_state"


def test_test_split_guard_on_sealed_dataset() -> None:
    """Verify TestSplitGuard blocks unauthorized access to test_cases_100.json."""
    with pytest.raises(TestSplitAccessViolation, match="Prohibited access"):
        TestSplitGuard.verify_access(str(TEST_CASES_PATH))

    with TestSplitGuard.authorize():
        TestSplitGuard.verify_access(str(TEST_CASES_PATH))
