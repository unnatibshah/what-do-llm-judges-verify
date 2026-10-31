"""Deterministic Central Financial Assistance (CFA) subsidy calculator for rooftop solar."""

from dataclasses import dataclass


@dataclass
class CfaSubsidyResult:
    """Calculated Central Financial Assistance under PM Surya Ghar: Muft Bijli Yojana."""

    is_eligible: bool
    subsidy_amount_inr: float
    eligible_capacity_kw: float
    cfa_rate_breakdown: str
    scheme_name: str
    rejection_reason: str | None = None
    currency_warning: str | None = None


def calculate_cfa_subsidy(
    proposed_capacity_kw: float,
    consumer_category: str = "residential",
    dcr_compliant: bool = True,
    scheme: str = "pm_surya_ghar",
) -> CfaSubsidyResult:
    """Compute exact Central Financial Assistance (CFA) subsidy per MNRE guidelines.

    PM Surya Ghar Slabs (Clause 5(e)):
    - Up to 2 kWp: Rs 30,000 per kWp (Max Rs 60,000).
    - Additional capacity up to 3 kWp: Rs 18,000 per kWp.
    - Capacity above 3 kWp: Nil additional subsidy (Capped at exactly Rs 78,000).
    - DCR requirement: Mandatory for all residential subsidy claims.
    - Commercial/Industrial: Ineligible for Central CFA subsidy (Rs 0).
    """
    # 1. Check Consumer Category Eligibility
    if consumer_category.lower() not in {"residential", "lt-i", "lt-1", "individual"}:
        return CfaSubsidyResult(
            is_eligible=False,
            subsidy_amount_inr=0.0,
            eligible_capacity_kw=0.0,
            cfa_rate_breakdown="Nil (Commercial / Industrial ineligible for residential CFA)",
            scheme_name="PM Surya Ghar: Muft Bijli Yojana",
            rejection_reason="CFA subsidy is strictly limited to residential consumers. Commercial/Industrial connections are ineligible.",
        )

    # 2. Check DCR Compliance
    if not dcr_compliant:
        return CfaSubsidyResult(
            is_eligible=False,
            subsidy_amount_inr=0.0,
            eligible_capacity_kw=0.0,
            cfa_rate_breakdown="Nil (Non-DCR modules disqualify installation from Central CFA)",
            scheme_name="PM Surya Ghar: Muft Bijli Yojana",
            rejection_reason="Central Financial Assistance requires 100% Domestic Content Requirement (DCR) compliant cells and modules.",
        )

    # 3. Check for obsolete Phase-II scheme trap (F3)
    currency_warning = None
    if scheme.lower() in {"phase2", "phase-2", "phase_ii"}:
        currency_warning = (
            "Claiming subsidy under MNRE Phase-II (40%/20% benchmark cost) is superseded. "
            "PM Surya Ghar slabs (Rs 30,000/18,000) must govern all applications from 2024-02-13."
        )

    # 4. Calculate Slabs under PM Surya Ghar
    cap = max(0.0, proposed_capacity_kw)
    if cap <= 0.0:
        return CfaSubsidyResult(
            is_eligible=False,
            subsidy_amount_inr=0.0,
            eligible_capacity_kw=0.0,
            cfa_rate_breakdown="Nil (0 kW capacity)",
            scheme_name="PM Surya Ghar: Muft Bijli Yojana",
        )

    if cap <= 2.0:
        subsidy = cap * 30000.0
        rate_desc = f"Rs 30,000/kWp × {cap:.2f} kWp"
    elif cap <= 3.0:
        subsidy = 60000.0 + (cap - 2.0) * 18000.0
        rate_desc = f"Rs 60,000 (first 2 kWp) + Rs 18,000/kWp × {(cap - 2.0):.2f} kWp"
    else:
        # Strictly capped at Rs 78,000 for capacity > 3 kWp
        subsidy = 78000.0
        rate_desc = "Rs 78,000 (Maximum residential cap for 3 kWp and above)"

    return CfaSubsidyResult(
        is_eligible=True,
        subsidy_amount_inr=round(subsidy, 2),
        eligible_capacity_kw=min(3.0, cap),
        cfa_rate_breakdown=rate_desc,
        scheme_name="PM Surya Ghar: Muft Bijli Yojana",
        rejection_reason=None,
        currency_warning=currency_warning,
    )
