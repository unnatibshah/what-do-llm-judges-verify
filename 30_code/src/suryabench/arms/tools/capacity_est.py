"""Deterministic capacity estimator for distribution transformer (DT) saturation limits."""

from dataclasses import dataclass


@dataclass
class DtCapacityEvaluationResult:
    """Evaluation output for distribution transformer solar hosting capacity."""

    is_feasible: bool
    dt_capacity_kva: float
    cumulative_solar_kw: float
    permissible_limit_kw: float
    saturation_pct: float
    statutory_cap_pct: float
    spare_headroom_kw: float
    excess_kw: float
    state: str
    rejection_reason: str | None = None


def evaluate_dt_capacity(
    dt_capacity_kva: float | None,
    cumulative_solar_kw: float | None,
    state: str = "MH",
) -> DtCapacityEvaluationResult:
    """Evaluate distribution transformer capacity headroom against statutory limits.

    Statutory Caps:
    - Maharashtra (MERC Grid-Interactive Solar Regulations cl 5.2): 70.0% of DT rated capacity.
    - Rajasthan (RERC Grid-Interactive Solar Regulations cl 6.1): 80.0% (and 85.0% amended).
    """
    if dt_capacity_kva is None or cumulative_solar_kw is None:
        return DtCapacityEvaluationResult(
            is_feasible=False,
            dt_capacity_kva=0.0,
            cumulative_solar_kw=0.0,
            permissible_limit_kw=0.0,
            saturation_pct=0.0,
            statutory_cap_pct=70.0,
            spare_headroom_kw=0.0,
            excess_kw=0.0,
            state=state,
            rejection_reason="Distribution transformer rating or cumulative solar capacity telemetry is unrecorded.",
        )

    # Determine statutory cap by jurisdiction
    cap_pct = 70.0 if state.upper() == "MH" else 80.0
    permissible_kw = round(dt_capacity_kva * (cap_pct / 100.0), 2)
    saturation = round((cumulative_solar_kw / dt_capacity_kva) * 100.0, 2)

    if cumulative_solar_kw > permissible_kw:
        excess = round(cumulative_solar_kw - permissible_kw, 2)
        return DtCapacityEvaluationResult(
            is_feasible=False,
            dt_capacity_kva=dt_capacity_kva,
            cumulative_solar_kw=cumulative_solar_kw,
            permissible_limit_kw=permissible_kw,
            saturation_pct=saturation,
            statutory_cap_pct=cap_pct,
            spare_headroom_kw=0.0,
            excess_kw=excess,
            state=state,
            rejection_reason=(
                f"Cumulative solar capacity ({cumulative_solar_kw} kW) on distribution transformer "
                f"exceeds the permissible statutory ceiling limit of {cap_pct}% ({permissible_kw} kW on {dt_capacity_kva} kVA DT). "
                f"Transformer is overloaded by {excess} kW."
            ),
        )

    headroom = round(permissible_kw - cumulative_solar_kw, 2)
    return DtCapacityEvaluationResult(
        is_feasible=True,
        dt_capacity_kva=dt_capacity_kva,
        cumulative_solar_kw=cumulative_solar_kw,
        permissible_limit_kw=permissible_kw,
        saturation_pct=saturation,
        statutory_cap_pct=cap_pct,
        spare_headroom_kw=headroom,
        excess_kw=0.0,
        state=state,
        rejection_reason=None,
    )
