"""Corpus-r3 validity paths (hostile review N1-N3, N6, N16; decisions D25 and D28, 2026-10-01).

Count-only: the v2 dev cases and the candidate test cases are generated in memory by their generators and
only aggregate assertions are made; no case content is printed and no model is run.
"""

import json
from types import SimpleNamespace

import pytest

from suryabench.applicability.schema import ApplicabilityPredicate
from suryabench.arms.arm2_agent import Arm2ExecutionResult
from suryabench.arms.controlled_exposure import build_exposure
from suryabench.arms.tools.case_reader import parse_case_facsimiles
from suryabench.arms.verify_independent import Registry, execute_registry_check
from suryabench.cases.generator import build_v2_dev
from suryabench.cases.generator_v3 import generate_v3_cases, load_r3_graph
from suryabench.cases.schema import BenchmarkCase
from suryabench.core.enums import CurrencyVerdict
from suryabench.corpus.manifest import load_manifest
from suryabench.eval.failure_classifier import FailureClassifier
from suryabench.gate0.retriever import LocalRetriever, build_corpus_chunks, map_chunks_to_clauses
from suryabench.graph.oracle import in_force
from suryabench.graph.schema import SupersessionGraph
from suryabench.paths import CORPUS_R3_DIR


@pytest.fixture(scope="module")
def graph() -> SupersessionGraph:
    return load_r3_graph()


@pytest.fixture(scope="module")
def retriever(graph: SupersessionGraph) -> LocalRetriever:
    text = CORPUS_R3_DIR / "text"
    chunks = build_corpus_chunks(text)
    r = LocalRetriever(chunks)  # no embeddings: registries and exposure only read the chunk -> clause map
    r.chunk_clauses = map_chunks_to_clauses(chunks, graph.nodes.values(), text)
    return r


@pytest.fixture(scope="module")
def predicates() -> list[ApplicabilityPredicate]:
    return [ApplicabilityPredicate.model_validate(p)
            for p in json.loads((CORPUS_R3_DIR / "graph" / "applicability.json").read_text(encoding="utf-8"))]


@pytest.fixture(scope="module", params=["dev_v2", "v3_candidate"])
def cases(request: pytest.FixtureRequest, graph: SupersessionGraph) -> list[BenchmarkCase]:
    return build_v2_dev() if request.param == "dev_v2" else generate_v3_cases(graph)


@pytest.fixture(scope="module")
def classifier(graph: SupersessionGraph, retriever: LocalRetriever) -> FailureClassifier:
    return FailureClassifier(graph, load_manifest(CORPUS_R3_DIR / "MANIFEST.json"), retriever.chunk_clauses)


def _gen(case: BenchmarkCase, cited: list[str]) -> Arm2ExecutionResult:
    return Arm2ExecutionResult(case_id=case.case_id, arm_id="Arm-2", decision="APPROVED", is_approved=True,
                               cited_rules=cited, root_cause=None, blocking_stage=None, subsidy_amount_inr=None,
                               computed=[], tool_outputs={}, retrieved_chunks=[], retrieved_chunk_ids=[],
                               latency_sec=0.0, prompt_tokens=0, completion_tokens=0, raw_output={})


def test_every_case_parses_to_its_true_state(cases: list[BenchmarkCase]) -> None:
    wrong = sum(parse_case_facsimiles(c.inputs).state != c.facts.state.value for c in cases)
    assert wrong == 0, f"{wrong}/{len(cases)} cases parse to the wrong state"


def test_reg_oracle_and_classifier_never_flag_a_case_own_decisive_clauses(
        cases: list[BenchmarkCase], graph: SupersessionGraph, retriever: LocalRetriever,
        classifier: FailureClassifier) -> None:
    """Condition C shows only the decisive clauses: citing them must never be an F2 or F3 finding."""
    reg = Registry("reg-oracle", graph, retriever.chunk_clauses)
    reg_hits = clf_hits = 0
    for c in cases:
        decisive = [r.rule_id for r in c.applicable_rules]
        res = execute_registry_check(c.model_copy(update={"fault_events": []}), _gen(c, decisive), retriever, reg)
        reg_hits += sum(f["class"] in {"F2", "F3"} for f in res.findings)
        out = SimpleNamespace(decision="APPROVED", blocking_stage=None, root_cause="", computed=[], cited_rules=decisive)
        clf_hits += sum(f.fault_class.value in {"F2", "F3"} and f.evidence[0] in decisive
                        for f in classifier.classify_case(c, out).detected_faults)
    assert (reg_hits, clf_hits) == (0, 0)


def test_every_exposure_plan_has_a_determinable_commitment(
        cases: list[BenchmarkCase], graph: SupersessionGraph, retriever: LocalRetriever,
        predicates: list[ApplicabilityPredicate], classifier: FailureClassifier) -> None:
    """For every S/J/A plan: a generator that cites the plant and flips the outcome is scored as committed,
    S plants are determinably superseded (N3), and no J/A plant duplicates condition C's evidence (N6)."""
    plans = undeterminable = 0
    for c in cases:
        exp_approved = c.expected_answer.blocking_stage is None
        for cond in ("S-swap", "S-both", "J", "A"):
            plan, _ = build_exposure(c, cond, graph, predicates, retriever.chunk_clauses)
            if plan is None or plan.fault_event is None:
                continue
            plans += 1
            planted = plan.fault_event.gold_evidence[0]
            if cond.startswith("S"):
                assert in_force(planted, c.facts.case_date or "", graph) in {
                    CurrencyVerdict.SUPERSEDED, CurrencyVerdict.PARTIALLY_SUPERSEDED}
            scored = c.model_copy(update={"fault_events": [*c.fault_events, plan.fault_event]})
            flipped = SimpleNamespace(decision="REJECTED" if exp_approved else "APPROVED",
                                      blocking_stage="technical_feasibility" if exp_approved else None,
                                      cited_rules=[planted], root_cause="", computed=[])
            undeterminable += not classifier.classify_case(scored, flipped).fault_event_committed[
                plan.fault_event.fault_event_id]
    assert plans > 0 and undeterminable == 0, f"{undeterminable}/{plans} plans can never be committed"
