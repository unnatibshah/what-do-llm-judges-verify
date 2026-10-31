"""Structured record of the values an arm actually bound and computed.

`FailureClassifier` detects F6 (input binding) and F7 (computation) solely by
iterating `agent_output.computed`; arms that do not populate it make F6 and F7
structurally undetectable rather than merely absent. Keys are named for the
classifier's detectors, not for the gold `expected_answer.computed` schema:
F6 reads `sanctioned_kw`, F7 reads `saturation_pct` and `excess_kw`.
"""

from typing import Any

from suryabench.arms.tools.capacity_est import DtCapacityEvaluationResult
from suryabench.arms.tools.case_reader import ParsedCaseFacts
from suryabench.arms.tools.subsidy_calc import CfaSubsidyResult


def build_computed(
    parsed: ParsedCaseFacts,
    dt_res: DtCapacityEvaluationResult,
    cfa_res: CfaSubsidyResult,
) -> list[dict[str, Any]]:
    """Record the bound inputs and derived quantities for F6/F7 evaluation.

    Keys whose value is None are dropped: the classifier subtracts these against
    gold values without a None guard.
    """
    trace: dict[str, Any] = {
        "sanctioned_kw": parsed.sanctioned_load_kw,
        "proposed_kw": parsed.proposed_capacity_kw,
        "dt_capacity_kva": parsed.dt_capacity_kva,
        "cumulative_solar_kw": parsed.cumulative_solar_kw,
        "saturation_pct": dt_res.saturation_pct,
        "excess_kw": dt_res.excess_kw,
        "subsidy_amount_inr": cfa_res.subsidy_amount_inr,
    }
    return [{k: v for k, v in trace.items() if v is not None}]
