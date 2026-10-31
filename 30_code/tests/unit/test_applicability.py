"""Unit tests for ApplicabilityPredicate and deterministic evaluator."""

import json
from pathlib import Path

import pytest

from suryabench.applicability.evaluator import evaluate_condition, evaluate_predicate
from suryabench.applicability.schema import (
    ApplicabilityPredicate,
    CaseFacts,
    ConditionGroup,
    ConditionLeaf,
)
from suryabench.core.enums import (
    ConsumerCategory,
    DiscomCode,
    MeteringMode,
    StateCode,
)
from suryabench.core.exceptions import PredicateEvaluationError
from suryabench.paths import CORPUS_DIR

FIXTURE_APPLICABILITY_PATH = (
    Path(__file__).parents[1] / "fixtures" / "corpus" / "graph" / "applicability.json"
)


def _load_fixture_predicates() -> list[ApplicabilityPredicate]:
    with open(FIXTURE_APPLICABILITY_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return [ApplicabilityPredicate.model_validate(p) for p in data]


def test_load_live_corpus_predicates() -> None:
    """Test loading and validating the live corpus applicability predicates if they exist."""
    live_pred_path = CORPUS_DIR / "graph" / "applicability.json"
    if not live_pred_path.exists():
        pytest.skip("Live corpus predicates not yet populated")

    with open(live_pred_path, encoding="utf-8") as f:
        data = json.load(f)

    predicates = [ApplicabilityPredicate.model_validate(p) for p in data]
    assert len(predicates) >= 10


def test_fixture_predicates_evaluation() -> None:
    """Test that fixture predicates evaluate correctly against matching and non-matching facts."""
    predicates = _load_fixture_predicates()
    pred_mh = next(p for p in predicates if p.node_id == "MH-C3-002#cl-3")
    pred_cfa = next(p for p in predicates if p.node_id == "IN-C1-001#cl-4.1")

    # Matching MH residential net-metered consumer
    matching_facts = CaseFacts(
        state=StateCode.MH,
        discom=DiscomCode.MSEDCL,
        consumer_category=ConsumerCategory.RESIDENTIAL,
        metering_mode=MeteringMode.NET,
        proposed_capacity_kw=12.0,
        sanctioned_load_kw=15.0,
        subsidy_claimed=True,
    )
    assert evaluate_predicate(pred_mh, matching_facts) is True
    assert evaluate_predicate(pred_cfa, matching_facts) is True

    # Near-miss applicability trap (F5): Gross metering instead of net metering
    gross_facts = matching_facts.model_copy(update={"metering_mode": MeteringMode.GROSS})
    assert evaluate_predicate(pred_mh, gross_facts) is False
    assert evaluate_predicate(pred_cfa, gross_facts) is True

    # Cross-jurisdiction distractor (F2): Rajasthan instead of Maharashtra
    rj_facts = matching_facts.model_copy(update={"state": StateCode.RJ})
    assert evaluate_predicate(pred_mh, rj_facts) is False


def test_condition_operators() -> None:
    """Test individual leaf operators: eq, neq, in, not_in, gt, gte, lt, lte."""
    facts = CaseFacts(
        state=StateCode.MH,
        consumer_category=ConsumerCategory.RESIDENTIAL,
        proposed_capacity_kw=10.0,
        sanctioned_load_kw=15.0,
    )

    # eq
    assert evaluate_condition(ConditionLeaf(field="state", op="eq", value="MH"), facts) is True
    assert evaluate_condition(ConditionLeaf(field="state", op="eq", value="RJ"), facts) is False

    # neq
    assert evaluate_condition(ConditionLeaf(field="state", op="neq", value="RJ"), facts) is True

    # in
    assert (
        evaluate_condition(ConditionLeaf(field="state", op="in", value=["MH", "RJ"]), facts) is True
    )
    assert (
        evaluate_condition(ConditionLeaf(field="state", op="in", value=["KA", "TN"]), facts)
        is False
    )

    # comparisons
    assert (
        evaluate_condition(ConditionLeaf(field="proposed_capacity_kw", op="lte", value=10.0), facts)
        is True
    )
    assert (
        evaluate_condition(ConditionLeaf(field="proposed_capacity_kw", op="lt", value=10.0), facts)
        is False
    )
    assert (
        evaluate_condition(ConditionLeaf(field="sanctioned_load_kw", op="gt", value=10.0), facts)
        is True
    )


def test_nested_condition_groups() -> None:
    """Test complex ConditionGroup with nested 'all' and 'any'."""
    condition = ConditionGroup(
        all=[
            ConditionLeaf(field="state", op="eq", value="MH"),
            ConditionGroup(
                any=[
                    ConditionLeaf(field="consumer_category", op="eq", value="residential"),
                    ConditionLeaf(field="consumer_category", op="eq", value="commercial"),
                ]
            ),
        ]
    )

    facts1 = CaseFacts(state=StateCode.MH, consumer_category=ConsumerCategory.RESIDENTIAL)
    assert evaluate_condition(condition, facts1) is True

    facts2 = CaseFacts(state=StateCode.MH, consumer_category=ConsumerCategory.AGRICULTURAL)
    assert evaluate_condition(condition, facts2) is False


def test_unknown_field_raises_error() -> None:
    """Test that a condition targeting an invalid field raises PredicateEvaluationError."""
    leaf = ConditionLeaf(field="non_existent_field", op="eq", value="xyz")
    facts = CaseFacts(state=StateCode.MH, consumer_category=ConsumerCategory.RESIDENTIAL)

    with pytest.raises(PredicateEvaluationError, match="unknown field"):
        evaluate_condition(leaf, facts)
