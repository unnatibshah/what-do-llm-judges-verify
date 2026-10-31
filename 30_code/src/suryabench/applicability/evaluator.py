"""Deterministic evaluator for applicability predicates over CaseFacts."""

from enum import Enum
from typing import Any

from suryabench.applicability.schema import (
    ApplicabilityPredicate,
    CaseFacts,
    Condition,
    ConditionGroup,
    ConditionLeaf,
)
from suryabench.core.exceptions import PredicateEvaluationError


def _normalize_value(val: Any) -> Any:
    """Normalize enum instances to their string values."""
    if isinstance(val, Enum):
        return val.value
    return val


def _evaluate_leaf(leaf: ConditionLeaf, facts: CaseFacts) -> bool:
    """Evaluate a single leaf comparison against CaseFacts."""
    if not hasattr(facts, leaf.field):
        raise PredicateEvaluationError(
            f"Condition references unknown field '{leaf.field}' on CaseFacts"
        )

    actual_raw = getattr(facts, leaf.field)
    actual = _normalize_value(actual_raw)
    target = _normalize_value(leaf.value)

    # If the case facts omit this field, comparisons generally evaluate to False
    if actual is None:
        if leaf.op == "eq":
            return target is None
        if leaf.op == "neq":
            return target is not None
        return False

    if leaf.op == "eq":
        if isinstance(actual, int | float) and isinstance(target, int | float):
            return abs(float(actual) - float(target)) < 1e-6
        return bool(actual == target)

    if leaf.op == "neq":
        if isinstance(actual, int | float) and isinstance(target, int | float):
            return abs(float(actual) - float(target)) >= 1e-6
        return bool(actual != target)

    if leaf.op == "in":
        target_list = [_normalize_value(x) for x in target]
        return actual in target_list

    if leaf.op == "not_in":
        target_list = [_normalize_value(x) for x in target]
        return actual not in target_list

    if leaf.op == "gt":
        return float(actual) > float(target)

    if leaf.op == "gte":
        return float(actual) >= float(target) - 1e-6

    if leaf.op == "lt":
        return float(actual) < float(target)

    if leaf.op == "lte":
        return float(actual) <= float(target) + 1e-6

    raise PredicateEvaluationError(f"Unsupported operator: '{leaf.op}'")


def evaluate_condition(condition: Condition, facts: CaseFacts) -> bool:
    """Recursively evaluate a Condition (leaf or group) against CaseFacts."""
    if isinstance(condition, ConditionLeaf):
        return _evaluate_leaf(condition, facts)

    if isinstance(condition, ConditionGroup):
        if condition.all is not None:
            return all(evaluate_condition(c, facts) for c in condition.all)
        if condition.any is not None:
            return any(evaluate_condition(c, facts) for c in condition.any)
        raise PredicateEvaluationError("ConditionGroup must specify either 'all' or 'any'")

    # In case condition was parsed as a dict
    if isinstance(condition, dict):
        if "all" in condition and condition["all"] is not None:
            return all(evaluate_condition(c, facts) for c in condition["all"])
        if "any" in condition and condition["any"] is not None:
            return any(evaluate_condition(c, facts) for c in condition["any"])
        if "field" in condition and "op" in condition:
            return _evaluate_leaf(ConditionLeaf.model_validate(condition), facts)

    raise PredicateEvaluationError(f"Invalid condition type: {type(condition)}")


def evaluate_predicate(predicate: ApplicabilityPredicate, facts: CaseFacts) -> bool:
    """Determine whether an applicability predicate applies to given case facts."""
    return evaluate_condition(predicate.applies_when, facts)
