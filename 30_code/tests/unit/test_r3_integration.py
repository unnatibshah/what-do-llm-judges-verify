"""Corpus r3 end to end (2026-10-01): corpus choice, r3 predicates and exposure material, registries, dev cases.

Candidate test cases are only generated in memory by the generator (the build path); no model is run on them.
"""

import json
import sys
from pathlib import Path

import pytest

from suryabench.applicability.evaluator import evaluate_predicate
from suryabench.applicability.schema import ApplicabilityPredicate
from suryabench.arms.controlled_exposure import EXPOSURE_MATERIAL, build_exposure
from suryabench.arms.verify_independent import Registry, load_registry, resolve_citation
from suryabench.cases.generator import UNREADABLE_CAPACITY_KW, build_v2_dev
from suryabench.cases.generator_v3 import (
    BUILDERS_V3,
    DROPPED_SLOTS,
    generate_v3_cases,
    load_r3_graph,
)
from suryabench.cases.schema import BenchmarkCase
from suryabench.core.enums import CurrencyVerdict
from suryabench.eval import runner
from suryabench.gate0.retriever import LocalRetriever, TextChunk
from suryabench.graph.oracle import in_force
from suryabench.graph.schema import SupersessionGraph
from suryabench.paths import (
    BENCHMARK_DIR,
    CODE_DIR,
    CORPUS_DIR,
    CORPUS_R3_DIR,
    RESULTS_DIR,
    corpus_dir,
    corpus_name,
    embeddings_cache,
)

sys.path.insert(0, str(CODE_DIR / "scripts"))
import build_applicability_r3 as bar3  # noqa: E402


@pytest.fixture(scope="module")
def graph() -> SupersessionGraph:
    return load_r3_graph()


@pytest.fixture(scope="module")
def predicates() -> list[ApplicabilityPredicate]:
    return [ApplicabilityPredicate.model_validate(p)
            for p in json.loads((CORPUS_R3_DIR / "graph" / "applicability.json").read_text(encoding="utf-8"))]


@pytest.fixture(scope="module")
def v3_cases(graph: SupersessionGraph) -> list[BenchmarkCase]:
    return generate_v3_cases(graph)


# --- 1. corpus choice --------------------------------------------------------------------------------
def test_corpus_choice_and_caches(tmp_path: Path) -> None:
    assert corpus_dir("r2") == CORPUS_DIR and corpus_dir("r3") == CORPUS_R3_DIR
    with pytest.raises(ValueError):
        corpus_dir("r4")
    assert corpus_name(CORPUS_R3_DIR) == "r3" and corpus_name("corpus") == "r2" and corpus_name(tmp_path) is None
    assert embeddings_cache("r2") == RESULTS_DIR / "embeddings_cache.json"
    assert embeddings_cache(CORPUS_R3_DIR) == RESULTS_DIR / "embeddings_cache_r3.json"
    assert embeddings_cache(tmp_path / "corpus") == tmp_path / "results" / "embeddings_cache.json"
    ignored = (CORPUS_DIR.parents[1] / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "50_analysis/results/embeddings_cache_r3.json" in ignored


def test_real_registry_by_corpus(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert runner.default_real_registry("r2") == (runner.REAL_REGISTRY, None)
    monkeypatch.setattr(runner, "REAL_REGISTRY_R3", tmp_path / "missing.json")
    path, warning = runner.default_real_registry("r3")
    assert path == runner.REAL_REGISTRY and warning and "falls back" in warning  # logged, never fatal
    monkeypatch.setattr(runner, "REAL_REGISTRY_R3", runner.REAL_REGISTRY)
    assert runner.default_real_registry("r3") == (runner.REAL_REGISTRY, None)


def test_r3_real_registry_unmatched_ids_are_unknown() -> None:
    """The blind r3 registry renumbers IN-C1-001 (REGISTRY-NOTES-v2-r3): a real clause id it lacks resolves to
    [] (unknown), never None (fabricated)."""
    reg_path = runner.REAL_REGISTRY_R3
    if not reg_path.exists():
        pytest.skip("registry_real_v2_r3.json not built yet")
    real = load_registry(reg_path)
    assert "IN-C1-001#cl-4.1" not in real.nodes
    chunk = TextChunk("IN-C1-001#chk-0000", "IN-C1-001", "x" * 50, 0, 50)
    r = LocalRetriever([chunk])
    r.chunk_clauses = {chunk.chunk_id: {"IN-C1-001#cl-4.1"}}
    reg = Registry("reg-real", real, {})
    assert resolve_citation("IN-C1-001#cl-4.1", reg, r) == []
    assert resolve_citation("ZZ-C9-999#cl-1", reg, r) is None


# --- 2. r3 applicability predicates and exposure material ---------------------------------------------
def test_new_predicates_cover_every_new_cluster_node(graph: SupersessionGraph, v3_cases: list[BenchmarkCase]) -> None:
    r2 = json.loads((CORPUS_DIR / "graph" / "applicability.json").read_text(encoding="utf-8"))
    r2_nodes = json.loads((CORPUS_DIR / "graph" / "supersession.json").read_text(encoding="utf-8"))["nodes"]
    saved = json.loads((CORPUS_R3_DIR / "graph" / "applicability.json").read_text(encoding="utf-8"))
    assert saved == bar3.build() and saved[:len(r2)] == r2  # r2 predicates kept unchanged, file = builder output
    used = {r.rule_id for c in v3_cases for r in c.applicable_rules}
    used |= {e for c in v3_cases for f in c.fault_events if f.fault_class.value == "F5" for e in f.gold_evidence}
    used |= {m["A"] for m in EXPOSURE_MATERIAL.values() if "A" in m}
    new = {n for n in used if n in graph.nodes and n not in r2_nodes}
    assert new <= set(bar3.R3_PREDICATES), sorted(new - set(bar3.R3_PREDICATES))


def test_decisive_predicates_hold_on_the_cases_they_decide(predicates: list[ApplicabilityPredicate],
                                                          v3_cases: list[BenchmarkCase]) -> None:
    by = {p.node_id: p for p in predicates if p.node_id in bar3.R3_PREDICATES}
    checked = 0
    for c in v3_cases:
        if c.facts.proposed_capacity_kw == UNREADABLE_CAPACITY_KW:  # F9: the capacity is hidden
            continue
        for r in c.applicable_rules:
            if r.rule_id in by:
                assert evaluate_predicate(by[r.rule_id], c.facts), (r.rule_id, c.case_id)
                checked += 1
    assert checked > 200


def test_r3_exposure_material_and_plans(graph: SupersessionGraph, predicates: list[ApplicabilityPredicate],
                                        v3_cases: list[BenchmarkCase]) -> None:
    assert set(BUILDERS_V3) - set(EXPOSURE_MATERIAL) == {"KA-C4-001#cl-1", "UP-C3-002#cl-6.2-proviso2"}
    preds = {p.node_id: p for p in predicates}
    n = {cond: 0 for cond in ("S-swap", "S-both", "J", "A")}  # S-both: opaque hex ids must parse
    for c in v3_cases:
        for cond in n:
            plan, _ = build_exposure(c, cond, graph, predicates)
            if plan is None:
                continue
            n[cond] += 1
            assert plan.fault_event is not None
            (planted,) = plan.fault_event.gold_evidence
            assert planted not in {r.rule_id for r in c.applicable_rules}
            if cond == "A":
                assert not evaluate_predicate(preds[planted], c.facts)
                assert in_force(planted, c.facts.case_date or "", graph) == CurrencyVerdict.IN_FORCE
    assert all(v > 0 for v in n.values()), n


# --- 5. dev cases on r3; candidate fix -----------------------------------------------------------------
def test_dev_v2_is_labelled_r3_and_its_nodes_are_unchanged_in_r3(graph: SupersessionGraph) -> None:
    cases = json.loads((BENCHMARK_DIR / "dev_cases_v2.json").read_text(encoding="utf-8"))
    assert {c["corpus_version"] for c in cases} == {json.loads(
        (CORPUS_R3_DIR / "MANIFEST.json").read_text(encoding="utf-8"))["corpus_version"]}
    r2_nodes = json.loads((CORPUS_DIR / "graph" / "supersession.json").read_text(encoding="utf-8"))["nodes"]
    ids = {r["rule_id"] for c in cases for r in c["applicable_rules"]}
    ids |= {e for c in cases for f in c["fault_events"] for e in f["gold_evidence"] if "#" in e}
    r3_nodes = json.loads((CORPUS_R3_DIR / "graph" / "supersession.json").read_text(encoding="utf-8"))["nodes"]
    for i in ids:
        assert r3_nodes[i] == r2_nodes[i], i
    assert [c.model_dump(mode="json") for c in build_v2_dev()] == cases


def test_dropped_self_trap_is_gone(v3_cases: list[BenchmarkCase]) -> None:
    assert len(v3_cases) == 239  # 242 drawn, 3 self-trap slots dropped
    for c in v3_cases:
        for f in c.fault_events:
            assert (c.cluster_id, f.gold_trigger) not in DROPPED_SLOTS
            if c.cluster_id == "DL-C3-009#cl-3.8" and f.fault_class.value == "F5":
                assert "DL-C3-009#cl-3.8" not in f.gold_evidence
