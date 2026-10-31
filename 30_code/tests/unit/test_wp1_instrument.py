"""Paper A v2 instrument fixes (plan PAPER-A-V2-PLAN.md D7-D12, WP1 items 1-11)."""

import io
import json
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from suryabench.applicability.schema import ApplicabilityPredicate
from suryabench.arms import arm2_agent, llm_client
from suryabench.arms.arm1_rag import execute_arm1_rag
from suryabench.arms.arm2_agent import Arm2ExecutionResult, execute_arm2_agent
from suryabench.arms.completeness import check_rule_completeness, required_subjects
from suryabench.arms.controlled_exposure import build_exposure
from suryabench.arms.tools.calculators import (
    capacity_vs_limit,
    run_calculator,
    slab_amount,
    transformer_loading,
)
from suryabench.arms.tools.case_reader import parse_case_facsimiles
from suryabench.arms.verify_independent import (
    Registry,
    execute_registry_check,
    load_registry,
    noisy_registry,
    norm_clause_id,
    spurious_registry,
)
from suryabench.arms.verify_reflect import execute_verify_reflect
from suryabench.arms.verify_shared import execute_verify_shared, parse_verdict, verifier_task
from suryabench.cases.schema import BenchmarkCase
from suryabench.core.exceptions import InvalidModelOutput, SuryaBenchError
from suryabench.eval.failure_classifier import FailureClassifier
from suryabench.eval.runner import BenchmarkRunner, code_hash
from suryabench.gate0.retriever import LocalRetriever, build_corpus_chunks, map_chunks_to_clauses
from suryabench.graph.schema import SupersessionGraph
from suryabench.paths import BENCHMARK_DIR, CORPUS_DIR


@pytest.fixture(scope="module")
def graph() -> SupersessionGraph:
    return SupersessionGraph.model_validate_json((CORPUS_DIR / "graph" / "supersession.json").read_text(encoding="utf-8"))


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


def _gen(case_id: str, cited: list[str], retrieved: list[str] | None = None, decision: str = "APPROVED",
         stage: str | None = None) -> Arm2ExecutionResult:
    retrieved = retrieved or []
    return Arm2ExecutionResult(
        case_id=case_id, arm_id="Arm-2", decision=decision, is_approved=decision == "APPROVED", cited_rules=cited,
        root_cause=None, blocking_stage=stage, subsidy_amount_inr=0.0, computed=[], tool_outputs={},
        retrieved_chunks=["text"] * len(retrieved), retrieved_chunk_ids=retrieved, latency_sec=0.0,
        prompt_tokens=0, completion_tokens=0, raw_output={})


# --- 1. LLM client ------------------------------------------------------------------------------------
def test_routing_canary_and_strict_json(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_gemini(prompt: str, *a: Any, **k: Any) -> tuple[str, int, int]:
        seen["prompt"] = prompt
        return '```json\n{"ok": true}\n```', 1, 1

    monkeypatch.setattr(llm_client, "_call_gemini_api", fake_gemini)
    out, _, _ = llm_client.call_llm_json("hello", model="gemini-3.8-flash")
    assert out == {"ok": True} and llm_client.CANARY in seen["prompt"]
    assert llm_client._provider_for("gemma-4-31b-it", None) == "gemini"
    monkeypatch.setattr(llm_client, "_call_local_ollama", lambda *a, **k: ("not json", 1, 1))
    with pytest.raises(SuryaBenchError, match="not valid JSON"):
        llm_client.call_llm_json("x", model="qwen2.5:7b", provider="local")


def test_disk_cache_resumes_without_a_call(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SURYABENCH_LLM_CACHE", str(tmp_path))
    monkeypatch.setattr(llm_client, "_call_local_ollama", lambda *a, **k: ('{"v": 1}', 3, 4))
    assert llm_client.call_llm_json("same prompt", model="qwen2.5:7b", provider="local") == ({"v": 1}, 3, 4)

    def boom(*a: Any, **k: Any) -> Any:
        raise AssertionError("cached call must not reach the model")

    monkeypatch.setattr(llm_client, "_call_local_ollama", boom)
    assert llm_client.call_llm_json("same prompt", model="qwen2.5:7b", provider="local") == ({"v": 1}, 3, 4)


def _http_error(code: int, body: str) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("u", code, "m", {}, io.BytesIO(body.encode()))  # type: ignore[arg-type]


def test_gemini_daily_quota_and_json_mode_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("SURYABENCH_MIN_INTERVAL", "0")
    def body(*quota_ids: str) -> str:
        return json.dumps({"error": {"code": 429, "message": "You exceeded ... GenerateRequestsPerDay ...", "details": [
            {"@type": "QuotaFailure", "violations": [{"quotaId": q} for q in quota_ids]}, {"retryDelay": "0s"}]}})

    monkeypatch.setattr(llm_client.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(_http_error(429, body("GenerateRequestsPerDayPerProject"))))
    with pytest.raises(llm_client.QuotaExhausted):
        llm_client._call_gemini_api("p", "s", "gemini-3.8-flash", 0.0, 5, 3)
    assert llm_client._quota_info(body("GenerateRequestsPerMinutePerProject")) == (False, 1.0)  # per-minute: retry

    bodies: list[dict[str, Any]] = []

    class Resp(io.BytesIO):
        def __enter__(self) -> "Resp":
            return self

        def __exit__(self, *a: Any) -> None:
            return None

    def urlopen(req: Any, **_: Any) -> Any:
        bodies.append(json.loads(req.data))
        if len(bodies) == 1:
            raise _http_error(400, "JSON mode is not enabled for models/gemma-x")
        return Resp(json.dumps({"candidates": [{"content": {"parts": [{"text": '{"a": 1}'}]}}],
                                "usageMetadata": {"promptTokenCount": 2, "candidatesTokenCount": 3},
                                "modelVersion": "gemma-x-001"}).encode())

    monkeypatch.setattr(llm_client.urllib.request, "urlopen", urlopen)
    assert llm_client._call_gemini_api("p", "s", "gemma-x", 0.0, 5, 3) == ('{"a": 1}', 2, 3)
    assert "responseMimeType" in bodies[0]["generationConfig"] and "responseMimeType" not in bodies[1]["generationConfig"]
    assert llm_client.MODEL_INFO["gemma-x"]["model_version"] == "gemma-x-001"


# --- 2. Generator --------------------------------------------------------------------------------------
def test_calculators_hold_no_regulatory_values() -> None:
    assert capacity_vs_limit(5.0, 4.0, 100.0)["within_limit"] is False
    assert capacity_vs_limit(5.0, 4.0, 150.0)["within_limit"] is True  # the limit is the model's to read
    assert transformer_loading(100.0, 60.0, 5.0, 70.0)["within_limit"] is True
    assert slab_amount(3.5, [{"up_to_kw": 2, "rate_inr_per_kw": 30000}, {"up_to_kw": 3, "rate_inr_per_kw": 18000}],
                       cap_inr=78000)["amount_inr"] == 78000
    assert slab_amount(10, [{"rate_inr_per_kw": 18000}], units=2, cap_inr=None)["amount_inr"] == 360000
    assert "error" in run_calculator("nope", {}) and "error" in run_calculator("capacity_vs_limit", {"x": 1})


def test_agent_loop_binds_inputs_itself_and_reaches_a_final(monkeypatch: pytest.MonkeyPatch, retriever: LocalRetriever,
                                                            dev_cases: list[BenchmarkCase]) -> None:
    prompts: list[str] = []
    replies = iter([
        {"action": "compute", "args": {"tool": "capacity_vs_limit",
                                       "args": {"proposed_kw": 5, "reference_kw": 4, "limit_pct": 100}}},
        {"action": "corpus_search", "args": {"query": "x"}},
        {"action": "final", "args": {"decision": "rejected", "blocking_stage": "technical_feasibility",
                                     "cited_rules": ["MH-C3-001#cl-6.2"], "cfa_subsidy_inr": 0,
                                     "computed": [{"field": "sanctioned_kw", "value": 4, "inputs": {"sanctioned_load_kw": 4}}]}},
    ])
    monkeypatch.setattr(arm2_agent, "call_llm_json", lambda prompt, **_: (prompts.append(prompt) or next(replies), 1, 1))
    res = execute_arm2_agent(BenchmarkRunner._unlabelled(dev_cases[0]), retriever, model="m",
                             evidence=(["X#chk-0001"], ["[SOURCE chunk_id=X#chk-0001 | document=X | clause_ids=none]\nt"]))
    assert res.decision == "REJECTED" and res.cited_rules == ["MH-C3-001#cl-6.2"]
    assert '"within_limit": false' in prompts[1]  # the model's own numbers went into the calculator
    assert "not available" in prompts[2]  # closed evidence: corpus_search adds nothing
    assert {"field": "sanctioned_kw", "value": 4.0, "tool": "llm_direct", "inputs": {"sanctioned_load_kw": 4}} in res.computed
    assert {"subsidy_amount_inr": 0.0} in res.computed


def test_agent_sees_unreadable_cases_and_must_finish(monkeypatch: pytest.MonkeyPatch, retriever: LocalRetriever,
                                                    dev_cases: list[BenchmarkCase]) -> None:
    unreadable = next(c for c in dev_cases if parse_case_facsimiles(c.inputs).missing_fields)
    prompts: list[str] = []
    monkeypatch.setattr(arm2_agent, "call_llm_json", lambda prompt, **_: (prompts.append(prompt) or {"action": "think"}, 1, 1))
    with pytest.raises(InvalidModelOutput, match="no final decision"):  # D30
        execute_arm2_agent(BenchmarkRunner._unlabelled(unreadable), retriever, model="m", evidence=([], []))
    assert len(prompts) == arm2_agent.MAX_STEPS + 1  # no regex abstention before the model; a forced final turn
    assert "UNREADABLE" in prompts[0] or "MISSING" in prompts[0]


# --- 3. Verifier output --------------------------------------------------------------------------------
def test_verdict_parsing_and_prompt_variants() -> None:
    v, risk, findings, flags = parse_verdict({"verdict": "flag", "risk": "1.7", "findings": [
        {"class": "f3 currency", "clause_id": "IN-C1-002#cl-2", "reason": "Not in force", "rationale": "old"},
        {"class": "F4-R", "clause_id": ""}]}, taxonomy=True)
    assert (v, risk) == ("FLAG", 1.0) and flags == ["F3:IN-C1-002#cl-2:not_in_force", "F4-R::other"]
    assert findings[0]["rationale"] == "old"
    # D26: without the taxonomy ablation a finding has no class; it is matched on the clause alone
    assert parse_verdict({"verdict": "PASS", "findings": [{"class": "F3", "clause_id": "A#cl-1"}]})[3] == ["ANY:A#cl-1:other"]
    with pytest.raises(InvalidModelOutput):  # D30: no verdict is an invalid output, not a crash
        parse_verdict({"flagged_faults": ["F3"]})
    for variant in ("support", "support-p1", "support-p2", "validity"):
        assert "every class that applies" not in verifier_task(variant, True)
        assert "Fault classes" not in verifier_task(variant, False) and "F3" not in verifier_task(variant, False)
        assert "F3 Currency" in verifier_task(variant, True)
    assert "in force on the application date" in verifier_task("validity", False)
    for word in ("consumer category", "capacity range", "metering mode"):  # N7: no case dimensions named
        assert word not in verifier_task("validity", False)


def test_cross_model_verifier_uses_its_own_model(monkeypatch: pytest.MonkeyPatch, dev_cases: list[BenchmarkCase]) -> None:
    from suryabench.arms import verify_reflect, verify_shared

    models: list[str | None] = []
    reply = {"verdict": "PASS", "risk": 0.2, "findings": [], "reflection": "r"}
    monkeypatch.setattr(verify_shared, "call_llm_json", lambda prompt, model=None, **_: (models.append(model) or reply, 1, 1))
    monkeypatch.setattr(verify_reflect, "call_llm_json", lambda prompt, model=None, **_: (models.append(model) or reply, 1, 1))
    case = BenchmarkRunner._unlabelled(dev_cases[0])
    execute_verify_shared(case, _gen(case.case_id, []), model="gemini-3.8-flash", variant="validity")
    execute_verify_reflect(case, _gen(case.case_id, []), model="gemini-3.8-flash", taxonomy=False)
    assert models == ["gemini-3.8-flash"] * 3


# --- 4. Registries -------------------------------------------------------------------------------------
def test_noisy_registry_and_registry_findings(graph: SupersessionGraph, retriever: LocalRetriever,
                                              dev_cases: list[BenchmarkCase]) -> None:
    assert len(noisy_registry(graph, 0.0).edges) == len(graph.edges)
    assert noisy_registry(graph, 0.0).superseded_documents == graph.superseded_documents
    assert len(noisy_registry(graph, 0.5).edges) == len(graph.edges) - round(len(graph.edges) / 2)
    assert noisy_registry(graph, 0.5, seed=0).edges == noisy_registry(graph, 0.5, seed=0).edges
    for seed in range(5):  # D31: nested, the 50% drop set contains the 25% set at every seed
        kept25 = {(e.from_node, e.to_node, e.relation) for e in noisy_registry(graph, 0.25, seed).edges}
        kept50 = {(e.from_node, e.to_node, e.relation) for e in noisy_registry(graph, 0.5, seed).edges}
        assert kept50 <= kept25
    spur = spurious_registry(graph, 0.10, 0)
    assert len(spur.edges) - len(graph.edges) == round(len(graph.edges) * 0.10)
    assert spur.edges == spurious_registry(graph, 0.10, 0).edges and spur.edges != spurious_registry(graph, 0.10, 1).edges
    reg = Registry("reg-oracle", graph, retriever.chunk_clauses)
    mh = BenchmarkRunner._unlabelled(next(c for c in dev_cases if c.case_id.startswith("MH-")))
    res = execute_registry_check(mh, _gen(mh.case_id, ["RJ-C3-003#cl-2"]), retriever, reg)
    assert res.flagged_faults == ["F2:RJ-C3-003#cl-2:wrong_jurisdiction"] and res.verdict == "FLAG"
    inc = BenchmarkRunner._unlabelled(next(c for c in dev_cases if c.case_id.startswith("IN-C1-001")))
    stale = execute_registry_check(inc, _gen(inc.case_id, ["IN-C1-002#cl-2"]), retriever, reg)
    assert "F3:IN-C1-002#cl-2:not_in_force" in stale.flagged_faults


def test_load_registry_accepts_the_wp6_schema(tmp_path: Path) -> None:
    data = {"generated_by": "x", "nodes": [
        {"node_id": "MH-C3-001#cl-2.1(j)", "doc_id": "MH-C3-001", "jurisdiction": "MH", "clause_ref": "2.1(j)",
         "topic": "t", "snippet": "s", "effective_date": "2019-12-30", "confidence": "high"},
        {"node_id": "MH-C3-003#cl-2.1(j)", "doc_id": "MH-C3-003", "jurisdiction": "MH", "clause_ref": "2.1(j)",
         "topic": "t", "snippet": "s", "effective_date": "2023-11-16", "confidence": "high"}],
        "edges": [{"from_node": "MH-C3-001#cl-2.1(j)", "to_node": "MH-C3-003#cl-2.1(j)", "type": "supersedes",
                   "effective_date": "2023-11-16", "evidence_quote": "q", "confidence": "high"}],
        "document_supersessions": [{"doc_from": "MH-C3-001", "doc_to": "MH-C3-003", "type": "prospective_replacement_no_repeal",
                                    "evidence_quote": "q", "confidence": "high"}]}
    path = tmp_path / "r.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    from suryabench.graph.oracle import in_force

    g = load_registry(path, {"MH-C3-003": "2023-11-16"})
    assert in_force("MH-C3-001#cl-2.1(j)", "2024-01-01", g).value == "superseded"
    assert in_force("MH-C3-001#cl-2.1(j)", "2023-01-01", g).value == "in_force"
    assert g.superseded_documents == {}  # "no_repeal" is not a supersession
    assert norm_clause_id("MH-C3-001#cl-2.1(j)") == norm_clause_id("MH-C3-001#cl-2.1j")


# --- 5. Scoring ----------------------------------------------------------------------------------------
def test_decision_level_commitment_and_evidence_level_catch(graph: SupersessionGraph, predicates: list[ApplicabilityPredicate],
                                                            retriever: LocalRetriever, dev_cases: list[BenchmarkCase]) -> None:
    clf = FailureClassifier(graph=graph, chunk_clauses=retriever.chunk_clauses)
    case, plan = next((c, p) for c in dev_cases for p in [build_exposure(c, "S-swap", graph, predicates)[0]]
                      if p is not None)
    assert plan is not None and plan.fault_event is not None
    scored = case.model_copy(update={"fault_events": [*case.fault_events, plan.fault_event]})
    eid, planted = plan.fault_event.fault_event_id, plan.fault_event.gold_evidence[0]
    exp_approved = case.expected_answer.blocking_stage is None
    right = SimpleNamespace(decision="APPROVED" if exp_approved else "REJECTED",
                            blocking_stage=None if exp_approved else case.expected_answer.blocking_stage,
                            cited_rules=[planted], root_cause="", computed=[])
    flipped = SimpleNamespace(decision="REJECTED" if exp_approved else "APPROVED",
                              blocking_stage="technical_feasibility" if exp_approved else None,
                              cited_rules=[planted], root_cause="", computed=[])
    r1 = clf.classify_case(scored, right, verifier_flags=[f"F3:{planted}:not_in_force"])
    assert r1.fault_event_committed_citation[eid] and not r1.fault_event_committed[eid]  # cited, outcome not flipped
    r2 = clf.classify_case(scored, flipped, verifier_flags=[f"F3:{planted}:not_in_force"])
    assert r2.fault_event_committed[eid] and r2.fault_event_matches[eid]
    assert r2.fault_event_matches_class[eid]  # class agrees too
    r3 = clf.classify_case(scored, flipped, verifier_flags=["F3:OTHER-C9-001#cl-1:not_in_force"])
    assert not r3.fault_event_matches[eid] and not r3.fault_event_matches_class[eid]  # wrong clause: no catch
    r4 = clf.classify_case(scored, flipped, verifier_flags=[f"ANY:{planted}:not_in_force"])  # no class needed
    assert r4.fault_event_matches[eid] and not r4.fault_event_matches_class[eid]  # class agreement is secondary
    r5 = clf.classify_case(scored, flipped, verifier_flags=[f"ANY:{planted}"])  # pre-D32 flag: no reason
    assert r5.fault_event_matches_clause[eid] and not r5.fault_event_matches[eid]  # D32: clause alone is secondary


def test_empty_root_cause_counts_as_nominal(graph: SupersessionGraph, dev_cases: list[BenchmarkCase]) -> None:
    clean = next(c for c in dev_cases if c.failure_class_probed == "CLEAN" and c.expected_answer.blocking_stage is None)
    out = SimpleNamespace(decision="APPROVED", blocking_stage=None, root_cause="", computed=[],
                          cited_rules=[r.rule_id for r in clean.applicable_rules])
    res = FailureClassifier(graph=graph).classify_case(clean, out)
    assert res.outcome_correct


# --- 6. Exposure leakage skips -------------------------------------------------------------------------
def test_exposure_skips_leaky_or_unmatched_swaps(graph: SupersessionGraph, predicates: list[ApplicabilityPredicate],
                                                 dev_cases: list[BenchmarkCase]) -> None:
    case, plan = next((c, p) for c in dev_cases for p in [build_exposure(c, "S-swap", graph, predicates)[0]] if p is not None)
    assert plan is not None and plan.fault_event is not None
    planted = plan.fault_event.gold_evidence[0]
    anchor = next(r.rule_id for r in case.applicable_rules if r.rule_id not in plan.node_ids)
    leaky = {"X#chk-0001": {planted, anchor}}
    skipped, reason = build_exposure(case, "S-swap", graph, predicates, leaky)
    assert skipped is None and "also contains the anchor" in reason


# --- 7. Completeness -----------------------------------------------------------------------------------
def test_completeness_expands_chunk_citations_and_follows_the_stage(graph: SupersessionGraph, retriever: LocalRetriever,
                                                                   dev_cases: list[BenchmarkCase]) -> None:
    sub = next(c for c in dev_cases if "subsidy" in (parse_case_facsimiles(c.inputs).application_stage or "").lower())
    parsed = parse_case_facsimiles(sub.inputs)
    assert "dt_capacity_limit" not in required_subjects(parsed)
    target = next(n for n, node in graph.nodes.items() if str(node.subject) == required_subjects(parsed)[0]
                  and any(n in cl for cl in retriever.chunk_clauses.values()))
    chunk = next(cid for cid, cl in retriever.chunk_clauses.items() if target in cl)
    by_chunk = check_rule_completeness(sub.case_id, parsed, graph, [chunk], [chunk], retriever.chunk_clauses)
    assert required_subjects(parsed)[0] not in by_chunk.f4_r_subjects + by_chunk.f4_c_subjects


# --- 8. Gold isolation ---------------------------------------------------------------------------------
def test_arms_never_read_gold_fields(monkeypatch: pytest.MonkeyPatch, retriever: LocalRetriever,
                                     graph: SupersessionGraph, dev_cases: list[BenchmarkCase]) -> None:
    u = BenchmarkRunner._unlabelled(dev_cases[0])
    with pytest.raises(AssertionError, match="Isolation breach"):
        _ = u.facts.state
    with pytest.raises(AssertionError, match="Isolation breach"):
        list(u.applicable_rules)
    gen = execute_arm2_agent(u, retriever, model="mock")  # mock: the loop's final action
    execute_arm1_rag(u, retriever, model="mock")
    execute_verify_shared(u, gen, model="mock")
    execute_verify_reflect(u, gen, model="mock")
    execute_registry_check(u, gen, retriever, Registry("reg-oracle", graph, retriever.chunk_clauses))
    oracle = BenchmarkRunner._unlabelled(dev_cases[0], oracle=True)
    assert list(oracle.applicable_rules)  # Arm 2-O keeps its explicit oracle field


# --- 9. Runner ------------------------------------------------------------------------------------------
def test_code_hash_is_stable() -> None:
    h = code_hash()
    assert h == code_hash() and len(h) == 64
