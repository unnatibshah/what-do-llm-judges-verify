"""Integration test suite for experimental arms 0–4, oracle, verifiers, and tools.

Validates:
1. Deterministic tool computations (load, DT capacity, ALMM, CFA subsidy).
2. Arm 0 symbolic rule execution.
3. Arm 1 RAG generator execution and telemetry.
4. Arm 2 tool-augmented agent execution.
5. Arm 2-O diagnostic oracle execution.
6. Arm 3 shared-evidence verifier (I=000).
7. Arm 3-Reflect 2-pass reflection verifier.
8. Arm 4 independent verifier (configs 100 & 111).
9. Completeness checking mechanism (F4-R and F4-C).
10. TestSplitGuard enforcement and RunManifest reproducibility.
"""

import json

import pytest

from suryabench.arms.arm0_rules import Arm0DecisionTree
from suryabench.arms.arm1_rag import execute_arm1_rag
from suryabench.arms.arm2_agent import execute_arm2_agent
from suryabench.arms.arm2o_oracle import execute_arm2o_oracle
from suryabench.arms.completeness import check_rule_completeness
from suryabench.arms.tools.almm_lookup import check_almm_and_dcr
from suryabench.arms.tools.capacity_est import evaluate_dt_capacity
from suryabench.arms.tools.case_reader import parse_case_facsimiles
from suryabench.arms.tools.load_calc import evaluate_load_eligibility
from suryabench.arms.tools.subsidy_calc import calculate_cfa_subsidy
from suryabench.arms.verify_independent import execute_verify_independent
from suryabench.arms.verify_reflect import execute_verify_reflect
from suryabench.arms.verify_shared import execute_verify_shared
from suryabench.cases.schema import BenchmarkCase
from suryabench.core.enums import ExpectedDecision, IndependenceConfig
from suryabench.core.exceptions import TestSplitAccessViolation
from suryabench.core.guard import TestSplitGuard
from suryabench.eval.manifest import RunManifest
from suryabench.gate0.retriever import LocalRetriever, build_corpus_chunks
from suryabench.graph.schema import SupersessionGraph
from suryabench.paths import BENCHMARK_DIR, CORPUS_DIR

DEV_CASES_PATH = BENCHMARK_DIR / "dev_cases_60.json"
GRAPH_PATH = CORPUS_DIR / "graph" / "supersession.json"
TEXT_DIR = CORPUS_DIR / "text"


@pytest.fixture(scope="module")
def dev_cases() -> list[BenchmarkCase]:
    """Load development split cases."""
    assert DEV_CASES_PATH.exists()
    data = json.loads(DEV_CASES_PATH.read_text(encoding="utf-8"))
    return [BenchmarkCase.model_validate(c) for c in data]


@pytest.fixture(scope="module")
def graph() -> SupersessionGraph:
    """Load supersession graph."""
    assert GRAPH_PATH.exists()
    data = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    return SupersessionGraph.model_validate(data)


@pytest.fixture(scope="module")
def retriever() -> LocalRetriever:
    """Build local retriever from corpus text chunks."""
    chunks = build_corpus_chunks(TEXT_DIR)
    return LocalRetriever(chunks)


# 1. Deterministic Tools Tests
def test_tools_execution() -> None:
    """Validate that domain calculators return deterministic values."""
    # Load calc
    res_load_ok = evaluate_load_eligibility(sanctioned_load_kw=5.0, proposed_capacity_kw=4.0)
    assert res_load_ok.is_eligible is True
    assert res_load_ok.excess_kw == 0.0

    res_load_fail = evaluate_load_eligibility(sanctioned_load_kw=3.0, proposed_capacity_kw=5.0)
    assert res_load_fail.is_eligible is False
    assert res_load_fail.excess_kw == 2.0
    assert res_load_fail.load_enhancement_required is True

    # Subsidy calc (PM Surya Ghar slabs)
    cfa_2kw = calculate_cfa_subsidy(2.0, "residential", True)
    assert cfa_2kw.subsidy_amount_inr == 60000.0

    cfa_3kw = calculate_cfa_subsidy(3.0, "residential", True)
    assert cfa_3kw.subsidy_amount_inr == 78000.0

    cfa_5kw = calculate_cfa_subsidy(5.0, "residential", True)
    assert cfa_5kw.subsidy_amount_inr == 78000.0  # Capped at 78k

    cfa_comm = calculate_cfa_subsidy(5.0, "commercial", True)
    assert cfa_comm.is_eligible is False
    assert cfa_comm.subsidy_amount_inr == 0.0

    # DT Capacity calc (70% cap in MH)
    dt_ok = evaluate_dt_capacity(dt_capacity_kva=100.0, cumulative_solar_kw=65.0, state="MH")
    assert dt_ok.is_feasible is True
    assert dt_ok.spare_headroom_kw == 5.0

    dt_fail = evaluate_dt_capacity(dt_capacity_kva=100.0, cumulative_solar_kw=73.0, state="MH")
    assert dt_fail.is_feasible is False
    assert dt_fail.excess_kw == 3.0

    # ALMM lookup
    almm_ok = check_almm_and_dcr("Waaree 540W Mono-PERC", True, "2024-06-15")
    assert almm_ok.is_compliant is True

    almm_fail = check_almm_and_dcr("Unlisted Imported Tier-1", True, "2024-06-15")
    assert almm_fail.is_compliant is False


# 2. Case Reader Facsimile Parsing
def test_case_reader(dev_cases: list[BenchmarkCase]) -> None:
    """Validate that case_reader extracts parameters from surface facsimiles."""
    case = dev_cases[0]
    parsed = parse_case_facsimiles(case.inputs)
    assert parsed.sanctioned_load_kw is not None
    assert parsed.proposed_capacity_kw is not None
    assert parsed.consumer_name is not None
    assert len(parsed.missing_fields) == 0


# 3. Arm 0: Symbolic Rule Tree Execution
def test_arm0_execution(dev_cases: list[BenchmarkCase], graph: SupersessionGraph) -> None:
    """Validate Arm 0 symbolic decision tree across clean and fault dev cases."""
    arm0 = Arm0DecisionTree(graph=graph)

    # Clean case
    clean_case = next(c for c in dev_cases if c.failure_class_probed == "CLEAN")
    out_clean = arm0.evaluate_case(clean_case)
    assert out_clean.decision == ExpectedDecision.ANSWER
    assert out_clean.blocking_stage is None

    # Abstention case (F9)
    f9_case = next(c for c in dev_cases if c.failure_class_probed == "F9")
    out_f9 = arm0.evaluate_case(f9_case)
    assert out_f9.decision == ExpectedDecision.ABSTAIN
    assert "F9" in (out_f9.abstention_reason or "")


# 4. Arm 1: RAG Generator
def test_arm1_rag_execution(dev_cases: list[BenchmarkCase], retriever: LocalRetriever) -> None:
    """Validate Arm 1 single-turn RAG execution and telemetry."""
    case = dev_cases[0]
    res1 = execute_arm1_rag(case=case, retriever=retriever, model="mock")
    assert res1.case_id == case.case_id
    assert res1.arm_id == "Arm-1"
    assert len(res1.retrieved_chunks) > 0
    assert res1.latency_sec >= 0.0


# 5. Arm 2: Tool-Augmented Agent
def test_arm2_agent_execution(dev_cases: list[BenchmarkCase], retriever: LocalRetriever) -> None:
    """Validate Arm 2 tool-augmented execution with tool outputs."""
    case = dev_cases[0]
    res2 = execute_arm2_agent(case=case, retriever=retriever, model="mock")
    assert res2.case_id == case.case_id
    assert res2.arm_id == "Arm-2"
    assert res2.tool_outputs["steps"][-1] == {"action": "final"}
    assert res2.retrieved_chunk_ids  # the loop's initial retrieval


# 6. Arm 2-O: Diagnostic Oracle
def test_arm2o_oracle_execution(dev_cases: list[BenchmarkCase], graph: SupersessionGraph,
                                retriever: LocalRetriever) -> None:
    """Validate Arm 2-O: the agent on the decisive clauses, rendered as retrieved chunks."""
    from suryabench.gate0.retriever import map_chunks_to_clauses

    retriever.chunk_clauses = map_chunks_to_clauses(retriever.chunks, graph.nodes.values(), CORPUS_DIR / "text")
    case = dev_cases[0]
    reso = execute_arm2o_oracle(case=case, graph=graph, retriever=retriever, model="mock")
    assert reso.case_id == case.case_id
    assert reso.arm_id == "Arm-2-O"
    shown = set().union(*(retriever.chunk_clauses.get(i, {i}) for i in reso.retrieved_chunk_ids))
    assert {r.rule_id for r in case.applicable_rules} <= shown


# 7. Verifier Arms: Arm 3 (000), Arm 3-Reflect, and Arm 4 (111)
def test_verifiers_execution(
    dev_cases: list[BenchmarkCase],
    retriever: LocalRetriever,
    graph: SupersessionGraph,
) -> None:
    """Validate Arm 3 shared verifier, Arm 3-Reflect, and Arm 4 independent verifier."""
    # Verifiers only ever see unlabelled cases (as the runner passes them).
    case = dev_cases[0].model_copy(update={"fault_events": [], "non_fault_opportunities": []})
    gen_res = execute_arm1_rag(case=case, retriever=retriever, model="mock")

    # Arm 3 (Shared 000)
    v3 = execute_verify_shared(case=case, generator_result=gen_res, model="mock")
    assert v3.verifier_id == "Arm-3"
    assert v3.independence_config == "000"
    assert v3.verdict in {"PASS", "FLAG"}

    # Arm 3-Reflect
    v3_ref = execute_verify_reflect(case=case, generator_result=gen_res, model="mock")
    assert v3_ref.verifier_id == "Arm-3-Reflect"
    assert "000-reflect" in v3_ref.independence_config

    # Arm 4 (Independent retrieval, neutral query)
    v4 = execute_verify_independent(
        case=case,
        generator_result=gen_res,
        retriever=retriever,
        independence_config="100-neutral",
        model="mock",
    )
    assert v4.verifier_id == "Arm-4-Independent"
    assert v4.independence_config == "100-neutral"
    assert v4.verdict in {"PASS", "FLAG"}


# 8. Completeness Checker (F4-R and F4-C): affirmative, never reads gold labels
def test_completeness_checker(dev_cases: list[BenchmarkCase], graph: SupersessionGraph) -> None:
    """The checklist is built from the application documents + registry; omissions split into F4-R / F4-C."""
    from suryabench.arms.tools.case_reader import parse_case_facsimiles

    case = next(c for c in dev_cases if c.case_id.startswith("MH-")
                and "feasibility" in (parse_case_facsimiles(c.inputs).application_stage or "").lower())
    blind = {"case_id": "X", "parsed": parse_case_facsimiles(case.inputs), "graph": graph, "chunk_clauses": {}}

    res_r = check_rule_completeness(retrieved_chunk_ids=[], cited_rules=[], **blind)
    assert "dt_capacity_limit" in res_r.checklist and "dt_capacity_limit" in res_r.f4_r_subjects
    assert any(f.startswith("F4-R:dt_capacity_limit:") and "MH-C3-001#cl-5.2" in f for f in res_r.flags)

    # Retrieved (chunk maps to the clause) but not cited -> F4-C
    res_c = check_rule_completeness(
        retrieved_chunk_ids=["MH-C3-001#chk-0042"], cited_rules=[],
        **{**blind, "chunk_clauses": {"MH-C3-001#chk-0042": {"MH-C3-001#cl-5.2"}}},
    )
    assert "dt_capacity_limit" in res_c.f4_c_subjects

    # Cited -> subject covered, by clause id or by the chunk that contains it
    res_ok = check_rule_completeness(retrieved_chunk_ids=[], cited_rules=["MH-C3-001#cl-5.2"], **blind)
    assert "dt_capacity_limit" not in res_ok.f4_r_subjects + res_ok.f4_c_subjects
    res_chunk = check_rule_completeness(
        retrieved_chunk_ids=[], cited_rules=["MH-C3-001#chk-0042"],
        **{**blind, "chunk_clauses": {"MH-C3-001#chk-0042": {"MH-C3-001#cl-5.2"}}},
    )
    assert "dt_capacity_limit" not in res_chunk.f4_r_subjects + res_chunk.f4_c_subjects


# 9. TestSplitGuard Interception
def test_test_split_guard() -> None:
    """Assert that TestSplitGuard strictly blocks unauthorized access to test cases."""
    with pytest.raises(TestSplitAccessViolation):
        TestSplitGuard.verify_access(BENCHMARK_DIR / "test_cases_100.json")


# 10. RunManifest Schema Serialization
def test_run_manifest() -> None:
    """Validate that execution telemetry can be captured in a compliant RunManifest."""
    manifest = RunManifest(
        run_id="run-test-001",
        corpus_hash="abcdef0123456789",
        benchmark_hash="95484953ad4dfb8b",
        model_id="qwen2.5-7b",
        seed=42,
        temperature=0.0,
        independence_config=IndependenceConfig.I111,
        arm_id="arm4",
        timestamp="2026-09-22T12:00:00Z",
    )
    dumped = manifest.model_dump_json()
    loaded = RunManifest.model_validate_json(dumped)
    assert loaded.run_id == "run-test-001"
    assert loaded.independence_config == IndependenceConfig.I111
