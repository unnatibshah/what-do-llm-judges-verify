"""Paper A redesign: controlled exposure (RD2), citation resolution (RD1), neutral query (RD3), Arm 5."""

import json
import re
from typing import Any

import pytest

from suryabench.applicability.evaluator import evaluate_predicate
from suryabench.applicability.schema import ApplicabilityPredicate
from suryabench.arms import arm2_agent, verify_independent
from suryabench.arms.arm2_agent import Arm2ExecutionResult, execute_arm2_agent
from suryabench.arms.arm5_recovery import execute_recovery
from suryabench.arms.controlled_exposure import (
    CONDITIONS,
    EXPOSURE_MATERIAL,
    build_exposure,
    format_nodes,
)
from suryabench.arms.verify_independent import (
    AUDIT_WORDS,
    Registry,
    execute_registry_check,
    execute_verify_independent,
    neutral_query,
    resolve_citation,
)
from suryabench.arms.verify_shared import VerifierResult
from suryabench.cases.schema import BenchmarkCase
from suryabench.core.enums import CurrencyVerdict
from suryabench.gate0.retriever import LocalRetriever, build_corpus_chunks, map_chunks_to_clauses
from suryabench.graph.oracle import in_force
from suryabench.graph.schema import SupersessionGraph
from suryabench.paths import BENCHMARK_DIR, CORPUS_DIR, CORPUS_R3_DIR


@pytest.fixture(scope="module")
def graph() -> SupersessionGraph:
    return SupersessionGraph.model_validate(
        json.loads((CORPUS_DIR / "graph" / "supersession.json").read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def predicates() -> list[ApplicabilityPredicate]:
    return [ApplicabilityPredicate.model_validate(p)
            for p in json.loads((CORPUS_DIR / "graph" / "applicability.json").read_text(encoding="utf-8"))]


@pytest.fixture(scope="module")
def dev_cases() -> list[BenchmarkCase]:
    return [BenchmarkCase.model_validate(c)
            for c in json.loads((BENCHMARK_DIR / "dev_cases_60.json").read_text(encoding="utf-8"))]


@pytest.fixture(scope="module")
def retriever(graph: SupersessionGraph) -> LocalRetriever:
    chunks = build_corpus_chunks(CORPUS_DIR / "text")
    r = LocalRetriever(chunks)  # unindexed: lexical fallback, no Ollama needed
    r.chunk_clauses = map_chunks_to_clauses(chunks, graph.nodes.values(), CORPUS_DIR / "text")
    return r


def _unlabelled(case: BenchmarkCase) -> BenchmarkCase:
    return case.model_copy(update={"fault_events": [], "expected_answer": None, "failure_class_probed": None,
                                   "non_fault_opportunities": []})


def _jur(graph: SupersessionGraph, nid: str) -> str:
    code = graph.nodes[nid].jurisdiction.code
    return str(getattr(code, "value", code))


# --- RD2: the section 5.3 material, confirmed by code ----------------------------------------------
def test_exposure_material_matches_graph() -> None:
    # r3 holds every r2 node unchanged plus the new clusters' anchors, so the whole table is checked on r3
    graph = SupersessionGraph.model_validate(
        json.loads((CORPUS_R3_DIR / "graph" / "supersession.json").read_text(encoding="utf-8")))
    preds = {p["node_id"] for p in json.loads((CORPUS_R3_DIR / "graph" / "applicability.json").read_text(encoding="utf-8"))}
    for anchor, mat in EXPOSURE_MATERIAL.items():
        a = graph.nodes[anchor]
        if "S" in mat:  # the predecessor is the source of a superseded_by edge into the anchor
            assert any(e.from_node == mat["S"] and e.to_node == anchor and e.relation == "superseded_by"
                       for e in graph.edges), anchor
        if "J" in mat:  # same subject, the other state, in force
            j = graph.nodes[mat["J"]]
            assert j.subject == a.subject and _jur(graph, mat["J"]) not in {_jur(graph, anchor), "IN"}
            assert j.status_at_snapshot == "in_force"
        if "A" in mat:  # same subject and jurisdiction, in force, with a predicate
            s = graph.nodes[mat["A"]]
            assert s.subject == a.subject and _jur(graph, mat["A"]) == _jur(graph, anchor)
            assert s.status_at_snapshot == "in_force" and mat["A"] in preds
    assert "MH-C5-001#cl-feasibility" not in {v for m in EXPOSURE_MATERIAL.values() for v in m.values()}


def test_dev_exposure_counts(graph: SupersessionGraph, predicates: list[ApplicabilityPredicate],
                             dev_cases: list[BenchmarkCase]) -> None:
    """Dev supports every condition (plan section 5.3); skipped cases are the ones without material, and (N11,
    2026-10-01) the ones whose plant is computed to give the anchor's outcome: the MH and RJ capacity rules are
    both 100% of sanctioned load, so most dev J plants cannot flip a decision (40 -> 6), S-swap/S-both 32 -> 24."""
    n = {c: sum(build_exposure(k, c, graph, predicates)[0] is not None for k in dev_cases) for c in CONDITIONS}
    assert n == {"N": 60, "C": 60, "S-swap": 24, "S-both": 24, "J": 6, "A": 36, "O": 8}


def test_exposure_plans_plant_valid_distractors(graph: SupersessionGraph, predicates: list[ApplicabilityPredicate],
                                                dev_cases: list[BenchmarkCase]) -> None:
    for case in dev_cases:
        decisive = [r.rule_id for r in case.applicable_rules]
        state = str(getattr(case.facts.state, "value", case.facts.state))
        for cond in ["S-swap", "S-both", "J", "A", "O"]:
            plan, _ = build_exposure(case, cond, graph, predicates)
            if plan is None:
                continue
            fe = plan.fault_event
            assert fe is not None and fe.fault_event_id == f"{case.case_id}#exp-{cond}"
            (planted,) = fe.gold_evidence
            if cond == "O":
                assert planted in decisive and planted not in plan.node_ids
                continue
            assert planted in plan.node_ids and planted not in decisive
            if cond.startswith("S"):
                assert in_force(planted, case.facts.case_date or "", graph) != CurrencyVerdict.IN_FORCE
            if cond == "S-both":  # predecessor first in even-numbered cases, second in odd
                even = int(case.case_id.rsplit("-", 1)[1]) % 2 == 0
                anchor = plan.node_ids[plan.node_ids.index(planted) + (1 if even else -1)]
                assert anchor in decisive
            if cond == "J":
                assert _jur(graph, planted) not in {state, "IN"}
            if cond == "A":
                pred = next(p for p in predicates if p.node_id == planted)
                assert not evaluate_predicate(pred, case.facts)


def test_injected_nodes_are_the_only_generator_context(graph: SupersessionGraph,
                                                       predicates: list[ApplicabilityPredicate],
                                                       dev_cases: list[BenchmarkCase], retriever: LocalRetriever,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    """RD2/D11 acceptance: the injected evidence is the generator's whole context, rendered as retrieved chunks
    (chunk ids, the retriever's header), and every injected clause lies inside a shown chunk."""
    prompts: list[str] = []

    def fake(prompt: str, **_: Any) -> tuple[dict[str, Any], int, int]:
        prompts.append(prompt)
        return {"action": "final", "decision": "APPROVED", "cited_rules": []}, 0, 0

    def no_retrieval(*_: Any, **__: Any) -> Any:
        raise AssertionError("an injected condition must not retrieve")

    monkeypatch.setattr(arm2_agent, "call_llm_json", fake)
    monkeypatch.setattr(retriever, "retrieve", no_retrieval)
    for case in dev_cases[:30]:
        for cond in ["C", "S-swap", "S-both", "J", "A", "O"]:
            plan, _ = build_exposure(case, cond, graph, predicates, retriever.chunk_clauses)
            if plan is None:
                continue
            prompts.clear()
            ids, texts = format_nodes(plan.node_ids, graph, retriever)
            res = execute_arm2_agent(_unlabelled(case), retriever, model="mock", evidence=(ids, texts))
            assert re.findall(r"\[SOURCE chunk_id=(\S+) ", prompts[0]) == ids
            assert res.retrieved_chunk_ids == ids
            shown = set().union(*(retriever.chunk_clauses.get(i, {i}) for i in ids))
            assert set(plan.node_ids) <= shown
            if cond == "O":
                assert plan.fault_event is not None and plan.fault_event.gold_evidence[0] not in shown


# --- RD1: chunk-id citations resolve to clauses, not to F1 ------------------------------------------
def test_resolve_citation(graph: SupersessionGraph, retriever: LocalRetriever) -> None:
    reg = Registry("reg-oracle", graph, retriever.chunk_clauses)
    mapped = next(c for c, ns in retriever.chunk_clauses.items() if ns)
    unmapped = next(c.chunk_id for c in retriever.chunks if c.chunk_id not in retriever.chunk_clauses)
    assert resolve_citation("MH-C3-001#cl-6.2", reg, retriever) == ["MH-C3-001#cl-6.2"]
    assert resolve_citation(mapped, reg, retriever) == sorted(retriever.chunk_clauses[mapped])
    assert resolve_citation(unmapped, reg, retriever) == []
    assert resolve_citation("MH-C3-001", reg, retriever) == []  # a real document
    assert resolve_citation("MH-C9-999#cl-1", reg, retriever) is None
    # the old substring match resolved this proviso to its parent clause
    assert resolve_citation("RJ-C3-003#cl-2-proviso", reg, retriever) == ["RJ-C3-003#cl-2-proviso"]


def _gen(case: BenchmarkCase, cited: list[str], retrieved: list[str]) -> Arm2ExecutionResult:
    return Arm2ExecutionResult(
        case_id=case.case_id, arm_id="Arm-2", decision="APPROVED", is_approved=True, cited_rules=cited,
        root_cause=None, blocking_stage=None, subsidy_amount_inr=0.0, computed=[], tool_outputs={},
        retrieved_chunks=["text"] * len(retrieved), retrieved_chunk_ids=retrieved, latency_sec=0.0,
        prompt_tokens=0, completion_tokens=0, raw_output={})


def test_registry_does_not_flag_real_chunk_citations(graph: SupersessionGraph, retriever: LocalRetriever,
                                                     dev_cases: list[BenchmarkCase]) -> None:
    case = _unlabelled(dev_cases[1])
    reg = Registry("reg-oracle", graph, retriever.chunk_clauses)
    mapped = next(c for c, ns in retriever.chunk_clauses.items() if "IN-C1-001#cl-4.1" in ns)
    unmapped = next(c.chunk_id for c in retriever.chunks if c.chunk_id not in retriever.chunk_clauses)
    res = execute_registry_check(case, _gen(case, [mapped, unmapped], [mapped]), retriever, reg)
    assert not any(f.startswith("F1") for f in res.flagged_faults)
    assert "IN-C1-001#cl-4.1" in res.evidence_ids  # the chunk was looked up as its clause
    assert res.prompt_tokens == 0  # deterministic: no LLM call
    fab = execute_registry_check(case, _gen(case, ["MH-C9-999#cl-1"], []), retriever, reg)
    assert fab.flagged_faults == ["F1:MH-C9-999#cl-1:other"]  # D32: fabrication has no validity reason


# --- RD3: the neutral query ---------------------------------------------------------------------------
def test_neutral_query_has_no_audit_wording_and_no_chunk_ids(graph: SupersessionGraph, retriever: LocalRetriever,
                                                            dev_cases: list[BenchmarkCase],
                                                            monkeypatch: pytest.MonkeyPatch) -> None:
    """RD3 acceptance: the I1 verifier never receives the generator's chunk ids."""
    queries: list[str] = []
    real = retriever.retrieve
    monkeypatch.setattr(retriever, "retrieve", lambda q, top_k=5: queries.append(q) or real(q, top_k))
    mapped = next(c for c, ns in retriever.chunk_clauses.items() if ns)
    for case in dev_cases:
        u = _unlabelled(case)
        gen = _gen(u, [mapped, "MH-C3-001#cl-6.2"], [mapped, "IN-C1-001#chk-0000"])
        queries.clear()
        execute_verify_independent(u, gen, retriever, independence_config="100-neutral", model="mock")
        (q,) = queries
        assert all(cid not in q for cid in gen.retrieved_chunk_ids + [mapped])
        assert all(w not in q.lower() for w in AUDIT_WORDS)
        assert "MH-C3-001" not in q and "Decision" not in q  # D29: no generator output in the query
    template = neutral_query(verify_independent.parse_case_facsimiles(dev_cases[0].inputs))
    assert all(w not in template.lower() for w in AUDIT_WORDS)


# --- Arm 5 --------------------------------------------------------------------------------------------
def test_recovery_reuses_evidence_and_passes_the_critique(retriever: LocalRetriever, dev_cases: list[BenchmarkCase],
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    prompts: list[str] = []
    monkeypatch.setattr(arm2_agent, "call_llm_json",
                        lambda prompt, **_: (prompts.append(prompt) or {"action": "final", "decision": "REJECTED"}, 0, 0))
    case = _unlabelled(dev_cases[1])
    initial = _gen(case, ["IN-C1-001#cl-4.1"], ["IN-C1-001#chk-0022"])
    ver = VerifierResult(case_id=case.case_id, verifier_id="v", independence_config="111", verdict="FLAG",
                         is_flagged=True, flagged_faults=["F3"], audit_reason="cites a superseded rule",
                         latency_sec=0.0, prompt_tokens=0, completion_tokens=0, raw_output={})
    revised = execute_recovery(case, initial, ver, retriever, model="mock")
    assert revised.arm_id == "Arm-5" and revised.decision == "REJECTED"
    assert revised.retrieved_chunk_ids == initial.retrieved_chunk_ids
    assert "[VERIFIER CRITIQUE]" in prompts[0] and "cites a superseded rule" in prompts[0] and "['F3']" in prompts[0]
