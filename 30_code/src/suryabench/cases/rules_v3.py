"""Rule functions for the corpus-r3 clusters (GJ, KA, TN, DL, UP and new central clauses).

Same contract as `suryabench.cases.rules`: one function per authentic clause (or clause family), the
numeric parameters quoted from the clause snippet recorded in `40_data/corpus_r3/graph/supersession.json`,
and every label in the v3 candidate split comes from these functions. Every clause here is
UNVERIFIED (staging corpus r3): labels are provisional until the human annotation (ANNOTATION-PACKET.md).
"""

from suryabench.cases.rules import Verdict

# --- Distribution-transformer hosting limits (percent of transformer capacity) ------------------
# GJ-C3-003#cl-5-proviso (2020): "...shall not exceed capacity of the distribution transformer;"
# GJ-C3-001#cl-5-proviso (2016, superseded): "...shall not exceed 65% of the peak capacity of the
#   distribution transformer;"  (peak capacity read as the rating; annotators to confirm)
# KA-C5-006#cl-4 (SOP 2025) / KA-C3-001#cl-6e (2023): "...shall not exceed 80% of the rated capacity."
# TN-C5-002#cl-VII.3 (2021): "...shall not exceed 90% of the distribution transformer capacity."
# TN-C5-002#cl-VII.4 (2021): Gross metering, HT, power transformer: "shall not exceed 70% of the Power
#   Transformer capacity."
# UP-C3-002#cl-6.2 (2019): "...is not more than 75% of that DT or any other transformer."
# UP-C3-001#cl-6.2 (2015, superseded): "...shall not exceed 15 % ... of the rated capacity..."
DT_PCT = {
    "GJ-C3-003#cl-5-proviso": 100.0, "GJ-C3-001#cl-5-proviso": 65.0,
    "KA-C5-006#cl-4": 80.0, "KA-C3-001#cl-6e": 80.0,
    "TN-C5-002#cl-VII.3": 90.0, "TN-C5-001#cl-5": 90.0, "TN-C5-002#cl-VII.4": 70.0,
    "UP-C3-002#cl-6.2": 75.0, "UP-C3-001#cl-6.2": 15.0,
}


def dt_limit(rule: str, dt_kva: float, existing_kw: float, proposed_kw: float) -> Verdict:
    """Cumulative solar (existing + proposed) on the transformer against the rule's percentage."""
    cumulative = round(existing_kw + proposed_kw, 2)
    permissible = round(dt_kva * DT_PCT[rule] / 100.0, 2)
    return Verdict(ok=cumulative <= permissible, computed={
        "dt_capacity_kva": dt_kva, "cumulative_solar_kw": cumulative,
        "saturation_pct": round(cumulative / dt_kva * 100.0, 2), "permissible_kw": permissible,
        "excess_kw": round(max(0.0, cumulative - permissible), 2)})


# KA-C3-001#cl-6f (2023): plants above 150 kW connect to the 11 kV system; total capacity on the
#   feeder "shall not exceed 80% of the rated current carrying capacity of that line."
def feeder_limit(rule: str, line_loading_pct: float) -> Verdict:
    assert rule == "KA-C3-001#cl-6f", rule
    return Verdict(ok=line_loading_pct <= 80.0, computed={"line_loading_pct": line_loading_pct,
                                                          "permissible_pct": 80.0})


# --- Individual capacity --------------------------------------------------------------------------
# GJ-C3-004#cl-6.2c-i (2022): residential projects "shall be allowed irrespective of consumer
#   sanctioned load"; GJ-C3-004#cl-6.2a: net metering "for projects having capacity of 1 kW and above
#   and upto 1000 kW".
# GJ-C3-001#cl-6.2 (2016, superseded): "upto a maximum of 50% of consumer's sanctioned load/contract
#   demand"; first proviso: "not be less than 1 kW and shall not exceed 1 MW".
# GJ-C3-004#cl-6.2c-iii (2022, REC mechanism only): "allowed up to sanctioned load/contracted demand."
# UP-C3-002#cl-5.1 (2019): "shall not exceed 100% of the connected /contracted demand"; proviso:
#   "not be less than 1 kWp and shall not exceed 2 MW."
# UP-C3-001#cl-5.1 (2015, superseded): "100% of the sanctioned connected load / contract demand";
#   5.2: "more than one kilo watt peak minimum" (no upper limit).
# TN-C5-002#cl-I.2 (2021): "up to the level of sanctioned load/contracted demand up to a maximum
#   capacity of 999 KW".   TN-C5-001#cl-2 (2019, superseded): "upto 100% of his sanctioned/contracted demand."
# IN-C3-004#cl-11.4 (ROC 2021, only "where the regulations does not provide for net-metering"):
#   "loads up to five hundred Kilowatt or upto the sanctioned load, whichever is lower".
# KA-C4-001#cl-1 (05.12.2024, sanctioned load up to and inclusive of 10 kW): install "upto and inclusive
#   of 10kW and the sanctioned load of the consumer shall be enhanced automatically".
# DL-C3-001#cl-5.4 (2014): a system "of capacity higher than the sanctioned load" pays the SLD
#   differential "at the time of registration".
# DL-C3-009#cl-3.8 (2024): ground-mounted GNM/VNM "upto 5 times of Sanctioned Load ... with maximum of
#   10 MW. However, there is no capping on capacity of Rooftop Solar".
# DL-C3-004#cl-3.8 (2019, superseded): "not be less than 5 kilo Watt and more than 5000 kilo Watt."
# GJ-C3-004#cl-6.2a (2022, added 2026-10-04 for the v3 candidate): net metering "for projects having capacity of
#   1 kW and above and upto 1000 kW"; with 6.2c-ii ("No capacity restrictions upto sanctioned load/ contracted
#   demand shall be applicable for the captive consumers") no sanctioned-load cap for captive non-residential use.
# GJ-C3-003#cl-6.2 (2020, superseded by GJ-C3-004 Reg 6.2): non-residential "upto a maximum of 50% of consumer's
#   sanctioned load/contract demand" (1 kW minimum, 1 MW maximum as in the 2016 first proviso).
# The bound (lower, upper as a function of sanctioned load) each rule imposes.
def capacity(rule: str, sanctioned_kw: float, proposed_kw: float, *, sld_paid: bool = False,
             ground_mounted: bool = True) -> Verdict:
    s, p = sanctioned_kw, proposed_kw
    lower, upper = {
        "GJ-C3-004#cl-6.2c-i": (1.0, 1000.0),
        "GJ-C3-001#cl-6.2": (1.0, min(0.5 * s, 1000.0)),
        "GJ-C3-004#cl-6.2c-iii": (1.0, min(s, 1000.0)),
        "UP-C3-002#cl-5.1": (1.0, min(s, 2000.0)),
        "UP-C3-001#cl-5.1": (1.0 + 1e-9, s),
        "TN-C5-002#cl-I.2": (0.0, min(s, 999.0)),
        "TN-C5-001#cl-2": (0.0, s),
        "IN-C3-004#cl-11.4": (0.0, min(s, 500.0)),
        "KA-C4-001#cl-1": (0.0, 10.0 if s <= 10.0 else s),
        "DL-C3-001#cl-5.4": (1.0, float("inf") if sld_paid else s),
        "DL-C3-009#cl-3.8": (0.0, min(5.0 * s, 10000.0) if ground_mounted else float("inf")),
        "DL-C3-004#cl-3.8": (5.0, 5000.0),
        "GJ-C3-004#cl-6.2a": (1.0, 1000.0),
        "GJ-C3-003#cl-6.2": (1.0, min(0.5 * s, 1000.0)),
    }[rule]
    return Verdict(ok=lower <= p <= upper, computed={
        "sanctioned_load_kw": s, "proposed_capacity_kw": p,
        "max_permissible_kw": round(upper, 2) if upper != float("inf") else -1.0})


# TN-C5-002#cl-I.3a (2021, gross metering only): "...shall be 151 kWp up to a maximum capacity of 999 kW."
def gross_metering_size(rule: str, proposed_kw: float) -> Verdict:
    assert rule == "TN-C5-002#cl-I.3a", rule
    return Verdict(ok=151.0 <= proposed_kw <= 999.0, computed={"proposed_capacity_kw": proposed_kw})


# --- Technical feasibility ---------------------------------------------------------------------
# Question answered: may the application proceed past technical feasibility at the case date?
# GJ-C3-005#cl-7-proviso (2024): "upto 10 kW capacity, complete in all respect shall be deemed to have
#   been accepted without requiring technical feasibility study"; above 10 kW the Reg 7 TFR route
#   (GJ-C3-005#cl-7-row4) applies, with no deemed outcome.
# GJ-C3-001#cl-7-row4 (2016, superseded): every application goes to the field for a TFR.
# KA-C5-006#cl-4-note-ii (SOP 2025): "proposed capacity upto 150kW are considered to be deemed feasible";
#   above 150 kW KA-C3-001#cl-l-feasibility: feasibility letter "Within 10 (ten) working days" (no
#   deemed outcome).   KA-C5-001#cl-26 (2023, superseded): "The Sub-divisional officer (SDO) shall
#   verify for Technical feasibility of the installation".
# DL-C3-016#cl-g3-stage1-deemed (2026): no feasibility analysis "up to 10 kW on the same supply type";
#   DL-C3-016#cl-g3-stage1-lapse: if the licensee "fails to communicate the outcome ... within the said
#   period [15 days], the feasibility shall be deemed to have been granted".
# DL-C3-002#cl-g3.3 (2014, superseded): feasibility "within thirty (30) days" (no deemed grant).
# IN-C3-001#cl-11.7 (ROC amendment 22.02.2024): study "completed within a period of fifteen days ... failing which
#   it shall be presumed that the proposal is technically feasible".   IN-C3-002#cl-11.7 (ROC 2020, substituted):
#   "not exceeding twenty days" (no presumption of feasibility).
FEAS = {  # rule: (deemed-acceptance ceiling kW or None, study window days or None, deemed on lapse)
    "GJ-C3-005#cl-7-proviso": (10.0, None, False),
    "GJ-C3-005#cl-7-row4": (None, None, False),
    "GJ-C3-001#cl-7-row4": (None, None, False),
    "KA-C5-006#cl-4-note-ii": (150.0, None, False),
    "KA-C3-001#cl-l-feasibility": (None, None, False),
    "KA-C5-001#cl-26": (None, None, False),
    "DL-C3-016#cl-g3-stage1-deemed": (10.0, None, False),
    "DL-C3-016#cl-g3-stage1-lapse": (None, 15, True),
    "DL-C3-002#cl-g3.3": (None, 30, False),
    "IN-C3-001#cl-11.7": (None, 15, True),
    "IN-C3-002#cl-11.7": (None, 20, False),
}


def feasibility(rule: str, capacity_kw: float, days_elapsed: int, outcome: str | None,
                same_supply: bool = True) -> Verdict:
    """outcome: None (not communicated), 'feasible' or 'infeasible'."""
    deemed_kw, window, lapse = FEAS[rule]
    if deemed_kw is not None and capacity_kw <= deemed_kw and (same_supply or not rule.startswith("DL")):
        ok = True
    elif deemed_kw is not None:
        ok = False  # the deemed clause does not reach this application: it is not decided by it
    elif outcome is not None:
        ok = outcome == "feasible"
    else:
        ok = bool(lapse and window is not None and days_elapsed > window)
    return Verdict(ok=ok, computed={"capacity_kw": capacity_kw, "days_elapsed": days_elapsed})


# --- Metering ------------------------------------------------------------------------------------
# GJ-C3-003#cl-13.5-check (2020): "Check Meters shall be mandatory for Rooftop Solar PV Systems having
#   capacity more than 20 kW."   GJ-C3-001#cl-13.5-check (2016): same 20 kW.
# KA-C5-006#cl-18 (SOP 2025): "check meter shall be provided for DSPV systems of capacity more than 50kWp."
# KA-C5-001#cl-15 (2023, superseded): "...for SRTPV systems capacity of more than 17.5 kW."
CHECK_METER_KW = {"GJ-C3-003#cl-13.5-check": 20.0, "GJ-C3-001#cl-13.5-check": 20.0,
                  "KA-C5-006#cl-18": 50.0, "KA-C5-001#cl-15": 17.5}


def check_meter(rule: str, capacity_kw: float, check_meter_provided: bool) -> Verdict:
    thr = CHECK_METER_KW[rule]
    return Verdict(ok=check_meter_provided or capacity_kw <= thr,
                   computed={"capacity_kw": capacity_kw, "check_meter_threshold_kw": thr})


# GJ-C3-003#cl-13.5-class (2020): "The main Solar Meter and Net Meter shall be of 1.0 and 0.5S or better
#   class accuracy".   GJ-C3-001#cl-13.5-class (2016, superseded): "main Solar Meters shall be of 0.2s
#   class accuracy".  Accuracy class index: smaller is better.
def meter_class(rule: str, solar_class: float, net_class: float) -> Verdict:
    if rule == "GJ-C3-003#cl-13.5-class":
        ok = solar_class <= 1.0 and net_class <= 0.5
    elif rule == "GJ-C3-001#cl-13.5-class":
        ok = solar_class <= 0.2
    else:
        raise KeyError(rule)
    return Verdict(ok=ok, computed={"solar_meter_class": solar_class, "net_meter_class": net_class})


# --- Connectivity voltage level -----------------------------------------------------------------
# KA-C3-001#cl-6a (2023): "1. Upto 5kW 230V-Single Phase 2. Above 5kW and upto 150kW 400V- Three Phase
#   3. Above 150kW and upto 2000kW 11kV HT"
# KA-C3-001#cl-6a-2016-quoted (2016 Reg 6(a) as quoted, superseded): "... Above 5kW and upto 50kW 400V-
#   Three Phase 3. Above 50kW and upto 2000kW 11kV HT"
# TN-C5-001#cl-3 (2019): "For load exceeding 4 kW upto 112 KW , the voltage level is 415V, three phase."
VOLTAGE_BANDS = {  # rule: [(upper kW, level)], levels: LT-1ph, LT-3ph, HT
    "KA-C3-001#cl-6a": [(5.0, "LT-1ph"), (150.0, "LT-3ph"), (2000.0, "HT")],
    "KA-C3-001#cl-6a-2016-quoted": [(5.0, "LT-1ph"), (50.0, "LT-3ph"), (2000.0, "HT")],
    "TN-C5-001#cl-3": [(4.0, "LT-1ph"), (112.0, "LT-3ph"), (2000.0, "HT")],
}


def voltage_level(rule: str, capacity_kw: float, requested: str) -> Verdict:
    required = next(level for upper, level in VOLTAGE_BANDS[rule] if capacity_kw <= upper)
    # up to the single-phase band the consumer may also opt for three phase (TN: "at the option")
    ok = requested == required or (required == "LT-1ph" and requested == "LT-3ph" and rule.startswith("TN"))
    return Verdict(ok=ok, computed={"capacity_kw": capacity_kw, "required_level": required == "HT"})


# --- ALMM List-II (solar PV cells) for net-metering projects -------------------------------------
# IN-C2-013#cl-1b (04.08.2026): "For Net-Metering & Open Access Projects, if commissioned by 31.12.2026,
#   the projects are exempt from ALMM List-ll for solar cells, else not."
# IN-C2-013#cl-1b-giu: residential 'Give It Up' net-metering cases via the PMSG National Portal "be
#   exempted ... till the end of the scheme period, i.e., 31st March 2027".
# IN-C2-013#cl-1e: List-I and List-II "shall not apply to behind-the-meter solar power plants solely used
#   for captive consumption" (non-government).
# IN-C2-012#cl-3 (18.07.2026): net-metering projects "commissioned after 31st December, 2026, will be
#   required to comply with the ALMM List-ll provisions."
# IN-C2-008#cl-8 (28.07.2025, superseded for net metering): projects "commissioned on or after 1st June
#   2026, shall have to mandatorily source ... solar PV cells from ALMM List-Il."
def almm_list2(rule: str, commission_date: str, cells_list2: bool, giu_residential: bool = False,
               behind_the_meter: bool = False) -> Verdict:
    if rule == "IN-C2-013#cl-1b":
        cutoff = "2027-03-31" if giu_residential else "2026-12-31"
        ok = cells_list2 or behind_the_meter or commission_date <= cutoff
    elif rule == "IN-C2-013#cl-1b-giu":
        ok = cells_list2 or commission_date <= "2027-03-31"
    elif rule == "IN-C2-013#cl-1e":
        ok = True  # treats the project as behind-the-meter captive: no ALMM at all
    elif rule == "IN-C2-012#cl-3":
        ok = cells_list2 or commission_date <= "2026-12-31"
    elif rule in ("IN-C2-008#cl-8", "IN-C2-011#cl-7"):
        ok = cells_list2 or commission_date < "2026-06-01"
    else:
        raise KeyError(rule)
    return Verdict(ok=ok, computed={"list2_cells": cells_list2, "almm_list2_mandatory": not ok})


# --- PM Surya Ghar: Phase-II claim window -----------------------------------------------------------
# IN-C1-001#cl-annex1-ii-amended (OM 318/140/2024, 07.07.2025): Phase-II applications "admissible for CFA
#   if claim is received till 31.12.2025"; "Applications submitted but not installed as on 01.04.2025
#   shall be ineligible for CFA".
# IN-C1-011#cl-annex-phase2-claims (07.06.2024, superseded): "admissible for CFA if the claim is received
#   till October 2024. The claims received after October 2024 will not be entertained."
# IN-C1-001#cl-phase2-pmsg-split: applications "on and after 13th Feb 2024" are PM Surya Ghar
#   applications, outside the Phase-II window rule.
def phase2_claim(rule: str, application_date: str, claim_date: str, installed_by_2025_04_01: bool) -> Verdict:
    phase2 = application_date < "2024-02-13"
    if rule == "IN-C1-001#cl-annex1-ii-amended":
        ok = claim_date <= "2025-12-31" and installed_by_2025_04_01
    elif rule == "IN-C1-011#cl-annex-phase2-claims":
        ok = claim_date <= "2024-10-31"
    elif rule == "IN-C1-001#cl-phase2-pmsg-split":
        ok = not phase2  # a PM Surya Ghar application is not subject to the Phase-II window
    else:
        raise KeyError(rule)
    return Verdict(ok=ok, computed={"phase2_application": phase2, "claim_admissible": ok})


# --- UP augmentation charge --------------------------------------------------------------------------
# UP-C3-002#cl-6.2-proviso2 (2019): "if augmentation of transformer/distribution network is required,
#   then up to total 10 kWp solar rooftop installation, the consumer would not pay any charge except to a
#   one time charge computed at the rate of Rs 1000 per kWp on the capacity beyond 10 KWp".
def up_augmentation(rule: str, capacity_kw: float, augmentation_required: bool, paid_inr: int) -> Verdict:
    assert rule == "UP-C3-002#cl-6.2-proviso2", rule
    due = int(round(1000 * max(0.0, capacity_kw - 10.0))) if augmentation_required else 0
    return Verdict(ok=paid_inr >= due, computed={"augmentation_charge_due_inr": due, "paid_inr": paid_inr})


# --- Delhi VNM/GNM guidelines, Seventh Amendment (DL-C3-015, 20.01.2026; added 2026-10-04) ------------------
# DL-C3-015#cl-3.2: VNM "shall be applicable for all consumers of NCT of Delhi".
# DL-C3-006#cl-3.2 (2020, substituted): VNM for "consumers under domestic category", charitable/non-profit
#   institutions not covered under domestic, "offices of Government /Local Authorities" and MMKABY generators.
VNM_ELIGIBLE_2020 = {"domestic", "charitable", "government"}


def vnm_applicability(rule: str, consumer_type: str) -> Verdict:
    """consumer_type: domestic, charitable, government, commercial or industrial."""
    if rule == "DL-C3-015#cl-3.2":
        ok = True
    elif rule == "DL-C3-006#cl-3.2":
        ok = consumer_type in VNM_ELIGIBLE_2020
    else:
        raise KeyError(rule)
    return Verdict(ok=ok, computed={"vnm_eligible": ok})


# DL-C3-015#cl-9.2b: change the credit share or add participating connections "twice in the financial year with
#   an advance notice of two months".   DL-C3-004#cl-9.2b (2019, substituted): "once in the financial year with an
#   advance notice of two months".
VNM_CHANGES_PER_FY = {"DL-C3-015#cl-9.2b": 2, "DL-C3-004#cl-9.2b": 1}


def vnm_change(rule: str, changes_this_fy: int, notice_months: float) -> Verdict:
    """A request to change shares or add participants, given the changes already made this financial year."""
    ok = changes_this_fy < VNM_CHANGES_PER_FY[rule] and notice_months >= 2
    return Verdict(ok=ok, computed={"changes_already_this_fy": changes_this_fy, "notice_months": notice_months})


# DL-C3-015#cl-3.6: the SLD and network-augmentation waiver for VNM/GNM "will be effective till cumulative capacity
#   doesn't exceed 110 MW, 100 MW, 30 MW and 10 MW for BRPL, TPDDL, BYPL and NDMC respectively"; first proviso:
#   "applicable on 11kV and below Network only".   DL-C3-009#cl-3.6 (2024, substituted): "75 MW, 50 MW, 30 MW and
#   10 MW".
SLD_WAIVER_MW = {"DL-C3-015#cl-3.6": {"BRPL": 110.0, "TPDDL": 100.0},
                 "DL-C3-009#cl-3.6": {"BRPL": 75.0, "TPDDL": 50.0}}


def sld_waiver(rule: str, discom: str, cumulative_mw: float, sld_paid: bool, upto_11kv: bool = True) -> Verdict:
    """May a VNM/GNM project proceed past registration: SLD paid, or waived (11 kV and below, cap not exceeded)?"""
    waived = upto_11kv and cumulative_mw <= SLD_WAIVER_MW[rule][discom]
    return Verdict(ok=sld_paid or waived, computed={"cumulative_vnm_gnm_mw": cumulative_mw, "sld_waived": waived})
