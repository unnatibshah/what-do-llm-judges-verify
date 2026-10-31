"""D32 (2026-10-02): a primary catch is the right clause AND the right reason.

Reason parsing, the identical reason block in every verifier prompt, registry reasons, per-class matching, and a
regression test for the dev-pilot pattern (planted clause named on content grounds under S-swap). Dev v2 cases
only, generated in memory; no model is run.
"""

import json
import re
from types import SimpleNamespace
from typing import Any

import pytest

from suryabench.analysis.paper import _validity_flagged, exposure_events
from suryabench.applicability.schema import ApplicabilityPredicate
from suryabench.arms import verify_reflect, verify_shared
from suryabench.arms.arm2_agent import Arm2ExecutionResult
from suryabench.arms.arm5_recovery import critique_block
from suryabench.arms.controlled_exposure import build_exposure
from suryabench.arms.verify_independent import (
    Registry,
    execute_registry_check,
    execute_registry_llm,
    execute_verify_independent,
)
from suryabench.arms.verify_reflect import execute_verify_reflect
from suryabench.arms.verify_shared import (
    REASON_BLOCK,
    REASONS,
    VARIANTS,
    VerifierResult,
    execute_verify_shared,
    parse_verdict,
    reason_code,
)
from suryabench.cases.generator import build_v2_dev
from suryabench.cases.generator_v3 import load_r3_graph
from suryabench.cases.schema import BenchmarkCase
from suryabench.corpus.manifest import load_manifest
from suryabench.eval.failure_classifier import CLASS_REASON, FailureClassifier
from suryabench.gate0.retriever import LocalRetriever, build_corpus_chunks, map_chunks_to_clauses
from suryabench.graph.schema import SupersessionGraph
from suryabench.paths import CORPUS_R3_DIR


@pytest.fixture(scope="module")
def graph() -> SupersessionGraph:
    return load_r3_graph()


@pytest.fixture(scope="module")
def retriever(graph: SupersessionGraph) -> LocalRetriever:
    text = CORPUS_R3_DIR / "text"
    chunks = build_corpus_chunks(text)
    r = LocalRetriever(chunks)
    r.chunk_clauses = map_chunks_to_clauses(chunks, graph.nodes.values(), text)
    return r


@pytest.fixture(scope="module")
def cases() -> list[BenchmarkCase]:
    return build_v2_dev()


@pytest.fixture(scope="module")
def classifier(graph: SupersessionGraph, retriever: LocalRetriever) -> FailureClassifier:
    return FailureClassifier(graph, load_manifest(CORPUS_R3_DIR / "MANIFEST.json"), retriever.chunk_clauses)


def _gen(case: BenchmarkCase, cited: list[str]) -> Arm2ExecutionResult:
    return Arm2ExecutionResult(case_id=case.case_id, arm_id="Arm-2", decision="APPROVED", is_approved=True,
                               cited_rules=cited, root_cause=None, blocking_stage=None, subsidy_amount_inr=None,
                               computed=[], tool_outputs={}, retrieved_chunks=["text"], retrieved_chunk_ids=[],
                               latency_sec=0.0, prompt_tokens=0, completion_tokens=0, raw_output={})


def test_reason_parsing() -> None:
    assert reason_code("Not in force") == "not_in_force" and reason_code("wrong-jurisdiction") == "wrong_jurisdiction"
    assert {k.value: v for k, v in CLASS_REASON.items()} == {"F2": "wrong_jurisdiction", "F3": "not_in_force",
                                                            "F4": "missing_rule", "F5": "not_applicable"}
    assert reason_code("superseded") == "other" and reason_code(None) == "other" and reason_code("") == "other"
    _, _, findings, flags = parse_verdict({"verdict": "FLAG", "findings": [
        {"clause_id": "A#cl-1", "reason": "content_or_arithmetic", "rationale": "exceeds 50% of DT capacity"},
        {"clause_id": "B#cl-2", "reason": "the clause is old"}, {"clause_id": "C#cl-3"}]})
    assert [f["reason"] for f in findings] == ["content_or_arithmetic", "other", "other"]
    assert flags == ["ANY:A#cl-1:content_or_arithmetic", "ANY:B#cl-2:other", "ANY:C#cl-3:other"]


def test_reason_block_is_neutral_and_identical_in_every_verifier_prompt(
        monkeypatch: pytest.MonkeyPatch, cases: list[BenchmarkCase], graph: SupersessionGraph,
        retriever: LocalRetriever) -> None:
    assert set(REASONS) == {"not_in_force", "wrong_jurisdiction", "not_applicable", "missing_rule",
                            "content_or_arithmetic", "other"}
    assert not re.search(r"[A-Z]{2}-C\d|#cl-|\bF\d\b|plant", REASON_BLOCK)  # no clause, class or plant named
    prompts: list[str] = []
    reply = {"verdict": "PASS", "risk": 0.1, "findings": [], "reflection": "r"}

    def fake(prompt: str, **_: Any) -> tuple[dict[str, Any], int, int]:
        prompts.append(prompt)
        return reply, 1, 1

    monkeypatch.setattr(verify_shared, "call_llm_json", fake)
    monkeypatch.setattr(verify_reflect, "call_llm_json", fake)
    monkeypatch.setattr(retriever, "retrieve", lambda *a, **k: [])
    case = cases[0].model_copy(update={"fault_events": []})
    gen = _gen(case, [case.applicable_rules[0].rule_id])
    for variant in VARIANTS:
        for tax in (False, True):
            execute_verify_shared(case, gen, variant=variant, taxonomy=tax)
    execute_verify_reflect(case, gen)
    execute_verify_independent(case, gen, retriever)
    execute_registry_llm(case, gen, retriever, Registry("reg-real", graph, retriever.chunk_clauses))
    final = [p for p in prompts if "stage 1 of 2" not in p]  # reflect pass 1 asks for a critique, not findings
    assert len(final) == 2 * len(VARIANTS) + 3
    # E2 (T2): the -cc variants show the CC reason list instead; every other prompt shows REASON_BLOCK once
    cc = verify_shared.reason_block(verify_shared.CC_REASONS)
    n_cc = 2 * sum(v.endswith("-cc") for v in VARIANTS)
    assert sum(p.count(cc) == 1 and REASON_BLOCK not in p for p in final) == n_cc
    assert sum(p.count(REASON_BLOCK) == 1 for p in final) == len(final) - n_cc


def test_registry_findings_carry_reasons(cases: list[BenchmarkCase], graph: SupersessionGraph,
                                         retriever: LocalRetriever) -> None:
    reg = Registry("reg-oracle", graph, retriever.chunk_clauses)
    by_class: dict[str, set[str]] = {}
    for c in cases:
        case = c.model_copy(update={"fault_events": []})
        for cond in ("S-swap", "J"):
            plan, _ = build_exposure(c, cond, graph, _predicates(), retriever.chunk_clauses)
            if plan is None or plan.fault_event is None:
                continue
            res = execute_registry_check(case, _gen(case, [plan.fault_event.gold_evidence[0]]), retriever, reg)
            for f in res.findings:
                by_class.setdefault(f["class"], set()).add(f["reason"])
    assert by_class.get("F3") == {"not_in_force"} and by_class.get("F2") == {"wrong_jurisdiction"}


def _predicates() -> list[ApplicabilityPredicate]:
    return [ApplicabilityPredicate.model_validate(p)
            for p in json.loads((CORPUS_R3_DIR / "graph" / "applicability.json").read_text(encoding="utf-8"))]


def _committed(cases: list[BenchmarkCase], graph: SupersessionGraph, retriever: LocalRetriever,
               cond: str) -> tuple[BenchmarkCase, SimpleNamespace, str, str] | None:
    """The first dev case with a plan under ``cond``: the scored case, a flipped output citing the plant, event, plant."""
    for c in cases:
        plan, _ = build_exposure(c, cond, graph, _predicates(), retriever.chunk_clauses)
        if plan is None or plan.fault_event is None:
            continue
        approved = c.expected_answer.blocking_stage is None
        out = SimpleNamespace(decision="REJECTED" if approved else "APPROVED",
                              blocking_stage="technical_feasibility" if approved else None,
                              cited_rules=[plan.fault_event.gold_evidence[0]], root_cause="", computed=[])
        scored = c.model_copy(update={"fault_events": [*c.fault_events, plan.fault_event]})
        return scored, out, plan.fault_event.fault_event_id, plan.fault_event.gold_evidence[0]
    return None


@pytest.mark.parametrize("cond", ["S-swap", "S-both", "J", "A"])
def test_primary_needs_the_class_reason(cond: str, cases: list[BenchmarkCase], graph: SupersessionGraph,
                                        retriever: LocalRetriever, classifier: FailureClassifier) -> None:
    found = _committed(cases, graph, retriever, cond)
    if found is None:
        pytest.skip(f"no dev plan under {cond}")
    scored, out, eid, planted = found
    fe = next(f for f in scored.fault_events if f.fault_event_id == eid)
    want = CLASS_REASON[fe.fault_class]
    for reason in [*REASONS, "", "bogus"]:
        r = classifier.classify_case(scored, out, verifier_flags=[f"ANY:{planted}:{reason}"])
        assert r.fault_event_committed_citation[eid] and r.fault_event_matches_clause[eid]
        assert r.fault_event_matches[eid] == (reason == want), reason  # invalid/missing reason: never primary
    other = classifier.classify_case(scored, out, verifier_flags=[f"ANY:OTHER-C9-001#cl-1:{want}"])
    assert not other.fault_event_matches[eid] and not other.fault_event_matches_clause[eid]  # wrong clause


def test_pilot_pattern_clause_named_on_content_grounds_is_not_a_primary_catch(
        cases: list[BenchmarkCase], graph: SupersessionGraph, retriever: LocalRetriever,
        classifier: FailureClassifier) -> None:
    """Dev pilot 2026-10-02 (qwen2.5:7b, S-swap): the planted superseded clause named with an arithmetic objection."""
    found = _committed(cases, graph, retriever, "S-swap")
    assert found is not None
    scored, out, eid, planted = found
    _, _, _, flags = parse_verdict({"verdict": "FLAG", "findings": [{
        "clause_id": planted, "reason": "content_or_arithmetic",
        "rationale": "cumulative capacity exceeds 50% of DT capacity"}]})
    r = classifier.classify_case(scored, out, verifier_flags=flags)
    assert r.fault_event_committed[eid]
    assert r.fault_event_matches_clause[eid] and not r.fault_event_matches[eid]
    rec = {"case_id": scored.case_id, "cluster_clause_id": "k", "verifier_flags": r.verifier_flags,
           "avoided_trap_matches": {},
           **{k: {f"{scored.case_id}#exp-S-swap": getattr(r, k)[eid]} for k in (
               "fault_event_committed", "fault_event_committed_citation", "fault_event_matches",
               "fault_event_matches_clause", "fault_event_matches_class")}}
    ev = exposure_events([rec], "S-swap")[0]
    assert ev["caught_clause"] and not ev["caught"]  # a wrong-reason catch in the analysis
    assert not _validity_flagged(rec)  # content_or_arithmetic is not a validity-reason false alarm
    assert _validity_flagged({"verifier_flags": [f"ANY:{planted}:not_in_force"]})
    assert not _validity_flagged({"verifier_flags": [f"F3:{planted}"]})  # pre-D32 flag: no reason


def test_arm5_critique_passes_the_reason_through() -> None:
    gen = Arm2ExecutionResult(case_id="x", arm_id="Arm-2", decision="APPROVED", is_approved=True, cited_rules=[],
                              root_cause=None, blocking_stage=None, subsidy_amount_inr=None, computed=[],
                              tool_outputs={}, retrieved_chunks=[], retrieved_chunk_ids=[], latency_sec=0.0,
                              prompt_tokens=0, completion_tokens=0, raw_output={})
    findings = [{"class": "ANY", "clause_id": "A#cl-1", "reason": "not_in_force", "rationale": "r"}]
    ver = VerifierResult(case_id="x", verifier_id="Arm-3", independence_config="000", verdict="FLAG", is_flagged=True,
                         flagged_faults=["ANY:A#cl-1:not_in_force"], audit_reason="r", latency_sec=0.0,
                         prompt_tokens=0, completion_tokens=0, raw_output={}, findings=findings)
    assert "not_in_force" in critique_block(gen, ver)
