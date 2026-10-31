"""Unit tests for SuryaBench deterministic Failure Classifier (F1–F9)."""

import json

import pytest

from suryabench.applicability.schema import CaseFacts
from suryabench.arms.arm0_rules import Arm0Output
from suryabench.cases.schema import (
    ApplicableRuleReference,
    BenchmarkCase,
    CaseInputs,
    ExpectedAnswer,
    FaultEvent,
    GroundTruthProvenance,
    NonFaultOpportunity,
)
from suryabench.core.enums import (
    ConfidenceLevel,
    ConsumerCategory,
    ExpectedDecision,
    FaultClass,
    FaultSubtype,
    StateCode,
)
from suryabench.corpus.schema import CorpusManifest
from suryabench.eval.failure_classifier import FailureClassifier
from suryabench.graph.schema import SupersessionGraph
from suryabench.paths import CORPUS_DIR

GRAPH_PATH = CORPUS_DIR / "graph" / "supersession.json"
MANIFEST_PATH = CORPUS_DIR / "MANIFEST.json"


@pytest.fixture(scope="module")
def graph() -> SupersessionGraph:
    with open(GRAPH_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return SupersessionGraph.model_validate(data)


@pytest.fixture(scope="module")
def manifest() -> CorpusManifest:
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return CorpusManifest.model_validate(data)


@pytest.fixture(scope="module")
def classifier(graph: SupersessionGraph, manifest: CorpusManifest) -> FailureClassifier:
    return FailureClassifier(graph=graph, manifest=manifest)


def make_test_case(
    case_id: str = "TEST-001",
    state: StateCode = StateCode.MH,
    sanctioned_load: float = 5.0,
    proposed_capacity: float = 4.0,
    expected_decision: ExpectedDecision = ExpectedDecision.ANSWER,
    failure_class_probed: str = "CLEAN",
    blocking_stage: str | None = None,
    applicable_rules: list[str] | None = None,
    fault_events: list[FaultEvent] | None = None,
    nfos: list[NonFaultOpportunity] | None = None,
) -> BenchmarkCase:
    rules = [
        ApplicableRuleReference(
            rule_id=r,
            clause=r.split("#")[1] if "#" in r else "1",
            effective_date="2024-06-15",
            jurisdiction=state.value,
            applicability_basis="test basis",
        )
        for r in (applicable_rules or ["MH-C3-002#cl-3"])
    ]
    return BenchmarkCase(
        case_id=case_id,
        corpus_version="v1.0",
        facts=CaseFacts(
            state=state,
            consumer_category=ConsumerCategory.RESIDENTIAL,
            sanctioned_load_kw=sanctioned_load,
            proposed_capacity_kw=proposed_capacity,
            case_date="2026-11-01",
        ),
        inputs=CaseInputs(bill="bill text", proposal="proposal text", portal_state="portal text"),
        applicable_rules=rules,
        expected_answer=ExpectedAnswer(
            blocking_stage=blocking_stage,
            root_cause="nominal_compliant" if blocking_stage is None else "capacity_exceeded",
            computed=[{"metric": "central_cfa_subsidy", "subsidy_inr": 78000.0}],
        ),
        ground_truth_provenance=GroundTruthProvenance(basis="explicit", confidence=ConfidenceLevel.HIGH),
        failure_class_probed=failure_class_probed,
        expected_decision=expected_decision,
        fault_events=fault_events or [],
        non_fault_opportunities=nfos or [],
    )


def test_f1_fabrication_detection(classifier: FailureClassifier) -> None:
    """Validate that F1 flags clauses not existing in graph or manifest."""
    case = make_test_case()
    output = Arm0Output(
        decision=ExpectedDecision.ANSWER,
        cited_rules=["NONEXISTENT-CLAUSE#cl-999"],
    )
    res = classifier.classify_case(case, output)
    assert any(f.fault_class == FaultClass.F1 for f in res.detected_faults)


def test_f2_jurisdiction_error_detection(classifier: FailureClassifier) -> None:
    """Validate that F2 flags alien state jurisdiction citations."""
    case = make_test_case(state=StateCode.MH)
    output = Arm0Output(
        decision=ExpectedDecision.ANSWER,
        cited_rules=["RJ-C3-001#cl-3.1"],
    )
    res = classifier.classify_case(case, output)
    assert any(f.fault_class == FaultClass.F2 for f in res.detected_faults)


def test_f3_currency_error_detection(classifier: FailureClassifier) -> None:
    """Validate that F3 flags superseded clauses at case date."""
    case = make_test_case(state=StateCode.MH)
    # IN-C1-002#cl-2 is superseded by IN-C1-001#cl-4.1 as of 2024-02-13
    output = Arm0Output(
        decision=ExpectedDecision.ANSWER,
        cited_rules=["IN-C1-002#cl-2"],
    )
    res = classifier.classify_case(case, output)
    assert any(f.fault_class == FaultClass.F3 for f in res.detected_faults)


def test_f4_omission_retrieval_and_citation(classifier: FailureClassifier) -> None:
    """Validate F4-R and F4-C detection."""
    case = make_test_case(applicable_rules=["MH-C3-002#cl-3", "IN-C1-001#cl-4.1"])

    # 1. F4-R: Rule never retrieved in top-k chunks
    output = Arm0Output(decision=ExpectedDecision.ANSWER, cited_rules=[])
    res_f4r = classifier.classify_case(
        case, output, retrieved_chunk_ids=["SOME_OTHER_CHUNK"]
    )
    f4_faults = [f for f in res_f4r.detected_faults if f.fault_class == FaultClass.F4]
    assert any(f.fault_subtype == FaultSubtype.F4_R for f in f4_faults)

    # 2. F4-C: Rule was retrieved in top-k (exact clause id, as Arm 2-O supplies), but omitted
    res_f4c = classifier.classify_case(
        case, output, retrieved_chunk_ids=["MH-C3-002#cl-3"]
    )
    f4_c_faults = [f for f in res_f4c.detected_faults if f.fault_subtype == FaultSubtype.F4_C]
    assert len(f4_c_faults) > 0


def test_f4_retrieval_matches_clause_not_document(graph: SupersessionGraph) -> None:
    """A chunk from the right document but not containing the clause is F4-R, not F4-C."""
    gold = "MH-C3-002#cl-3"
    clf = FailureClassifier(
        graph=graph,
        chunk_clauses={"MH-C3-002#chk-0007": {gold}, "MH-C3-002#chk-0001": set()},
    )
    case = make_test_case(applicable_rules=[gold])
    output = Arm0Output(decision=ExpectedDecision.ANSWER, cited_rules=[])

    def f4(chunk_ids: list[str]) -> set[FaultSubtype | None]:
        res = clf.classify_case(case, output, retrieved_chunk_ids=chunk_ids)
        return {f.fault_subtype for f in res.detected_faults if f.fault_class == FaultClass.F4}

    assert f4(["MH-C3-002#chk-0001"]) == {FaultSubtype.F4_R}  # same doc, wrong chunk
    assert f4(["MH-C3-002#chk-0007"]) == {FaultSubtype.F4_C}  # chunk contains the clause


def test_chunk_clause_map_locates_gold_clause(graph: SupersessionGraph) -> None:
    """The runner's chunk->clause map resolves a gold clause to chunks of its own document only."""
    from suryabench.gate0.retriever import build_corpus_chunks, map_chunks_to_clauses

    text_dir = CORPUS_DIR / "text"
    mapping = map_chunks_to_clauses(build_corpus_chunks(text_dir), graph.nodes.values(), text_dir)
    hits = [cid for cid, nodes in mapping.items() if "MH-C3-001#cl-5.2" in nodes]
    assert hits and all(cid.startswith("MH-C3-001#chk-") for cid in hits)


def test_f7_arithmetic_computation_error(classifier: FailureClassifier) -> None:
    """Validate F7 calculation mismatch detection."""
    case = make_test_case()
    output = Arm0Output(
        decision=ExpectedDecision.ANSWER,
        cited_rules=["MH-C3-002#cl-3"],
        computed=[{"metric": "central_cfa_subsidy", "subsidy_inr": 45000.0}],  # Expected 78000.0
    )
    res = classifier.classify_case(case, output)
    assert any(f.fault_class == FaultClass.F7 for f in res.detected_faults)


def test_f9_epistemic_abstention_failure(classifier: FailureClassifier) -> None:
    """Validate F9 failure when answering instead of abstaining."""
    case = make_test_case(
        expected_decision=ExpectedDecision.ABSTAIN,
        failure_class_probed="F9",
    )
    output = Arm0Output(
        decision=ExpectedDecision.ANSWER,  # Failed to abstain!
        cited_rules=["MH-C3-002#cl-3"],
    )
    res = classifier.classify_case(case, output)
    assert any(f.fault_class == FaultClass.F9 for f in res.detected_faults)
    assert res.is_correct is False


def test_unsupported_correct_detection(classifier: FailureClassifier) -> None:
    """Validate that nominally correct decision with invalid evidence is flagged as unsupported_correct."""
    case = make_test_case(
        blocking_stage="feasibility_rejected",
        failure_class_probed="F3",
    )
    # Nominally correct rejection, but cites superseded clause
    output = Arm0Output(
        decision=ExpectedDecision.ANSWER,
        blocking_stage="feasibility_rejected",
        root_cause="capacity_exceeded",
        cited_rules=["IN-C1-002#cl-2"],  # Superseded!
    )
    res = classifier.classify_case(case, output)
    assert res.is_correct is True
    assert res.unsupported_correct is True


def test_f6_reads_arm1_field_level_provenance(classifier: FailureClassifier) -> None:
    """Arm 1's LLM-bound records carry the source field and still drive F6."""
    from types import SimpleNamespace

    from suryabench.arms.arm1_rag import parse_bound_values

    records = parse_bound_values([
        {"field": "sanctioned_kw", "value": "6.0", "inputs": {"connected_load_kw": 6.0}},
        {"field": "saturation_pct", "value": "n/a"},  # malformed: dropped
        "not a record",  # malformed: dropped
    ])
    assert records == [{
        "field": "sanctioned_kw", "value": 6.0, "tool": "llm_direct",
        "inputs": {"connected_load_kw": 6.0},
    }]

    case = make_test_case(sanctioned_load=5.0)
    output = SimpleNamespace(decision="APPROVED", cited_rules=[], computed=records)
    res = classifier.classify_case(case, output)
    assert any(f.fault_class == FaultClass.F6 for f in res.detected_faults)


def test_f6_fires_on_wrong_source_field_even_when_values_coincide(classifier: FailureClassifier) -> None:
    """Connected load bound as sanctioned load is F6 even if both equal 5.0 kW."""
    from types import SimpleNamespace

    case = make_test_case(sanctioned_load=5.0)
    wrong = [{"field": "sanctioned_kw", "value": 5.0, "tool": "llm_direct", "inputs": {"connected_load_kw": 5.0}}]
    right = [{"field": "sanctioned_kw", "value": 5.0, "tool": "llm_direct", "inputs": {"sanctioned_load_kw": 5.0}}]

    def f6(records: list[dict]) -> bool:
        out = SimpleNamespace(decision="APPROVED", cited_rules=[], computed=records)
        return any(f.fault_class == FaultClass.F6 for f in classifier.classify_case(case, out).detected_faults)

    assert f6(wrong)
    assert not f6(right)


def test_f3_chunk_of_wholly_superseded_instrument(graph: SupersessionGraph) -> None:
    """Citing any chunk of an instrument superseded in full is F3 and commits that instrument's trap."""
    from types import SimpleNamespace

    clf = FailureClassifier(graph=graph)
    case = make_test_case(state=StateCode.RJ)
    case = case.model_copy(update={"fault_events": [FaultEvent(
        fault_event_id="T#fe-1", case_id=case.case_id, fault_class=FaultClass.F3, gold_trigger="t",
        gold_evidence=["RJ-C3-001#cl-3.1"], expected_behavior="b")]})
    out = SimpleNamespace(decision="APPROVED", cited_rules=["RJ-C3-001#chk-0005"])
    res = clf.classify_case(case, out)
    assert any(f.fault_class == FaultClass.F3 for f in res.detected_faults)
    assert res.fault_event_committed_citation["T#fe-1"] is True
    # primary commitment also needs the outcome to flip against the label (plan D10)
    assert res.fault_event_committed["T#fe-1"] is (not res.outcome_correct)
    # a chunk from a live document does not commit it
    res2 = clf.classify_case(case, SimpleNamespace(decision="APPROVED", cited_rules=["RJ-C3-002#chk-0005"]))
    assert res2.fault_event_committed_citation["T#fe-1"] is False


def test_f5_requires_citing_the_seeded_trap_clause(graph: SupersessionGraph) -> None:
    """In an F5 case, citing an unrelated valid clause is not F5; citing the trap clause is."""
    from types import SimpleNamespace

    clf = FailureClassifier(graph=graph)
    case = make_test_case(state=StateCode.MH, applicable_rules=["MH-C3-001#cl-2.1j"])
    case = case.model_copy(update={"failure_class_probed": "F5", "fault_events": [FaultEvent(
        fault_event_id="T#fe-1", case_id=case.case_id, fault_class=FaultClass.F5, gold_trigger="t",
        gold_evidence=["MH-C3-001#cl-6.2"], expected_behavior="b")]})

    def f5(cited: list[str]) -> bool:
        out = SimpleNamespace(decision="APPROVED", cited_rules=cited)
        return any(f.fault_class == FaultClass.F5 for f in clf.classify_case(case, out).detected_faults)

    assert f5(["MH-C3-001#cl-6.2"])  # the inapplicable clause the trap names
    assert not f5(["MH-C3-001#cl-5.2"])  # a different, valid clause
