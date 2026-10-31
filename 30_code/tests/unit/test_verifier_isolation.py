"""Unit tests for verifier isolation and zero-leakage security invariants."""

import json

import pytest

from suryabench.arms.arm2_agent import Arm2ExecutionResult
from suryabench.arms.verify_independent import execute_verify_independent
from suryabench.arms.verify_reflect import execute_verify_reflect
from suryabench.arms.verify_shared import execute_verify_shared
from suryabench.cases.schema import BenchmarkCase
from suryabench.gate0.retriever import LocalRetriever, build_corpus_chunks
from suryabench.graph.schema import SupersessionGraph
from suryabench.paths import BENCHMARK_DIR, CORPUS_DIR


@pytest.fixture(scope="module")
def sample_case() -> BenchmarkCase:
    with open(BENCHMARK_DIR / "dev_cases_60.json", encoding="utf-8") as f:
        cases_data = json.load(f)
    # Find a case with non-empty fault_events
    for c in cases_data:
        if c.get("fault_events"):
            return BenchmarkCase.model_validate(c)
    return BenchmarkCase.model_validate(cases_data[0])


@pytest.fixture(scope="module")
def unlabelled_case(sample_case: BenchmarkCase) -> BenchmarkCase:
    return sample_case.model_copy(
        update={
            "fault_events": [],
            "expected_answer": None,
            "failure_class_probed": None,
            "non_fault_opportunities": [],
        }
    )


@pytest.fixture(scope="module")
def dummy_gen_result(sample_case: BenchmarkCase) -> Arm2ExecutionResult:
    return Arm2ExecutionResult(
        case_id=sample_case.case_id,
        arm_id="Arm-2",
        decision="APPROVED",
        is_approved=True,
        cited_rules=["IN-C1-001#cl-4.1"],
        root_cause=None,
        blocking_stage=None,
        subsidy_amount_inr=60000.0,
        computed=[],
        tool_outputs={},
        retrieved_chunks=["Sample regulatory text chunk"],
        retrieved_chunk_ids=["IN-C1-001#chk-0000"],
        latency_sec=0.1,
        prompt_tokens=100,
        completion_tokens=20,
        raw_output={},
    )


@pytest.fixture(scope="module")
def graph() -> SupersessionGraph:
    with open(CORPUS_DIR / "graph" / "supersession.json", encoding="utf-8") as f:
        return SupersessionGraph.model_validate(json.load(f))


@pytest.fixture(scope="module")
def retriever() -> LocalRetriever:
    chunks = build_corpus_chunks(CORPUS_DIR / "text")
    return LocalRetriever(chunks)


def test_verify_shared_isolation_assertion(sample_case: BenchmarkCase, dummy_gen_result: Arm2ExecutionResult) -> None:
    """Ensure execute_verify_shared raises AssertionError if case contains fault_events."""
    assert len(sample_case.fault_events) > 0, "Test fixture requires a case with fault_events"
    with pytest.raises(AssertionError, match="Isolation breach"):
        execute_verify_shared(case=sample_case, generator_result=dummy_gen_result, model="mock")


def test_verify_reflect_isolation_assertion(sample_case: BenchmarkCase, dummy_gen_result: Arm2ExecutionResult) -> None:
    """Ensure execute_verify_reflect raises AssertionError if case contains fault_events."""
    assert len(sample_case.fault_events) > 0
    with pytest.raises(AssertionError, match="Isolation breach"):
        execute_verify_reflect(case=sample_case, generator_result=dummy_gen_result, model="mock")


def test_verify_independent_isolation_assertion(
    sample_case: BenchmarkCase,
    dummy_gen_result: Arm2ExecutionResult,
    retriever: LocalRetriever,
    graph: SupersessionGraph,
) -> None:
    """Ensure execute_verify_independent raises AssertionError if case contains fault_events."""
    assert len(sample_case.fault_events) > 0
    with pytest.raises(AssertionError, match="Isolation breach"):
        execute_verify_independent(
            case=sample_case,
            generator_result=dummy_gen_result,
            retriever=retriever,
            independence_config="100-neutral",
            model="mock",
        )


def test_verifiers_execute_safely_on_unlabelled_case(
    unlabelled_case: BenchmarkCase,
    dummy_gen_result: Arm2ExecutionResult,
    retriever: LocalRetriever,
    graph: SupersessionGraph,
) -> None:
    """Ensure all verifiers run without error when ground truth is correctly stripped."""
    res_shared = execute_verify_shared(
        case=unlabelled_case,
        generator_result=dummy_gen_result,
        model="mock",
    )
    assert res_shared.case_id == unlabelled_case.case_id
    assert res_shared.verdict in {"PASS", "FLAG"}

    res_reflect = execute_verify_reflect(
        case=unlabelled_case,
        generator_result=dummy_gen_result,
        model="mock",
    )
    assert res_reflect.case_id == unlabelled_case.case_id
    assert res_reflect.verdict in {"PASS", "FLAG"}

    res_indep = execute_verify_independent(
        case=unlabelled_case,
        generator_result=dummy_gen_result,
        retriever=retriever,
        independence_config="100-neutral",
        model="mock",
    )
    assert res_indep.case_id == unlabelled_case.case_id
    assert res_indep.verdict in {"PASS", "FLAG"}
