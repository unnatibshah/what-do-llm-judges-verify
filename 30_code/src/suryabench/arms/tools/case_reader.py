"""Surface facsimile parser extracting structured case facts from bill, proposal, and portal."""

import re
from dataclasses import dataclass, field
from typing import Any

from suryabench.cases.schema import CaseInputs

# DISCOM -> state for every DiscomCode (core/enums.py); D25, 2026-10-01 (before: MH and RJ only, all else "IN").
DISCOM_STATE = {"MSEDCL": "MH", "JVVNL": "RJ", "AVVNL": "RJ", "JDVVNL": "RJ", "UGVCL": "GJ", "MGVCL": "GJ",
                "BESCOM": "KA", "HESCOM": "KA", "TANGEDCO": "TN", "BRPL": "DL", "TPDDL": "DL", "PVVNL": "UP",
                "MVVNL": "UP"}


@dataclass
class ParsedCaseFacts:
    """Structured parameters parsed from raw text facsimiles."""

    consumer_name: str | None = None
    consumer_no: str | None = None
    discom: str | None = None
    state: str | None = None
    consumer_category: str | None = None
    sanctioned_load_kw: float | None = None
    connected_load_kw: float | None = None
    proposed_capacity_kw: float | None = None
    inverter_rating_kva: float | None = None
    module_make: str | None = None
    almm_enlisted: bool | None = None
    dcr_compliant: bool | None = None
    metering_mode: str | None = None
    dt_capacity_kva: float | None = None
    existing_solar_kw: float | None = None
    cumulative_solar_kw: float | None = None
    application_stage: str | None = None
    case_date: str | None = None
    days_since_registration: int | None = None
    days_since_submission: int | None = None
    feasibility_outcome: str | None = None
    households: int | None = None
    cfa_claim_inr: int | None = None
    own_transformer: bool = False
    missing_fields: list[str] = field(default_factory=list)
    raw_extractions: dict[str, Any] = field(default_factory=dict)


def parse_case_facsimiles(inputs: CaseInputs) -> ParsedCaseFacts:
    """Parse electricity bill, solar EPC proposal, and DISCOM portal state text."""
    bill = inputs.bill
    proposal = inputs.proposal
    portal = inputs.portal_state

    parsed = ParsedCaseFacts()

    # 1. Parse Bill
    # Discom / Utility
    discom_match = re.search(r"ELECTRICITY DISTRIBUTION UTILITY:\s*([A-Za-z0-9\-]+)", bill)
    if discom_match:
        parsed.discom = discom_match.group(1).strip()
        parsed.state = DISCOM_STATE.get(parsed.discom.upper())
    if parsed.state is None:  # unknown DISCOM: the portal reference RTS-<state>-...
        ref = re.search(r"\bRTS-([A-Z]{2})-", portal)
        parsed.state = ref.group(1) if ref else "IN"

    # Consumer Name
    name_match = re.search(r"Billing Name:\s*([^\n\r]+)", bill)
    if name_match:
        parsed.consumer_name = name_match.group(1).strip()

    # Consumer Number
    cno_match = re.search(r"Consumer No(?: / K-No)?:\s*([A-Za-z0-9]+)", bill)
    if cno_match:
        parsed.consumer_no = cno_match.group(1).strip()

    # Tariff Category
    cat_match = re.search(r"Tariff Category:\s*([^\n\r]+)", bill)
    if cat_match:
        cat_str = cat_match.group(1).lower()
        if "residential" in cat_str or "lt-i" in cat_str or "lt-1" in cat_str:
            parsed.consumer_category = "residential"
        elif "commercial" in cat_str or "lt-ii" in cat_str:
            parsed.consumer_category = "commercial"
        elif "industrial" in cat_str:
            parsed.consumer_category = "industrial"
        else:
            parsed.consumer_category = cat_str

    # Sanctioned Load
    s_load_match = re.search(
        r"Sanctioned Load(?: / Contract Demand)?:\s*(\d+(?:\.\d+)?)\s*kW", bill, re.IGNORECASE
    )
    if s_load_match:
        parsed.sanctioned_load_kw = float(s_load_match.group(1))
    elif "[UNREADABLE" in bill or "[DATA MISSING]" in bill or "Sanctioned Load:" not in bill:
        parsed.missing_fields.append("sanctioned_load_kw")

    # Connected Load
    c_load_match = re.search(r"Connected Load:\s*(\d+(?:\.\d+)?)\s*kW", bill, re.IGNORECASE)
    if c_load_match:
        parsed.connected_load_kw = float(c_load_match.group(1))
    elif "Connected Load:" not in bill or "[DATA MISSING]" in bill:
        parsed.missing_fields.append("connected_load_kw")

    # 2. Parse Proposal
    # Proposed Capacity
    cap_match = re.search(
        r"Proposed (?:DC )?Capacity:\s*(\d+(?:\.\d+)?)\s*kWp?", proposal, re.IGNORECASE
    )
    if cap_match:
        parsed.proposed_capacity_kw = float(cap_match.group(1))
    elif "Proposed DC Capacity: [UNREADABLE" in proposal:
        parsed.missing_fields.append("proposed_capacity_kw")

    # Inverter Rating
    inv_match = re.search(r"Inverter Rating:\s*(\d+(?:\.\d+)?)\s*kVA", proposal, re.IGNORECASE)
    if inv_match:
        parsed.inverter_rating_kva = float(inv_match.group(1))

    # Modules Make
    mod_match = re.search(r"Solar PV Modules:\s*([^\n\r]+)", proposal)
    if mod_match:
        parsed.module_make = mod_match.group(1).strip()
        parsed.almm_enlisted = (
            "ALMM List-I" in parsed.module_make or "Enlisted" in parsed.module_make
        )

    if "enlistment status [UNREADABLE]" in proposal:
        parsed.almm_enlisted = None
        parsed.missing_fields.append("module_almm_status")

    claim_match = re.search(r"CFA of Rs ([\d,]+)", proposal)
    if claim_match:
        parsed.cfa_claim_inr = int(claim_match.group(1).replace(",", ""))
    hh_match = re.search(r"\((\d+) member households\)", proposal)
    if hh_match:
        parsed.households = int(hh_match.group(1))

    # DCR Cell Origin
    cell_match = re.search(r"Cell & Wafer Origin:\s*([^\n\r]+)", proposal)
    if cell_match:
        origin_str = cell_match.group(1)
        parsed.dcr_compliant = "Domestic" in origin_str or "DCR Compliant" in origin_str
        if "Imported" in origin_str or "Non-DCR" in origin_str:
            parsed.dcr_compliant = False

    # Metering Mode
    meter_match = re.search(r"Requested Interconnection Mode:\s*([^\n\r]+)", proposal)
    if meter_match:
        m_str = meter_match.group(1).lower()
        if "net metering" in m_str:
            parsed.metering_mode = "net"
        elif "net billing" in m_str:
            parsed.metering_mode = "net_billing"
        elif "gross" in m_str:
            parsed.metering_mode = "gross"

    # 3. Parse Portal State
    # Submission / Review Date
    date_match = re.search(r"(?:Application Submission Date|Date):\s*(\d{4}-\d{2}-\d{2})", portal)
    if date_match:
        parsed.case_date = date_match.group(1)

    # Workflow Stage
    stage_match = re.search(r"Current Workflow Stage:\s*([^\n\r]+)", portal)
    if stage_match:
        parsed.application_stage = stage_match.group(1).strip()

    # Transformer Rating
    dt_match = re.search(
        r"(?:Distribution )?Transformer Rating:\s*(\d+(?:\.\d+)?)\s*kVA", portal, re.IGNORECASE
    )
    if dt_match:
        parsed.dt_capacity_kva = float(dt_match.group(1))

    # Cumulative Solar Loading
    cum_match = re.search(
        r"(?:Resultant Cumulative Solar Capacity|Connected Solar on Feeder):\s*(\d+(?:\.\d+)?)\s*kW",
        portal,
        re.IGNORECASE,
    )
    if cum_match:
        parsed.cumulative_solar_kw = float(cum_match.group(1))

    reg_match = re.search(r"Days Elapsed Since Registration/Acknowledgement:\s*(\d+)", portal)
    sub_match = re.search(r"Days Elapsed Since Submission:\s*(\d+)", portal)
    if reg_match:
        parsed.days_since_registration = int(reg_match.group(1))
    if sub_match:
        parsed.days_since_submission = int(sub_match.group(1))
    if "[DATE FIELD CORRUPTED]" in portal:
        parsed.missing_fields.append("days_elapsed")
    outcome_match = re.search(r"Technical Feasibility Outcome:\s*([^\n\r]+)", portal)
    if outcome_match:
        text = outcome_match.group(1).lower()
        parsed.feasibility_outcome = "infeasible" if "not feasible" in text else (
            "feasible" if "technically feasible" in text else None)
    parsed.own_transformer = "owned by the consumer" in portal

    # Check for unrecorded / missing transformer telemetry (F9 cases)
    if (
        "NOT RECORDED" in portal
        or "UNKNOWN" in portal
        or "OFFLINE" in portal
        or "[UNRECORDED" in portal
        or "Not Available" in portal
    ):
        parsed.missing_fields.append("dt_capacity_kva")

    return parsed
