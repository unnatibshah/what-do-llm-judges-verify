"""Deterministic load calculator evaluating proposed solar capacity against sanctioned demand."""

from dataclasses import dataclass


@dataclass
class LoadEvaluationResult:
    """Evaluation output for consumer load vs proposed solar capacity."""

    is_eligible: bool
    sanctioned_load_kw: float
    connected_load_kw: float
    proposed_capacity_kw: float
    excess_kw: float
    load_enhancement_required: bool
    limiting_factor: str
    rejection_reason: str | None = None


def evaluate_load_eligibility(
    sanctioned_load_kw: float | None,
    proposed_capacity_kw: float | None,
    connected_load_kw: float | None = None,
    state: str = "MH",
) -> LoadEvaluationResult:
    """Evaluate whether proposed solar capacity complies with state sanctioned load caps.

    Rules:
    - Maharashtra (MERC cl 6.2): Proposed rooftop solar capacity cannot exceed 100% of Sanctioned Load.
    - Connected load is demand capacity, NOT the legal interconnection cap (binding to connected load is F6).
    """
    if sanctioned_load_kw is None or proposed_capacity_kw is None:
        return LoadEvaluationResult(
            is_eligible=False,
            sanctioned_load_kw=0.0,
            connected_load_kw=connected_load_kw or 0.0,
            proposed_capacity_kw=0.0,
            excess_kw=0.0,
            load_enhancement_required=False,
            limiting_factor="missing_mandatory_load_data",
            rejection_reason="Sanctioned load or proposed solar capacity is missing or unreadable.",
        )

    connected = connected_load_kw if connected_load_kw is not None else sanctioned_load_kw

    # Check capacity ceiling against sanctioned load
    if proposed_capacity_kw > sanctioned_load_kw:
        excess = round(proposed_capacity_kw - sanctioned_load_kw, 2)
        return LoadEvaluationResult(
            is_eligible=False,
            sanctioned_load_kw=sanctioned_load_kw,
            connected_load_kw=connected,
            proposed_capacity_kw=proposed_capacity_kw,
            excess_kw=excess,
            load_enhancement_required=True,
            limiting_factor="sanctioned_load_cap_exceeded",
            rejection_reason=(
                f"Proposed solar capacity ({proposed_capacity_kw} kW) exceeds consumer sanctioned load "
                f"({sanctioned_load_kw} kW). Consumer must apply for load enhancement of {excess} kW "
                f"or downsize the solar system to {sanctioned_load_kw} kW."
            ),
        )

    return LoadEvaluationResult(
        is_eligible=True,
        sanctioned_load_kw=sanctioned_load_kw,
        connected_load_kw=connected,
        proposed_capacity_kw=proposed_capacity_kw,
        excess_kw=0.0,
        load_enhancement_required=False,
        limiting_factor="within_permissible_sanctioned_load",
        rejection_reason=None,
    )
