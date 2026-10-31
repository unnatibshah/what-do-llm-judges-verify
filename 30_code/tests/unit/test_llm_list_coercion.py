"""Regression test for the cited_rules / flagged_faults type-coercion bug.

A model returning these fields as a bare string caused downstream code to
iterate characters, producing one fabricated-citation (F1) fault per character
(98 per case on dev, ~12.8k per 140-case run). See
results/diagnostics/FLAG_PATH_DIAGNOSIS.md.
"""

from suryabench.arms.llm_client import as_str_list


def test_bare_string_is_not_iterated_per_character() -> None:
    prose = "1. Physical Site Inspection, 2. 30-Day Feasibility Period"
    out = as_str_list(prose)
    assert out == ["1. Physical Site Inspection", "2. 30-Day Feasibility Period"]
    assert len(out) < 10, "a bare string must not expand to one element per character"


def test_list_passes_through_cleaned() -> None:
    assert as_str_list(["MH-C3-001#cl-5.2", " IN-C1-001#cl-4.1 "]) == [
        "MH-C3-001#cl-5.2",
        "IN-C1-001#cl-4.1",
    ]


def test_null_and_empty() -> None:
    assert as_str_list(None) == []
    assert as_str_list("") == []
    assert as_str_list([None, "", "  "]) == []


def test_non_list_scalar() -> None:
    assert as_str_list(42) == ["42"]
