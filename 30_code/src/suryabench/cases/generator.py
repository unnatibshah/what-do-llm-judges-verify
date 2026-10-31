"""Rule-driven backward case generation for SuryaBench (protocol §7A).

Every label comes from a rule function in `suryabench.cases.rules`, applied to the
scenario's parameters. For each trap case the generator also applies the trap rule
(a superseded predecessor for F3, another state's analogue for F2, an inapplicable
sibling clause for F5, the wrong input field for F6) and asserts the trap changes
the verdict, so every seeded fault is a real decision hazard rather than a label.
(F2 cases where both states set the same limit are citation hazards only; they are
marked in the fault trigger.)

`applicable_rules` lists the decisive clauses: the ones whose conditions settle the
case outcome. Omission cases (F4) have two decisive clauses; the fault event names
the second.

Partition per cluster (10 cases): clean approvals and clean rejections, plus the
trap types the authentic corpus supports for that clause (F2, F3, F4, F5, F6, F9,
and one multi-fault case). Where the corpus holds no authentic trap partner for a
class, that slot holds a clean boundary case instead, and per-class counts are
reported as they fall. F1 (fabricated citations) and F7 (arithmetic) are measured
from generator behaviour, not seeded. F8 needs a genuine conflict between two
authoritative current sources, which this corpus does not contain.
"""

import datetime as _dt
import hashlib
import json
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from suryabench.applicability.schema import CaseFacts
from suryabench.cases import rules
from suryabench.cases.schema import (
    ApplicableRuleReference,
    BenchmarkCase,
    CaseInputs,
    ExpectedAnswer,
    FaultEvent,
    GroundTruthProvenance,
    NonFaultOpportunity,
)
from suryabench.cases.validator import validate_benchmark_suite
from suryabench.core.enums import (
    AlmmStatus,
    ConfidenceLevel,
    ConsumerCategory,
    DiscomCode,
    ExpectedDecision,
    FaultClass,
    FaultSubtype,
    MeteringMode,
    PremisesType,
    StateCode,
)
from suryabench.graph.schema import SupersessionGraph
from suryabench.paths import BENCHMARK_DIR, CORPUS_DIR, CORPUS_R3_DIR

BENCHMARK_CORPUS_VERSION = "SuryaBench-Corpus-2026.11-r2"
# v2 dev and the candidate test split are labelled with corpus r3 (2026-10-01): every dev node is unchanged in r3.
CORPUS_VERSION_R3 = "SuryaBench-Corpus-2026.10-r3"

# Clusters (one per decisive clause), stratified by jurisdiction across the split.
# Dev clusters each carry both F5 and F6 traps so Gate 2 elicitation is testable on dev.
DEV_RULE_NODES = ["IN-C1-001#cl-4.1", "MH-C3-001#cl-6.2", "RJ-C3-003#cl-2"]
TEST_RULE_NODES = [
    "IN-C2-002#cl-1",
    "MH-C3-001#cl-5.2",
    "MH-C3-002#cl-annex1-c",
    "RJ-C3-002#cl-7.2",
    "RJ-C3-005#cl-8.8",
]

# Superseded clauses whose supersession edge is implicit (IN-C2-003 -> IN-C2-002, 29.03.2024 OM).
IMPLICIT_F3_EVIDENCE = {"IN-C2-003#cl-1"}
STAGE_TECH = "technical_feasibility"
STAGE_SUBSIDY = "subsidy_approval"
STAGE_EQUIP = "equipment_verification"
MH, RJ = StateCode.MH, StateCode.RJ
UNREADABLE_CAPACITY_KW = 3.0  # true capacity behind an unreadable proposal (F9 cases)


# ==============================================================================
# Facsimile renderers (formats are what the Arm 2 case reader parses)
# ==============================================================================
def _make_bill(
    discom_name: str, consumer_no: str, consumer_name: str, tariff: str,
    sanctioned_load: float | None, connected_load: float, case_date: str,
) -> str:
    sanctioned = f"{sanctioned_load:.1f} kW" if sanctioned_load is not None else "[UNREADABLE - smudged]"
    return "\n".join([
        f"ELECTRICITY DISTRIBUTION UTILITY: {discom_name}",
        f"Consumer No / K-No: {consumer_no}",
        f"Billing Name: {consumer_name}",
        f"Tariff Category: {tariff}",
        f"Sanctioned Load / Contract Demand: {sanctioned}",
        f"Connected Load: {connected_load:.1f} kW",
        f"Billing Cycle: Monthly (Last Meter Reading: {case_date})",
    ])


def _make_proposal(
    consumer_name: str, consumer_no: str, proposed_kw: float | None, almm: bool | None,
    dcr: bool, metering_mode: str, extra: list[str], inverter_kva: float | None = None,
) -> str:
    capacity = f"{proposed_kw:.2f} kWp" if proposed_kw is not None else "[UNREADABLE - page torn]"
    almm_text = {True: "ALMM List-I Enlisted", False: "Non-ALMM / Unlisted",
                 None: "enlistment status [UNREADABLE]"}[almm]
    return "\n".join([
        "ROOFTOP SOLAR PV SYSTEM INSTALLATION PROPOSAL",
        f"Client: {consumer_name} (Consumer ID: {consumer_no})",
        f"Proposed DC Capacity: {capacity}",
        f"Inverter Rating: {(inverter_kva or proposed_kw or 0):.2f} kVA (AC)",
        f"Solar PV Modules: Mono PERC 540W ({almm_text})",
        f"Cell & Wafer Origin: {'Domestic Cells and Wafers (DCR Compliant)' if dcr else 'Imported Cells / Non-DCR'}",
        f"Requested Interconnection Mode: {metering_mode}",
        *extra,
    ])


def _make_portal(portal: str, app_ref: str, case_date: str, status: str, details: list[str]) -> str:
    return "\n".join([
        f"UTILITY & NATIONAL SOLAR INTERCONNECTION PORTAL ({portal})",
        f"Application Reference: {app_ref}",
        f"Application Submission Date: {case_date}",
        f"Current Workflow Stage: {status}",
        *details,
    ])


# ==============================================================================
# Scenario model
# ==============================================================================
@dataclass
class Fault:
    fault_class: FaultClass
    trigger: str
    evidence: list[str]
    behavior: str


@dataclass
class Scenario:
    """One case before rendering. `ok` is the verdict of the decisive rules (None: abstain)."""

    probed: str
    state: StateCode
    case_date: str
    ok: bool | None
    stage: str
    root_cause: str
    computed: dict[str, Any]
    decisive: list[str]
    sanctioned_kw: float | None
    connected_kw: float
    category: str
    proposed_kw: float | None
    portal_status: str
    portal_details: list[str]
    almm: bool | None = True
    dcr: bool = True
    proposal_extra: list[str] = field(default_factory=list)
    premises: PremisesType = PremisesType.INDIVIDUAL
    inverter_kva: float | None = None
    subsidy_claimed: bool = False
    faults: list[Fault] = field(default_factory=list)
    abstention_reason: str | None = None
    nfos: list[tuple[str, str]] = field(default_factory=list)
    # v3 (corpus r3) rendering options; the defaults reproduce v1/v2 output exactly.
    discom: DiscomCode | None = None
    tariff: str | None = None
    metering_text: str = "Net Metering"
    metering_mode: MeteringMode = MeteringMode.NET
    confidence: ConfidenceLevel | None = None


DISCOM = {MH: DiscomCode.MSEDCL, RJ: DiscomCode.JVVNL}
NAMES = [
    "Suhas Kulkarni", "Bhawani Singh", "Meera Joshi", "Om Prakash Choudhary", "Anil Shinde",
    "Kalyan Mal Sharma", "Pradeep Deshmukh", "Sunita Rathore", "Nitin Bhalerao", "Rekha Meena",
]


def _flip(governing: bool, trap: bool, label: str) -> None:
    """A trap must change the outcome, otherwise it is not a decision hazard."""
    assert governing != trap, f"trap does not change the verdict: {label}"


def _nfo(rule: str, state: StateCode) -> list[tuple[str, str]]:
    return [("currency", f"{rule} is in force at the case date"),
            ("jurisdiction", f"{rule} governs {state.value} applications")]


# ==============================================================================
# Cluster builders (10 scenarios each)
# ==============================================================================
def _dt_scenarios(rule: str, state: StateCode, date: str, v: int, scale: int = 1) -> list[Scenario]:
    """Distribution-transformer hosting limit (MH-C3-001#cl-5.2 70%, RJ-C3-003#cl-2 80%).

    Variant 1 doubles every magnitude: the verdicts are scale-invariant (percent limits).
    """
    s = (1.0 + v) * scale
    alien = "RJ-C3-003#cl-2" if state == MH else "MH-C3-001#cl-5.2"
    load_rule = "MH-C3-001#cl-6.2" if state == MH else "RJ-C3-002#cl-7.2"
    out: list[Scenario] = []

    def mk(probed: str, dt: float, ex: float, p: float, sl: float, faults: list[Fault],
           decisive: list[str] | None = None, ok: bool | None = None, cat: str = "residential",
           dt_known: bool = True, extra: list[str] | None = None) -> None:
        v = rules.dt_limit(rule, dt, ex, p)
        load_v = rules.load_limit(load_rule, sl, p)
        verdict = (v.ok and load_v.ok) if ok is None else ok
        details = (
            [f"Distribution Transformer Rating: {dt:.0f} kVA", f"Existing Solar on Transformer: {ex:.1f} kW",
             f"Resultant Cumulative Solar Capacity: {ex + p:.1f} kW"]
            if dt_known else ["Distribution Transformer Rating: NOT RECORDED in GIS for this DT"]
        ) + (extra or [])
        out.append(Scenario(
            probed=probed, state=state, case_date=date, ok=verdict if dt_known else None, stage=STAGE_TECH,
            root_cause="dt_hosting_limit_exceeded" if not v.ok else "capacity_exceeds_sanctioned_load",
            computed=v.computed if dt_known else {}, decisive=decisive or [rule],
            sanctioned_kw=sl, connected_kw=sl, category=cat, proposed_kw=p,
            portal_status="Technical Feasibility Study", portal_details=details, faults=faults,
            abstention_reason=None if dt_known else
            "F9 missing: transformer rating needed for the hosting-limit check is not recorded",
            nfos=_nfo(rule, state),
        ))

    def f2(dt: float, ex: float, p: float) -> Fault:
        _flip(rules.dt_limit(rule, dt, ex, p).ok, rules.dt_limit(alien, dt, ex, p).ok, f"{rule} F2 {ex}")
        return Fault(FaultClass.F2, f"applying {alien} (other state) flips the hosting verdict", [alien],
                     f"Apply {rule}; {alien} does not govern {state.value}")

    f4 = Fault(FaultClass.F4, f"{load_rule} (capacity vs sanctioned load) also decides the case", [load_rule],
               f"Cite and apply {load_rule} as well as {rule}")

    def f6(dt: float, ex: float, p: float) -> Fault:
        cap = rules.DT_CAP_PCT[rule] * dt / 100.0
        _flip(ex + p <= cap, ex <= cap, f"{rule} F6 {ex}")
        return Fault(FaultClass.F6, "binding existing solar instead of the resultant cumulative loading flips the verdict",
                     ["cumulative_solar_kw"], f"Bind the resultant cumulative loading ({ex + p} kW), not existing solar ({ex} kW)")

    mk("CLEAN", 100 * s, 40 * s, 5 * s, 6 * s, [])
    mk("CLEAN", 315 * s, 150 * s, 60 * s, 80 * s, [], cat="commercial")
    limit = rules.DT_CAP_PCT[rule]
    # existing solar below the limit, resultant cumulative above it
    mk("F6", 100 * s, (limit - 4) * s, 6 * s, 8 * s, [f6(100 * s, (limit - 4) * s, 6 * s)])
    ex_f2 = 68.0 if state == RJ else 70.0
    mk("F2", 100 * s, ex_f2 * s, 7 * s, 8 * s, [f2(100 * s, ex_f2 * s, 7 * s)])
    mk("F4", 100 * s, 40 * s, 8 * s, 6 * s, [f4], decisive=[rule, load_rule])
    mk("F9", 100 * s, 0, 5 * s, 6 * s, [Fault(FaultClass.F9, "transformer rating not recorded", ["dt_capacity_kva"],
                                              "Abstain until the transformer rating is available")], dt_known=False)
    if state == RJ:
        old = "RJ-C3-002#cl-6.1"

        def f3(dt: float, ex: float, p: float) -> Fault:
            _flip(rules.dt_limit(rule, dt, ex, p).ok, rules.dt_limit(old, dt, ex, p).ok, f"{rule} F3 {ex}")
            return Fault(FaultClass.F3, f"superseded {old} (50%) flips the verdict", [old],
                         f"Apply {rule} (80%); {old} was substituted in 2023")

        mk("F3", 100 * s, 45 * s, 10 * s, 12 * s, [f3(100 * s, 45 * s, 10 * s)])
        mk("F3", 250 * s, 120 * s, 20 * s, 25 * s, [f3(250 * s, 120 * s, 20 * s)])
        # F5: HT consumer that owns its transformer; the 80% limit "shall not be applicable"
        proviso = "RJ-C3-003#cl-2-proviso"
        v_proviso = rules.load_limit("RJ-C3-002#cl-7.2", 100 * s, 50 * s)
        _flip(v_proviso.ok, rules.dt_limit(rule, 500 * s, 380 * s, 50 * s).ok, "RJ DT F5")
        mk("F5", 500 * s, 380 * s, 50 * s, 100 * s,
           [Fault(FaultClass.F5, "80% DT limit applied to an HT consumer's own transformer", [rule],
                  "Apply the HT own-transformer proviso; capacity is then governed by reg 7.2")],
           decisive=[proviso, "RJ-C3-002#cl-7.2"], ok=v_proviso.ok, cat="industrial",
           extra=["Connection: HT 11 kV consumer; distribution transformer installed and owned by the consumer"])
        mk("MULTI", 100 * s, 76 * s, 6 * s, 8 * s, [f6(100 * s, 76 * s, 6 * s), Fault(
            FaultClass.F2, f"{alien} (other state, same verdict here) cited", [alien], f"Apply {rule}")])
    else:  # MH: the corpus holds no authentic predecessor of reg 5.2
        mk("F2", 200 * s, 130 * s, 15 * s, 20 * s, [f2(200 * s, 130 * s, 15 * s)])
        mk("F6", 250 * s, 170 * s, 10 * s, 12 * s, [f6(250 * s, 170 * s, 10 * s)])
        mk("F4", 100 * s, 60 * s, 12 * s, 10 * s, [f4], decisive=[rule, load_rule])
        mk("MULTI", 100 * s, 68 * s, 4 * s, 3 * s, [f2(100 * s, 68 * s, 4 * s), f4], decisive=[rule, load_rule])
    return out


def _load_scenarios(rule: str, state: StateCode, date: str, v: int, scale: int = 1) -> list[Scenario]:
    """Capacity versus sanctioned load (MH-C3-001#cl-6.2, RJ-C3-002#cl-7.2). Variant 1 doubles magnitudes."""
    s = (1.0 + v) * scale
    alien = "RJ-C3-002#cl-7.2" if state == MH else "MH-C3-001#cl-6.2"
    dt_rule = "MH-C3-001#cl-5.2" if state == MH else "RJ-C3-003#cl-2"
    out: list[Scenario] = []

    def mk(probed: str, sl: float | None, cl: float, p: float, faults: list[Fault],
           decisive: list[str] | None = None, dt: tuple[float, float] | None = None,
           cat: str = "residential") -> None:
        dt = dt or (250.0 * scale, 40.0 * scale)
        v = rules.load_limit(rule, sl, p) if sl is not None else None
        dt_v = rules.dt_limit(dt_rule, dt[0], dt[1], p)
        out.append(Scenario(
            probed=probed, state=state, case_date=date, ok=None if v is None else (v.ok and dt_v.ok),
            stage=STAGE_TECH,
            root_cause="capacity_exceeds_sanctioned_load" if v is not None and not v.ok else "dt_hosting_limit_exceeded",
            computed=v.computed if v else {}, decisive=decisive or [rule],
            sanctioned_kw=sl, connected_kw=cl, category=cat, proposed_kw=p,
            portal_status="Technical Feasibility Study",
            portal_details=[f"Distribution Transformer Rating: {dt[0]:.0f} kVA",
                            f"Existing Solar on Transformer: {dt[1]:.1f} kW",
                            f"Resultant Cumulative Solar Capacity: {dt[1] + p:.1f} kW"],
            faults=faults,
            abstention_reason=None if sl is not None else "F9 missing: sanctioned load on the bill is unreadable",
            nfos=[("currency", f"{rule} is in force at the case date"),
                  ("input_binding", "Sanctioned load, not connected load, is the capacity basis")],
        ))

    def f6(sl: float, cl: float, p: float) -> Fault:
        _flip(rules.load_limit(rule, sl, p).ok, rules.load_limit(rule, cl, p).ok, f"{rule} F6 {sl}/{cl}")
        return Fault(FaultClass.F6, "binding connected load as sanctioned load flips the verdict",
                     ["sanctioned_load_kw"], f"Bind sanctioned load ({sl} kW), not connected load ({cl} kW)")

    f2 = Fault(FaultClass.F2, f"{alien} (other state, same limit) cited for the capacity limit", [alien],
               f"Apply {rule}; {alien} does not govern {state.value}")
    ceiling = "MH-C3-001#cl-2.1j" if state == MH else "RJ-C3-004#cl-12"
    sf = min(s, 2.5)  # the 1 MW ceiling trap stays a few MW; the clean cases scale past it in kW only
    big, cd = 1200 * sf, 1500 * sf
    v_ceiling = rules.net_metering_eligible(ceiling, big)
    _flip(v_ceiling.ok, rules.load_limit(rule, cd, big).ok, f"{rule} F5")
    out.append(Scenario(
        probed="F5", state=state, case_date=date, ok=v_ceiling.ok, stage="metering_mode_selection",
        root_cause="net_metering_capacity_ceiling_exceeded", computed=v_ceiling.computed, decisive=[ceiling],
        sanctioned_kw=cd, connected_kw=cd, category="industrial", proposed_kw=big,
        portal_status="Technical Feasibility Study",
        portal_details=[f"Distribution Transformer Rating: {2500 * sf:.0f} kVA", "Existing Solar on Transformer: 0.0 kW",
                        f"Resultant Cumulative Solar Capacity: {big:.1f} kW"],
        faults=[Fault(FaultClass.F5, f"{rule} (capacity vs contract demand) applied to a {big / 1000:.1f} MW "
                      "net-metering request",
                      [rule], f"Apply {ceiling}: net metering is capped at 1 MW")],
        nfos=_nfo(ceiling, state),
    ))
    mk("CLEAN", 5 * s, 5 * s, 4 * s, [])
    mk("CLEAN", 3 * s, 3 * s, 3.5 * s, [])  # clean rejection
    mk("F6", 5 * s, 8 * s, 6 * s, [f6(5 * s, 8 * s, 6 * s)])
    mk("F6", 8 * s, 5 * s, 7 * s, [f6(8 * s, 5 * s, 7 * s)])
    mk("F2", 6 * s, 6 * s, 6 * s, [f2])
    mk("F4", 6 * s, 6 * s, 5 * s, [Fault(FaultClass.F4, f"{dt_rule} (transformer limit) also decides the case", [dt_rule],
                             f"Cite and apply {dt_rule} as well as {rule}")],
       decisive=[rule, dt_rule], dt=(100.0 * s, (78.0 if state == RJ else 68.0) * s))
    mk("F9", None, 5 * s, 4 * s, [Fault(FaultClass.F9, "sanctioned load unreadable", ["sanctioned_load_kw"],
                                "Abstain until the sanctioned load is legible")])
    if state == RJ:
        old = "RJ-C3-001#cl-3.1"

        def f3(sl: float, p: float) -> Fault:
            _flip(rules.load_limit(rule, sl, p).ok, rules.load_limit(old, sl, p).ok, f"{rule} F3 {sl}")
            return Fault(FaultClass.F3, f"superseded {old} (80%) flips the verdict", [old], f"Apply {rule} (100%)")

        mk("F3", 10 * s, 10 * s, 9 * s, [f3(10 * s, 9 * s)])
        mk("MULTI", 5 * s, 4 * s, 4.6 * s, [f6(5 * s, 4 * s, 4.6 * s), f3(5 * s, 4.6 * s)])
    else:  # MH: the corpus holds no authentic predecessor of reg 6.2
        mk("CLEAN", 10 * s, 10 * s, 10 * s, [])
        mk("MULTI", 5 * s, 7 * s, 6 * s, [f6(5 * s, 7 * s, 6 * s), f2])
    return out


def _feasibility_scenarios(main: str, state: StateCode, date: str, v: int, scale: int = 1) -> list[Scenario]:
    """Feasibility study timelines and the <=10 kW deemed-acceptance proviso (2024 amendments).

    Variant 1 uses different capacities and day counts on the same sides of every threshold.
    """

    def pk(a: float, b: float) -> float:
        return a if v == 0 else b

    proviso = f"{main}-proviso"
    old = "MH-C3-001#cl-annex1-c" if state == MH else "RJ-C3-002#cl-8.8"
    alien = "RJ-C3-005#cl-8.8" if state == MH else "MH-C3-002#cl-annex1-c"
    load_rule = "MH-C3-001#cl-6.2" if state == MH else "RJ-C3-002#cl-7.2"
    out: list[Scenario] = []

    def gov(kw: float) -> str:
        return proviso if kw <= 10.0 else main

    def mk(probed: str, kw: float, days: int | None, outcome: str | None, faults: list[Fault],
           sl: float | None = None, decisive: list[str] | None = None, lag: int = 0) -> None:
        v = rules.feasibility(gov(kw), kw, days or 0, outcome)
        sanctioned = sl if sl is not None else max(kw, 12.0)
        # For <=10 kW the proviso makes the licensee carry out any sanctioned-load enhancement.
        load_ok = kw <= 10.0 or rules.load_limit(load_rule, sanctioned, kw).ok
        outcome_text = {None: "Not communicated by the licensee", "feasible": "Technically feasible",
                        "infeasible": "Not feasible: distribution transformer loading"}[outcome]
        out.append(Scenario(
            probed=probed, state=state, case_date=date, ok=None if days is None else (v.ok and load_ok),
            stage=STAGE_TECH,
            root_cause="feasibility_not_established" if load_ok else "capacity_exceeds_sanctioned_load",
            computed=v.computed if days is not None else {}, decisive=decisive or [gov(kw)],
            sanctioned_kw=sanctioned, connected_kw=sanctioned,
            category="residential" if kw <= 10 else "commercial", proposed_kw=kw,
            portal_status="Technical Feasibility",
            portal_details=[
                f"Days Elapsed Since Submission: {days + lag}" if days is not None
                else "Days Elapsed Since Submission: [DATE FIELD CORRUPTED]",
                f"Days Elapsed Since Registration/Acknowledgement: {days}" if days is not None
                else "Days Elapsed Since Registration/Acknowledgement: [DATE FIELD CORRUPTED]",
                "Application Completeness: Complete in all respects",
                f"Technical Feasibility Outcome: {outcome_text}",
            ],
            faults=faults,
            abstention_reason=None if days is not None else
            "F9 missing: the registration date needed to apply the study window is corrupted",
            nfos=[("currency", f"{gov(kw)} is in force at the case date"),
                  ("applicability", f"{gov(kw)} is the clause for a {kw} kW system")],
        ))

    def f3(kw: float, days: int) -> Fault:
        _flip(rules.feasibility(gov(kw), kw, days, None).ok, rules.feasibility(old, kw, days, None).ok,
              f"{main} F3 {kw}/{days}")
        return Fault(FaultClass.F3, f"superseded {old} (no presumption, no deemed acceptance) flips the verdict",
                     [old], f"Apply the 2024 clause {gov(kw)}")

    def f5(kw: float, days: int) -> Fault:
        wrong = main if kw <= 10.0 else proviso
        # Misapplying the proviso means treating the system as deemed accepted.
        trap_ok = True if wrong == proviso else rules.feasibility(main, kw, days, None).ok
        _flip(rules.feasibility(gov(kw), kw, days, None).ok, trap_ok, f"{main} F5 {kw}/{days}")
        return Fault(FaultClass.F5, f"{wrong} applied to a {kw} kW system it does not govern", [wrong],
                     f"Apply {gov(kw)}: the 10 kW threshold decides which clause governs")

    def f6(kw: float, days: int, lag: int) -> Fault:
        _flip(rules.feasibility(gov(kw), kw, days, None).ok, rules.feasibility(gov(kw), kw, days + lag, None).ok,
              f"{main} F6")
        return Fault(FaultClass.F6, "counting the study window from submission instead of registration flips the verdict",
                     ["days_elapsed"], f"Count from registration/acknowledgement ({days} days), not submission ({days + lag})")

    d_ok, d_wait, d_f6, lag = int(pk(20, 19)), int(pk(8, 6)), int(pk(13, 12)), int(pk(4, 5))
    mk("CLEAN", pk(12, 14), d_ok, None, [])  # presumed feasible once 15 days pass without an outcome
    mk("CLEAN", pk(15, 18), d_wait, None, [])  # still inside the study window
    mk("F6", pk(12, 13), d_f6, None, [f6(pk(12, 13), d_f6, lag)], lag=lag)
    mk("F5", pk(9.5, 8), int(pk(3, 5)), None, [f5(pk(9.5, 8), int(pk(3, 5)))])
    mk("F5", pk(10.5, 11), int(pk(4, 2)), None, [f5(pk(10.5, 11), int(pk(4, 2)))])
    mk("F3", pk(12, 16), int(pk(17, 16)), None, [f3(pk(12, 16), int(pk(17, 16)))])
    mk("F3", pk(6, 4), int(pk(2, 1)), None, [f3(pk(6, 4), int(pk(2, 1)))])
    mk("F4", pk(14, 16), d_ok, None, [Fault(FaultClass.F4, f"{load_rule} (capacity vs sanctioned load) also decides "
                                            "the case", [load_rule], f"Cite and apply {load_rule} as well as {main}")],
       sl=pk(12, 14), decisive=[main, load_rule])
    mk("F9", pk(12, 20), None, None, [Fault(FaultClass.F9, "registration date corrupted", ["days_elapsed"],
                                            "Abstain until the registration date is known")])
    mk("MULTI", pk(9, 7), int(pk(1, 0)), None, [f3(pk(9, 7), int(pk(1, 0))), f5(pk(9, 7), int(pk(1, 0))),
                             Fault(FaultClass.F2, f"{alien} (other state, same verdict here) cited", [alien],
                                   f"Apply {proviso}")])
    return out


def _cfa_scenarios(rule: str, _state: StateCode, date: str, v: int, scale: int = 1) -> list[Scenario]:
    """PM Surya Ghar CFA slabs (IN-C1-001#cl-4.1), GHS/RWA sibling row, Phase-II predecessor."""
    gh, old, dcr = "IN-C1-001#cl-4.gh", "IN-C1-002#cl-2", "IN-C1-001#cl-5.1m"
    out: list[Scenario] = []

    def mk(probed: str, state: StateCode, kw: float | None, claim: int, faults: list[Fault],
           households: int = 0, dcr_ok: bool = True, decisive: list[str] | None = None,
           inverter: float | None = None) -> None:
        governing = gh if households else rule
        v = rules.cfa_claim(governing, kw, claim, households) if kw is not None else None
        d = rules.dcr_condition(dcr_ok, True)
        extra = [f"Financial Subsidy Claim: CFA of Rs {claim:,} under PM Surya Ghar: Muft Bijli Yojana"]
        if households:
            extra.append(f"Applicant: Registered Group Housing Society / RWA ({households} member households); "
                         "system for common facilities")
        sl = max(kw or 5.0, 5.0)
        out.append(Scenario(
            probed=probed, state=state, case_date=date, ok=None if v is None else (v.ok and d.ok),
            stage=STAGE_SUBSIDY if d.ok else STAGE_EQUIP,
            root_cause="cfa_claim_exceeds_entitlement" if d.ok else "non_dcr_modules_for_cfa",
            computed=v.computed if v else {}, decisive=decisive or [governing],
            sanctioned_kw=sl, connected_kw=sl, category="residential", proposed_kw=kw,
            portal_status="Subsidy Claim Review", portal_details=["Scheme: PM Surya Ghar: Muft Bijli Yojana"],
            dcr=dcr_ok, proposal_extra=extra, subsidy_claimed=True, inverter_kva=inverter,
            premises=PremisesType.RWA_COMMON if households else PremisesType.INDIVIDUAL,
            faults=faults,
            abstention_reason=None if kw is not None else
            "F9 missing: installed capacity needed to compute the CFA is unreadable",
            nfos=[("currency", f"{governing} is in force at the case date"),
                  ("arithmetic", "The CFA entitlement follows the slab table")],
        ))

    def f3(kw: float, claim: int, households: int = 0) -> Fault:
        governing = gh if households else rule
        _flip(rules.cfa_claim(governing, kw, claim, households).ok, rules.cfa_claim(old, kw, claim).ok,
              f"CFA F3 {kw}")
        return Fault(FaultClass.F3, "superseded Phase-II rates flip the claim verdict", [old],
                     "Apply PM Surya Ghar (IN-C1-001); Phase-II was subsumed")

    def f5(kw: float, claim: int, households: int) -> Fault:
        _flip(rules.cfa_claim(gh, kw, claim, households).ok, rules.cfa_claim(rule, kw, claim).ok, f"CFA F5 {kw}")
        return Fault(FaultClass.F5, "individual residential slabs applied to a GHS/RWA", [rule],
                     "Apply the GHS/RWA row: Rs 18,000/kWp at up to 3 kWp per house, max 500 kWp")

    def pk(a: Any, b: Any) -> Any:
        return a if v == 0 else b

    dc, ac = pk(2.2, 2.4), 2.0
    claim_f6 = rules.cfa_amount(rule, dc)
    _flip(rules.cfa_claim(rule, dc, claim_f6).ok, rules.cfa_claim(rule, ac, claim_f6).ok, "CFA F6")
    mk("F6", MH, dc, claim_f6, [Fault(FaultClass.F6, f"binding inverter AC rating ({ac} kVA) instead of module capacity "
                                      f"({dc} kWp) flips the claim verdict", ["proposed_capacity_kw"],
                                      f"Bind the RTS capacity in kWp ({dc}), not the inverter rating")], inverter=ac)
    mk("CLEAN", RJ, pk(5 * scale, 1.5), pk(78000, 45000), [])
    # the installer extended the slab past 3 kWp: exceeds the Rs 78,000 cap
    mk("CLEAN", MH, pk(4 * scale, 3.5 * scale), pk(96000, 87000), [])
    for state, kw in ((RJ, pk(8, 9) * scale), (MH, pk(10, 7.8) * scale)):
        mk("F3", state, kw, rules.cfa_amount(old, kw), [f3(kw, rules.cfa_amount(old, kw))])
    for state, kw, hh in ((RJ, pk(60, 45) * scale, pk(30, 12) * scale),
                          (MH, min(pk(100, 200) * scale, 500), pk(20, 50) * scale)):
        claim = rules.cfa_amount(gh, kw, hh)
        mk("F5", state, kw, claim, [f5(kw, claim, hh)], households=hh)
    mk("F4", RJ, pk(3, 2), pk(78000, 60000), [Fault(FaultClass.F4, f"{dcr} (DCR condition) also decides the case",
                                                    [dcr], "Cite and apply the DCR condition")],
       dcr_ok=False, decisive=[rule, dcr])
    mk("F9", MH, None, 78000, [Fault(FaultClass.F9, "installed capacity unreadable", ["proposed_capacity_kw"],
                                     "Abstain until capacity is legible")])
    kw_m, hh_m = pk(40, 30) * scale, pk(10, 8) * scale
    claim_m = rules.cfa_amount(gh, kw_m, hh_m)
    mk("MULTI", RJ, kw_m, claim_m, [f5(kw_m, claim_m, hh_m), f3(kw_m, claim_m, households=hh_m)], households=hh_m)
    return out


def _almm_scenarios(rule: str, _state: StateCode, _date: str, v: int, scale: int = 1) -> list[Scenario]:
    """ALMM List-I in effect from 01.04.2024 (IN-C2-002#cl-1) vs the 15.02.2024 abeyance (IN-C2-003#cl-1)."""
    abeyance, dcr = "IN-C2-003#cl-1", "IN-C1-001#cl-5.1m"
    out: list[Scenario] = []

    def mk(probed: str, state: StateCode, date: str, almm: bool | None, faults: list[Fault],
           dcr_ok: bool = True, decisive: list[str] | None = None) -> None:
        governing = rule if date >= "2024-04-01" else abeyance
        v = rules.almm_condition(governing, bool(almm), date) if almm is not None else None
        d = rules.dcr_condition(dcr_ok, True)
        out.append(Scenario(
            probed=probed, state=state, case_date=date, ok=None if v is None else (v.ok and d.ok),
            stage=STAGE_EQUIP,
            root_cause="non_almm_modules" if v is not None and not v.ok else "non_dcr_modules_for_cfa",
            computed=v.computed if v else {}, decisive=decisive or [governing],
            sanctioned_kw=5.0, connected_kw=5.0, category="residential", proposed_kw=3.0,
            portal_status="Equipment Verification", portal_details=[f"Module Procurement Date: {date}"],
            almm=almm, dcr=dcr_ok, subsidy_claimed=True,
            proposal_extra=["Financial Subsidy Claim: CFA under PM Surya Ghar: Muft Bijli Yojana "
                            "(government-subsidised rooftop)"],
            faults=faults,
            abstention_reason=None if almm is not None else "F9 missing: module enlistment status is unreadable",
            nfos=[("currency", f"{governing} is in force at the case date"),
                  ("jurisdiction", "ALMM orders are central and govern every state")],
        ))

    def f3(date: str) -> Fault:
        _flip(rules.almm_condition(rule, False, date).ok, rules.almm_condition(abeyance, False, date).ok, "ALMM F3")
        return Fault(FaultClass.F3, "superseded abeyance OM (15.02.2024) exempts the modules", [abeyance],
                     "Apply the 29.03.2024 OM: ALMM in effect from 01.04.2024")

    def f5(date: str) -> Fault:
        _flip(rules.almm_condition(abeyance, False, date).ok, rules.almm_condition(rule, False, "2024-04-01").ok,
              "ALMM F5")
        return Fault(FaultClass.F5, "ALMM mandate applied to a procurement before 01.04.2024", [rule],
                     "Apply the abeyance in force at the procurement date")

    f4 = Fault(FaultClass.F4, f"{dcr} (DCR condition) also decides the case", [dcr], "Cite and apply the DCR condition")
    dates = (["2024-06-10", "2024-07-22", "2024-10-05", "2024-03-12", "2024-03-20", "2024-05-14", "2025-01-08",
              "2024-06-18", "2024-08-02", "2024-08-27"] if v == 0 else
             ["2024-09-03", "2025-02-14", "2024-12-11", "2024-02-26", "2024-03-27", "2024-04-02", "2024-11-19",
              "2024-09-25", "2025-01-30", "2025-03-03"])
    mk("CLEAN", MH, dates[0], True, [])
    mk("CLEAN", RJ, dates[1], False, [])  # clean rejection
    mk("CLEAN", RJ, dates[2], True, [])
    mk("F5", RJ, dates[3], False, [f5(dates[3])])
    mk("F5", MH, dates[4], False, [f5(dates[4])])
    mk("F3", RJ, dates[5], False, [f3(dates[5])])
    mk("F3", MH, dates[6], False, [f3(dates[6])])
    mk("F4", MH, dates[7], True, [f4], dcr_ok=False, decisive=[rule, dcr])
    mk("F9", RJ, dates[8], None, [Fault(FaultClass.F9, "module enlistment unreadable", ["module_almm_status"],
                                            "Abstain until the module list is legible")])
    mk("MULTI", MH, dates[9], False, [f3(dates[9]), f4], dcr_ok=False, decisive=[rule, dcr])
    return out


BUILDERS: dict[str, tuple[Callable[..., list[Scenario]], StateCode, str]] = {
    "IN-C2-002#cl-1": (_almm_scenarios, MH, ""),
    "MH-C3-001#cl-6.2": (_load_scenarios, MH, "2024-09-16"),
    "RJ-C3-003#cl-2": (_dt_scenarios, RJ, "2024-11-04"),
    "IN-C1-001#cl-4.1": (_cfa_scenarios, MH, "2024-10-21"),
    "MH-C3-001#cl-5.2": (_dt_scenarios, MH, "2024-08-12"),
    "MH-C3-002#cl-annex1-c": (_feasibility_scenarios, MH, "2025-01-15"),
    "RJ-C3-002#cl-7.2": (_load_scenarios, RJ, "2024-12-09"),
    "RJ-C3-005#cl-8.8": (_feasibility_scenarios, RJ, "2025-02-11"),
}


# ==============================================================================
# Rendering
# ==============================================================================
TARIFF = {"residential": "LT-I Residential", "commercial": "LT-II Commercial", "industrial": "HT-I Industrial"}


def _render(node_id: str, idx: int, sc: Scenario, graph: SupersessionGraph, opaque_id: str | None = None,
            corpus_version: str = BENCHMARK_CORPUS_VERSION, names: list[str] | None = None) -> BenchmarkCase:
    """Render one scenario. v1 ids encode cluster and slot; v2 passes an opaque id and draws the name from it."""
    cid = opaque_id or f"{node_id.replace('#', '-').replace('.', '_')}-{idx:03d}"
    discom = sc.discom or DISCOM[sc.state]
    names = names or NAMES
    name = names[(idx + len(node_id)) % len(names)] if opaque_id is None else \
        names[int(hashlib.sha256(cid.encode()).hexdigest(), 16) % len(names)]
    cno = hashlib.sha256(cid.encode()).hexdigest()[:12].upper()
    facts = CaseFacts(
        state=sc.state, discom=discom, consumer_category=ConsumerCategory(sc.category),
        # An unreadable facsimile field hides, but does not erase, the underlying fact.
        sanctioned_load_kw=sc.sanctioned_kw if sc.sanctioned_kw is not None else sc.connected_kw,
        connected_load_kw=sc.connected_kw,
        proposed_capacity_kw=sc.proposed_kw if sc.proposed_kw is not None else UNREADABLE_CAPACITY_KW,
        premises_type=sc.premises, metering_mode=sc.metering_mode,
        module_almm_status={True: AlmmStatus.LISTED, False: AlmmStatus.NOT_LISTED, None: AlmmStatus.UNKNOWN}[sc.almm],
        dcr_claimed=sc.dcr, subsidy_claimed=sc.subsidy_claimed,
        application_stage=sc.portal_status.lower().replace(" ", "_"), case_date=sc.case_date,
    )
    inputs = CaseInputs(
        bill=_make_bill(discom.value, cno, name, sc.tariff or TARIFF[sc.category], sc.sanctioned_kw, sc.connected_kw,
                        sc.case_date),
        proposal=_make_proposal(name, cno, sc.proposed_kw, sc.almm, sc.dcr, sc.metering_text, sc.proposal_extra,
                                inverter_kva=sc.inverter_kva),
        portal_state=_make_portal(discom.value, f"RTS-{sc.state.value}-{cno[:6]}", sc.case_date,
                                  sc.portal_status, sc.portal_details),
    )
    applicable = []
    for rid in sc.decisive:
        node = graph.nodes[rid]
        applicable.append(ApplicableRuleReference(
            rule_id=rid, clause=node.clause_ref, effective_date=node.effective_date,
            jurisdiction=str(getattr(node.jurisdiction.code, "value", node.jurisdiction.code)),
            applicability_basis=node.clause_text_snippet[:160],
        ))
    abstain = sc.ok is None
    blocked = not abstain and not sc.ok
    return BenchmarkCase(
        case_id=cid,
        cluster_id=node_id if opaque_id is not None else None, corpus_version=corpus_version, facts=facts, inputs=inputs,
        applicable_rules=applicable,
        expected_answer=ExpectedAnswer(
            blocking_stage=sc.stage if blocked else None,
            root_cause=sc.root_cause if blocked else None,
            next_action=("Abstain and request the missing information" if abstain
                         else "Reject at the blocking stage and notify the applicant" if blocked
                         else "Proceed to the next stage"),
            computed=[sc.computed] if sc.computed else [],
        ),
        # F3 labels anchored on an implicit supersession edge are medium confidence (protocol §6).
        ground_truth_provenance=GroundTruthProvenance(
            basis="rule_function:" + ",".join(sc.decisive),
            confidence=sc.confidence or ConfidenceLevel.MEDIUM
            if sc.confidence or any(f.fault_class == FaultClass.F3 and set(f.evidence) & IMPLICIT_F3_EVIDENCE for f in sc.faults)
            else ConfidenceLevel.HIGH,
        ),
        failure_class_probed=sc.probed,
        expected_decision=ExpectedDecision.ABSTAIN if abstain else ExpectedDecision.ANSWER,
        abstention_reason=sc.abstention_reason if abstain else None,
        fault_events=[
            FaultEvent(fault_event_id=f"{cid}#fe-{k}", case_id=cid, fault_class=f.fault_class,
                       fault_subtype=FaultSubtype.F4_R if f.fault_class == FaultClass.F4 else None,
                       gold_trigger=f.trigger, gold_evidence=f.evidence, expected_behavior=f.behavior)
            for k, f in enumerate(sc.faults, start=1)
        ],
        non_fault_opportunities=[
            NonFaultOpportunity(opportunity_id=f"{cid}#nfo-{k}", case_id=cid, target_property=prop,
                                claim_text=claim)
            for k, (prop, claim) in enumerate(sc.nfos, start=1)
        ],
    )


CASES_PER_VARIANT = 10
VARIANTS = 2  # two magnitude variants of every partition: 20 cases per cluster
VARIANT_DATE_SHIFT_DAYS = 47
V2_SEED = "SuryaBench-v2-cases-2026-10"
# v2 magnitude multipliers drawn per slot, so clean and trap partitions share wide ranges (D13).
# DT and load limits are scale-invariant (percent / ratio rules); CFA scales only where the slab is saturated.
# Pools keep every proposed capacity under the 1 MW net-metering ceiling, which only the F5 ceiling cases exceed.
V2_SCALES = {_dt_scenarios: [1, 2, 3, 5, 8], _load_scenarios: [1, 2, 3, 5, 8, 13, 21, 34], _cfa_scenarios: [1, 2, 3, 5]}


def _node_scenarios(node_id: str, rng: random.Random | None) -> list[Scenario]:
    """Scenarios of one cluster. v1 (rng None): fixed slot order and magnitudes. v2: per-slot random scale, shuffled."""
    builder, state, date = BUILDERS[node_id]
    scenarios: list[Scenario] = []
    cache: dict[tuple[int, int], list[Scenario]] = {}
    for v in range(VARIANTS):
        shifted = (_dt.date.fromisoformat(date) + _dt.timedelta(days=VARIANT_DATE_SHIFT_DAYS * v)).isoformat() \
            if date else date
        if rng is None or builder not in V2_SCALES:
            batch = builder(node_id, state, shifted, v)
        else:
            batch = []
            for j in range(CASES_PER_VARIANT):
                sc = rng.choice(V2_SCALES[builder])
                if (v, sc) not in cache:
                    cache[(v, sc)] = builder(node_id, state, shifted, v, scale=sc)
                batch.append(cache[(v, sc)][j])
        assert len(batch) == CASES_PER_VARIANT, f"{node_id} v{v}: {len(batch)} scenarios"
        scenarios += batch
    if rng is not None:
        rng.shuffle(scenarios)  # trap types land in random slots within the cluster
    return scenarios


def generate_node_cases(node_id: str, graph: SupersessionGraph) -> list[BenchmarkCase]:
    """v1 generation of one cluster (ids encode cluster and slot). Kept byte-identical to the sealed 160 cases."""
    return [_render(node_id, i, sc, graph) for i, sc in enumerate(_node_scenarios(node_id, None), start=1)]


def generate_v2_cases(node_ids: list[str], graph: SupersessionGraph, seed: str = V2_SEED,
                      corpus_version: str = BENCHMARK_CORPUS_VERSION) -> list[BenchmarkCase]:
    """v2 generation (D13): opaque seeded ids, shuffled slots, wide magnitudes, globally shuffled order."""
    rng = random.Random(f"{seed}|{'|'.join(node_ids)}")
    pairs = [(n, i, sc) for n in node_ids for i, sc in enumerate(_node_scenarios(n, rng), start=1)]
    rng.shuffle(pairs)
    ids: set[str] = set()
    cases = []
    for n, i, sc in pairs:
        cid = f"SB-{rng.getrandbits(32):08x}"
        while cid in ids:
            cid = f"SB-{rng.getrandbits(32):08x}"
        ids.add(cid)
        cases.append(_render(n, i, sc, graph, opaque_id=cid, corpus_version=corpus_version))
    return cases


def _load_graph(corpus_dir: Path = CORPUS_DIR) -> SupersessionGraph:
    with open(corpus_dir / "graph" / "supersession.json", encoding="utf-8") as f:
        return SupersessionGraph.model_validate(json.load(f))


def build_v2_dev() -> list[BenchmarkCase]:
    """The three dev clusters regenerated under v2. No v2 test split: new test clusters come later (D14)."""
    cases = generate_v2_cases(DEV_RULE_NODES, _load_graph(CORPUS_R3_DIR), corpus_version=CORPUS_VERSION_R3)
    validate_benchmark_suite(cases)
    return cases


def save_v2_dev(output_dir: Path | None = None) -> str:
    """Write dev_cases_v2.json and its sha256 file; returns the digest."""
    out_dir = output_dir or BENCHMARK_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    text = json.dumps([c.model_dump(mode="json") for c in build_v2_dev()], indent=2)
    (out_dir / "dev_cases_v2.json").write_text(text, encoding="utf-8", newline="\n")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    (out_dir / "dev_cases_v2.sha256").write_text(f"{digest}  dev_cases_v2.json\n", encoding="utf-8", newline="\n")
    return digest


def build_full_benchmark() -> tuple[list[BenchmarkCase], list[BenchmarkCase], list[BenchmarkCase]]:
    """Build, validate and partition the v1 benchmark (cluster-level dev/test split). Reproduces the sealed 160."""
    graph = _load_graph()
    dev = [c for n in DEV_RULE_NODES for c in generate_node_cases(n, graph)]
    test = [c for n in TEST_RULE_NODES for c in generate_node_cases(n, graph)]
    validate_benchmark_suite(dev + test)
    return dev + test, dev, test


def save_and_seal_benchmark(output_dir: Path | None = None) -> dict[str, str]:
    """Write the full suite and both splits, and seal them in BENCHMARK.sha256."""
    out_dir = output_dir or BENCHMARK_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    all_cases, dev_cases, test_cases = build_full_benchmark()
    files = {
        f"benchmark_cases_{len(all_cases)}.json": all_cases,
        f"dev_cases_{len(dev_cases)}.json": dev_cases,
        f"test_cases_{len(test_cases)}.json": test_cases,
    }
    hashes = {}
    for name, cases in files.items():
        text = json.dumps([c.model_dump(mode="json", exclude=None if c.cluster_id else {"cluster_id"}) for c in cases], indent=2)
        (out_dir / name).write_text(text, encoding="utf-8", newline="\n")
        hashes[name] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    (out_dir / "BENCHMARK.sha256").write_text("".join(f"{h}  {n}\n" for n, h in hashes.items()), encoding="utf-8", newline="\n")
    return hashes


if __name__ == "__main__":
    # The sealed v1 files are never regenerated by default; v2 dev is the only output of this entry point.
    print(save_v2_dev(), "dev_cases_v2.json")
