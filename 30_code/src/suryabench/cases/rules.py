"""Per-clause rule functions: the single source of every benchmark label.

Each function encodes one authentic clause, with its numeric parameters quoted
from the clause text recorded in `corpus/graph/supersession.json`. The case
generator never types a decision by hand. It calls these functions (for the
governing rule and, for trap cases, for the superseded or out-of-state rule)
and asserts that each trap actually changes the outcome.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Verdict:
    """Outcome of applying one rule to one scenario."""

    ok: bool  # True: the application may proceed on this rule
    computed: dict[str, float | int | bool]


# --- Distribution-transformer hosting limits -------------------------------------
# MH-C3-001#cl-5.2: "...shall not exceed 70% of its rated capacity."
# RJ-C3-003#cl-2 (substituted 6.1, 2023): "...shall not exceed 80% of the capacity..."
# RJ-C3-002#cl-6.1 (2021, superseded): "...shall not exceed 50% of the capacity..."
DT_CAP_PCT = {"MH-C3-001#cl-5.2": 70.0, "RJ-C3-003#cl-2": 80.0, "RJ-C3-002#cl-6.1": 50.0}


def dt_limit(rule: str, dt_kva: float, existing_kw: float, proposed_kw: float) -> Verdict:
    """Cumulative solar on the transformer (existing + proposed) against the rule's % cap."""
    cap_pct = DT_CAP_PCT[rule]
    cumulative = existing_kw + proposed_kw
    permissible = round(dt_kva * cap_pct / 100.0, 2)
    return Verdict(
        ok=cumulative <= permissible,
        computed={
            "dt_capacity_kva": dt_kva,
            "cumulative_solar_kw": cumulative,
            "saturation_pct": round(cumulative / dt_kva * 100.0, 2),
            "permissible_kw": permissible,
            "excess_kw": round(max(0.0, cumulative - permissible), 2),
        },
    )


# --- Individual capacity versus sanctioned load ----------------------------------
# MH-C3-001#cl-6.2: "...shall not exceed the Sanctioned load (in kW) or the Contract Demand..."
# RJ-C3-002#cl-7.2: "...shall not exceed 100% of the Sanctioned Load/Contract Demand..."
# RJ-C3-001#cl-3.1 (2015, superseded): "...shall not be more than 80% of the sanctioned
#   connected load/contract demand..."
LOAD_CAP_PCT = {"MH-C3-001#cl-6.2": 100.0, "RJ-C3-002#cl-7.2": 100.0, "RJ-C3-001#cl-3.1": 80.0}


def load_limit(rule: str, sanctioned_kw: float, proposed_kw: float) -> Verdict:
    """Proposed capacity against the rule's percentage of sanctioned load."""
    permissible = round(sanctioned_kw * LOAD_CAP_PCT[rule] / 100.0, 2)
    return Verdict(
        ok=proposed_kw <= permissible,
        computed={
            "sanctioned_load_kw": sanctioned_kw,
            "proposed_capacity_kw": proposed_kw,
            "max_permissible_kw": permissible,
            "load_excess_kw": round(max(0.0, proposed_kw - permissible), 2),
        },
    )


# --- Net-metering eligibility ceiling ---------------------------------------------
# MH-C3-001#cl-2.1j: "Eligible Consumer" uses "a Renewable Energy Generating System having a
#   capacity less than 1 MW" (net billing exempt by proviso).
# RJ-C3-004#cl-12 (07.02.2024): net metering "for loads upto one megawatt (01 MW) or upto the
#   sanctioned load/contract demand, whichever is lower".
def net_metering_eligible(rule: str, proposed_kw: float) -> Verdict:
    limit = {"MH-C3-001#cl-2.1j": 1000.0, "RJ-C3-004#cl-12": 1000.0}[rule]
    ok = proposed_kw < limit if rule.startswith("MH") else proposed_kw <= limit
    return Verdict(ok=ok, computed={"proposed_capacity_kw": proposed_kw, "net_metering_limit_kw": limit})


# --- Technical feasibility timelines ---------------------------------------------
# Question answered: may the applicant proceed (feasibility granted, deemed or presumed)?
# MH-C3-002 Annexure-1 cl. c (2024): study "within a period of (15) days ... failing which it
#   shall be presumed that the proposal is technically feasible"; proviso: "upto 10 kW capacity,
#   complete in all respects shall be deemed to have been accepted without requiring technical
#   feasibility study".
# RJ-C3-005 reg 8.8 (2024 Second Amendment): same 15-day presumption and 10 kW deemed acceptance.
# MH-C3-001 Annexure-1 cl. c (2019, superseded): study "within 15 working days"; no presumption.
# RJ-C3-002 reg 8.8 (2021, superseded): check "Within twenty (20) days"; no presumption.
FEASIBILITY = {
    # rule: (study window in days, presumption on expiry, deemed acceptance threshold kW)
    "MH-C3-002#cl-annex1-c": (15, True, None),
    "MH-C3-002#cl-annex1-c-proviso": (None, False, 10.0),
    "RJ-C3-005#cl-8.8": (15, True, None),
    "RJ-C3-005#cl-8.8-proviso": (None, False, 10.0),
    "MH-C3-001#cl-annex1-c": (15, False, None),
    "RJ-C3-002#cl-8.8": (20, False, None),
}


def feasibility(rule: str, capacity_kw: float, days_elapsed: int, outcome: str | None) -> Verdict:
    """outcome: None (no reply from the licensee), 'feasible', or 'infeasible'."""
    window, presumed, deemed_kw = FEASIBILITY[rule]
    if deemed_kw is not None:  # proviso: complete applications up to the threshold
        ok = capacity_kw <= deemed_kw
    elif outcome is not None:
        ok = outcome == "feasible"
    else:
        ok = bool(presumed and window is not None and days_elapsed > window)
    return Verdict(ok=ok, computed={"capacity_kw": capacity_kw, "days_elapsed": days_elapsed})


# --- Central Financial Assistance (PM Surya Ghar) ---------------------------------
# IN-C1-001#cl-4.1: "Rs 30,000/kWp" first 2 kWp; "Rs 18,000/kWp" additional 1 kWp;
#   "No additional CFA" beyond 3 kWp.
# IN-C1-001#cl-4.gh: GHS/RWA common facilities "up to 500 kWp (@3 kWp per house)", Rs 18,000/kWp.
# Superseded Phase-II rates (IN-C1-002#cl-2; rupee values as tabulated in IN-C1-001):
#   Rs 14,588/kW up to 3 kW, Rs 7,294/kW thereafter up to 10 kW.
def cfa_amount(rule: str, capacity_kw: float, households: int = 0) -> int:
    """CFA entitlement in INR under the named rule."""
    if rule == "IN-C1-001#cl-4.1":
        return int(30000 * min(capacity_kw, 2.0) + 18000 * max(0.0, min(capacity_kw, 3.0) - 2.0))
    if rule == "IN-C1-001#cl-4.gh":
        return int(18000 * min(capacity_kw, 500.0, 3.0 * households))
    if rule == "IN-C1-002#cl-2":
        return int(14588 * min(capacity_kw, 3.0) + 7294 * max(0.0, min(capacity_kw, 10.0) - 3.0))
    raise KeyError(rule)


def cfa_claim(rule: str, capacity_kw: float, claimed_inr: int, households: int = 0) -> Verdict:
    """A claim is admissible when it does not exceed the entitlement under the rule."""
    entitled = cfa_amount(rule, capacity_kw, households)
    return Verdict(
        ok=claimed_inr <= entitled,
        computed={"subsidy_amount_inr": entitled, "claimed_cfa_inr": claimed_inr},
    )


# --- Equipment conditions ----------------------------------------------------------
# IN-C1-001#cl-5.1m: DCR modules are "an essential condition for the installation to be
#   eligible for the CFA".
# IN-C2-002#cl-1 (29.03.2024): ALMM for solar PV modules "shall accordingly come into effect
#   from 1st April, 2024".
# IN-C2-003#cl-1 (15.02.2024, superseded): the 09.02.2024 re-imposition "is hereby held in
#   abeyance till further orders".
def dcr_condition(dcr_modules: bool, subsidy_claimed: bool) -> Verdict:
    return Verdict(ok=dcr_modules or not subsidy_claimed, computed={"dcr_compliant": dcr_modules})


def almm_condition(rule: str, almm_listed: bool, case_date: str) -> Verdict:
    if rule == "IN-C2-002#cl-1":
        mandatory = case_date >= "2024-04-01"
    elif rule == "IN-C2-003#cl-1":
        mandatory = False  # re-imposition held in abeyance
    else:
        raise KeyError(rule)
    return Verdict(ok=almm_listed or not mandatory, computed={"almm_mandatory": mandatory})
