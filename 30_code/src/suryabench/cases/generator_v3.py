"""v3 case generation for the corpus-r3 clusters (D14): the candidate v2 test split.

Same method as `suryabench.cases.generator` (labels only from rule functions, every trap asserted to
flip the verdict, opaque seeded ids, shuffled order, cluster_id hidden from arms), over 20 new clusters
from jurisdictions and clauses not used in development: GJ, KA, TN, DL, UP and new central clauses.
Rule functions live in `suryabench.cases.rules_v3`; clause snippets in
`40_data/corpus_r3/graph/supersession.json`. Everything here is UNVERIFIED and provisional until the
human annotation in `20_method/ANNOTATION-PACKET.md`.

Balance (D13): many clusters decide on something other than capacity versus sanctioned load
(transformer limits, feasibility, check meters, meter class, voltage level, ALMM List-II, CFA claim
windows, augmentation charges), and several allow a proposed capacity above the sanctioned load
(GJ residential, KA up to 10 kW, DL with SLD charges or ground-mounted VNM), so the capacity heuristic
is not a shortcut to the label.

A trap marked `same=True` is a citation hazard only (the trap clause gives the same verdict); it only
appears beside a flipping trap in MULTI cases.
"""

import datetime as _dt
import hashlib
import json
import random
from collections.abc import Callable
from pathlib import Path
from typing import Any

from suryabench.cases import rules
from suryabench.cases import rules_v3 as r3
from suryabench.cases.generator import CORPUS_VERSION_R3, Fault, Scenario, _render
from suryabench.cases.schema import BenchmarkCase
from suryabench.cases.validator import validate_benchmark_suite
from suryabench.core.enums import (
    ConfidenceLevel,
    DiscomCode,
    FaultClass,
    MeteringMode,
    PremisesType,
    StateCode,
)
from suryabench.graph.schema import SupersessionGraph
from suryabench.paths import BENCHMARK_DIR, CORPUS_R3_DIR

V3_SEED = "SuryaBench-v2-test-candidate-2026-10"
CANDIDATE_FILE = "test_cases_v2_CANDIDATE.json"
GJ, KA, TN, DL, UP = StateCode.GJ, StateCode.KA, StateCode.TN, StateCode.DL, StateCode.UP
F2, F3, F4, F5, F6, F8, F9 = (FaultClass.F2, FaultClass.F3, FaultClass.F4, FaultClass.F5, FaultClass.F6,
                              FaultClass.F8, FaultClass.F9)
TECH, EQUIP, SUBSIDY, METER_MODE, REG = ("technical_feasibility", "equipment_verification", "subsidy_approval",
                                         "metering_mode_selection", "portal_registration")

TARIFFS = {
    GJ: {"residential": "RGP (Residential General Purpose)", "commercial": "LTMD Non-RGP Commercial",
         "industrial": "HTP-I Industrial"},
    KA: {"residential": "LT-2(a) Domestic", "commercial": "LT-3 Commercial", "industrial": "HT-2(a) Industrial"},
    TN: {"residential": "LA-1A Domestic", "commercial": "LB-V Commercial", "industrial": "HT-I A Industrial"},
    DL: {"residential": "DX Domestic", "commercial": "NDLT Non-Domestic", "industrial": "Industrial (HT)"},
    UP: {"residential": "LMV-1 Domestic Light, Fan & Power", "commercial": "LMV-2 Non-Domestic",
         "industrial": "HV-2 Large and Heavy Power"},
}
DISCOMS = {GJ: [DiscomCode.UGVCL, DiscomCode.MGVCL], KA: [DiscomCode.BESCOM, DiscomCode.HESCOM],
           TN: [DiscomCode.TANGEDCO], DL: [DiscomCode.BRPL, DiscomCode.TPDDL], UP: [DiscomCode.PVVNL, DiscomCode.MVVNL]}
NAMES = {
    GJ: ["Hiral Patel", "Jignesh Desai", "Kokila Shah", "Bhavesh Parmar", "Nayana Joshi", "Rakesh Chaudhari"],
    KA: ["Manjunath Gowda", "Shwetha Rao", "Basavaraj Patil", "Lakshmi Hegde", "Prakash Shetty", "Asha Kulkarni"],
    TN: ["Murugan Selvam", "Lakshmi Narayanan", "Karthik Raja", "Meenakshi Sundaram", "Senthil Kumar", "Revathi Bala"],
    DL: ["Amit Kapoor", "Neha Malhotra", "Rohit Sehgal", "Pooja Bansal", "Sanjay Arora", "Ritu Khanna"],
    UP: ["Ramesh Yadav", "Sunita Mishra", "Alok Tripathi", "Kiran Verma", "Vinod Srivastava", "Anjali Pandey"],
}


def T(cls: FaultClass, gov_ok: bool, trap_ok: bool, evidence: list[str], trigger: str, behavior: str,
      same: bool = False) -> Fault:
    """A trap. Unless `same`, applying the trap clause must change the verdict."""
    if same:
        assert gov_ok == trap_ok, f"citation-only trap changes the verdict: {trigger}"
        trigger += " (citation hazard only: same verdict here)"
    else:
        assert gov_ok != trap_ok, f"trap does not change the verdict: {trigger}"
    return Fault(cls, trigger, evidence, behavior)


class Cluster:
    """Collects the scenarios of one cluster; dates are spread over the cluster's window."""

    def __init__(self, node: str, state: StateCode, start: str, end: str):
        self.node, self.state = node, state
        self.out: list[Scenario] = []
        self.start, self.span = _dt.date.fromisoformat(start), (
            _dt.date.fromisoformat(end) - _dt.date.fromisoformat(start)).days

    def add(self, probed: str, ok: bool | None, *, stage: str, root: str, decisive: list[str], sl: float | None,
            p: float | None, details: list[str], faults: list[Fault] | None = None, cat: str = "residential",
            cl: float | None = None, state: StateCode | None = None, extra: list[str] | None = None,
            reason: str = "", computed: dict[str, Any] | None = None, almm: bool | None = True, dcr: bool = True,
            premises: PremisesType = PremisesType.INDIVIDUAL, metering: str = "Net Metering",
            mode: MeteringMode = MeteringMode.NET, subsidy: bool = False, inverter: float | None = None,
            date: str | None = None, confidence: ConfidenceLevel | None = None, portal: str = "Technical Feasibility",
            nfos: list[tuple[str, str]] | None = None) -> None:
        st = state or self.state
        k = len(self.out)
        day = self.start + _dt.timedelta(days=(k * 37) % max(1, self.span))
        self.out.append(Scenario(
            probed=probed, state=st, case_date=date or day.isoformat(), ok=ok, stage=stage, root_cause=root,
            computed=computed or {}, decisive=decisive, sanctioned_kw=sl, connected_kw=cl if cl is not None else (sl or 0.0),
            category=cat, proposed_kw=p, portal_status=portal, portal_details=details, almm=almm, dcr=dcr,
            proposal_extra=extra or [], premises=premises, inverter_kva=inverter, subsidy_claimed=subsidy,
            faults=faults or [], abstention_reason=reason if ok is None else None,
            nfos=nfos or [("currency", f"{decisive[0]} is in force at the case date"),
                          ("jurisdiction", f"{decisive[0]} governs {st.value} applications")],
            discom=DISCOMS[st][k % len(DISCOMS[st])], tariff=TARIFFS[st][cat], metering_text=metering,
            metering_mode=mode, confidence=confidence,
        ))


def dt_lines(dt: float | None, ex: float, p: float) -> list[str]:
    if dt is None:
        return ["Distribution Transformer Rating: NOT RECORDED in GIS for this DT"]
    return [f"Distribution Transformer Rating: {dt:.0f} kVA", f"Existing Solar on Transformer: {ex:.1f} kW",
            f"Resultant Cumulative Solar Capacity: {ex + p:.1f} kW"]


MISSING_DT = "F9 missing: transformer rating needed for the hosting-limit check is not recorded"


# ==============================================================================================
# Distribution-transformer clusters (GJ 100%, KA 80%, TN 90%, UP 75%)
# ==============================================================================================
def _dt_cluster(c: Cluster, gov: str, cap_rule: str | None, aliens: dict[str, str], old: str | None,
                slots: list[tuple[Any, ...]]) -> list[Scenario]:
    """slots: (probed, dt, existing, proposed, sanctioned, cat, trap spec list). Trap spec: (class, rule|'F6', same)."""
    for probed, dt, ex, p, sl, cat, traps in slots:
        if dt is None:
            c.add("F9", None, stage=TECH, root="", decisive=[gov], sl=sl, p=p, details=dt_lines(None, ex, p),
                  cat=cat, reason=MISSING_DT,
                  faults=[Fault(F9, "transformer rating not recorded", ["dt_capacity_kva"], "Abstain until known")])
            continue
        v = r3.dt_limit(gov, dt, ex, p)
        decisive = [gov]
        cap_ok = True
        if cap_rule is not None:
            cap_ok = r3.capacity(cap_rule, sl, p).ok
            if not cap_ok:
                decisive.append(cap_rule)
        ok = v.ok and cap_ok
        faults = []
        for cls, rule, same in traps:
            if cls == F4:
                faults.append(Fault(F4, f"{rule} (capacity) also decides the case", [rule],
                                    f"Cite and apply {rule} as well as {gov}"))
            elif rule == "F6":
                trap = ex <= dt * r3.DT_PCT[gov] / 100.0 and cap_ok
                faults.append(T(F6, ok, trap, ["cumulative_solar_kw"], "binding existing solar instead of the "
                                "resultant cumulative loading", f"Bind the cumulative loading ({ex + p} kW)", same))
            else:
                trap = (r3.dt_limit(rule, dt, ex, p).ok if rule in r3.DT_PCT else rules.dt_limit(rule, dt, ex, p).ok) \
                    and cap_ok
                what = "superseded" if cls == F3 else ("other-state" if cls == F2 else "inapplicable")
                faults.append(T(cls, ok, trap, [rule], f"{what} {rule} applied to the hosting limit",
                                f"Apply {gov}", same))
        c.add(probed, ok, stage=TECH, root="dt_hosting_limit_exceeded" if not v.ok else "capacity_exceeds_sanctioned_load",
              decisive=decisive, sl=sl, p=p, details=dt_lines(dt, ex, p), faults=faults, cat=cat, computed=v.computed)
    return c.out


def gj_dt() -> list[Scenario]:
    gov, old, cap = "GJ-C3-003#cl-5-proviso", "GJ-C3-001#cl-5-proviso", "GJ-C3-004#cl-6.2c-i"
    c = Cluster(gov, GJ, "2024-11-04", "2026-08-28")
    return _dt_cluster(c, gov, cap, {}, old, [
        ("CLEAN", 100, 50, 5, 3, "residential", []),
        ("CLEAN", 63, 60, 5, 8, "residential", []),
        ("F3", 100, 60, 10, 6, "residential", [(F3, old, False)]),
        ("F3", 250, 150, 30, 40, "residential", [(F3, old, False)]),
        ("F2", 100, 78, 8, 5, "residential", [(F2, "KA-C5-006#cl-4", False)]),
        ("F2", 200, 170, 15, 10, "residential", [(F2, "TN-C5-002#cl-VII.3", False)]),
        ("F6", 100, 97, 6, 10, "residential", [(F6, "F6", False)]),
        ("F4", 100, 20, 0.6, 2, "residential", [(F4, "GJ-C3-004#cl-6.2a", False)]),
        ("F9", None, 0, 5, 4, "residential", []),
        ("MULTI", 100, 75, 10, 4, "residential", [(F3, old, False), (F2, "KA-C5-006#cl-4", False)]),
        ("CLEAN", 500, 300, 150, 200, "residential", []),
        ("CLEAN", 100, 92, 12, 6, "residential", []),
    ])


def ka_dt() -> list[Scenario]:
    gov, feeder = "KA-C5-006#cl-4", "KA-C3-001#cl-6f"
    c = Cluster(gov, KA, "2025-12-08", "2026-08-12")
    out = _dt_cluster(c, gov, "KA-C4-001#cl-1", {}, None, [
        ("CLEAN", 100, 50, 8, 5, "residential", []),
        ("CLEAN", 100, 75, 9, 10, "residential", []),
        ("F2", 100, 70, 8, 6, "residential", [(F2, "UP-C3-002#cl-6.2", False)]),
        ("F2", 100, 80, 10, 10, "residential", [(F2, "GJ-C3-003#cl-5-proviso", False)]),
        ("F2", 200, 150, 20, 25, "commercial", [(F2, "TN-C5-002#cl-VII.3", False)]),
        ("F6", 100, 78, 6, 4, "residential", [(F6, "F6", False)]),
        ("F9", None, 0, 6, 5, "residential", []),
        ("MULTI", 100, 79, 5, 3, "residential", [(F2, "GJ-C3-003#cl-5-proviso", False), (F6, "F6", False)]),
        ("CLEAN", 250, 100, 60, 80, "commercial", []),
        ("CLEAN", 63, 45, 6, 5, "residential", []),
    ])
    # F5: plants above 150 kW connect to the 11 kV feeder; the LT transformer limit "is applicable only for
    # LT installations" (SOP item 4 note i), the feeder rule (6(f)) decides.
    for dt, ex, p, sl, load in ((500, 250, 200, 250, 70.0), (1000, 100, 300, 400, 85.0)):
        v = r3.feeder_limit(feeder, load)
        trap = r3.dt_limit(gov, dt, ex, p).ok
        c.add("F5", v.ok, stage=TECH, root="feeder_loading_limit_exceeded", decisive=[feeder], sl=sl, p=p, cat="industrial",
              details=[*dt_lines(dt, ex, p), "Connection: HT 11 kV consumer (plant above 150 kW)",
                       f"11 kV Feeder Loading after Connection: {load:.0f}% of rated line current"],
              faults=[T(F5, v.ok, trap, [gov], "LT transformer limit applied to an HT plant above 150 kW",
                        f"Apply {feeder}: 80% of the feeder's rated current")], computed=v.computed)
    return out


def tn_dt() -> list[Scenario]:
    gov, pt = "TN-C5-002#cl-VII.3", "TN-C5-002#cl-VII.4"
    c = Cluster(gov, TN, "2022-01-10", "2025-12-15")
    out = _dt_cluster(c, gov, "TN-C5-002#cl-I.2", {}, None, [
        ("CLEAN", 100, 60, 8, 10, "residential", []),
        ("CLEAN", 100, 85, 8, 10, "residential", []),
        ("F2", 100, 80, 6, 8, "residential", [(F2, "KA-C5-006#cl-4", False)]),
        ("F2", 200, 140, 15, 20, "commercial", [(F2, "UP-C3-002#cl-6.2", False)]),
        ("F2", 100, 88, 5, 6, "residential", [(F2, "GJ-C3-003#cl-5-proviso", False)]),
        ("F5", 250, 190, 20, 25, "commercial", [(F5, pt, False)]),
        ("F6", 160, 140, 10, 12, "commercial", [(F6, "F6", False)]),
        ("F9", None, 0, 6, 8, "residential", []),
        ("MULTI", 100, 78, 9, 10, "residential", [(F2, "KA-C5-006#cl-4", False), (F5, pt, False)]),
        ("CLEAN", 500, 200, 100, 120, "commercial", []),
        ("CLEAN", 63, 52, 6, 8, "residential", []),
    ])
    # F5 reverse: HT gross metering at the power transformer is governed by VII.4 (70%), not VII.3 (90%).
    v = r3.dt_limit(pt, 5000, 3200, 400)
    c.add("F5", v.ok, stage=TECH, root="power_transformer_limit_exceeded", decisive=[pt], sl=600, p=400,
          cat="industrial", metering="Gross Metering", mode=MeteringMode.GROSS,
          details=["Power Transformer Rating: 5000 kVA (33/11 kV substation)", "Existing Solar on Power Transformer: 3200.0 kW",
                   "Resultant Cumulative Solar Capacity on Power Transformer: 3600.0 kW", "Connection: HT, gross metering"],
          faults=[T(F5, v.ok, r3.dt_limit(gov, 5000, 3200, 400).ok, [gov], "the 90% DT limit applied to HT gross "
                    "metering at a power transformer", f"Apply {pt}: 70% of the power transformer capacity")],
          computed=v.computed)
    return out


def up_dt() -> list[Scenario]:
    gov, old = "UP-C3-002#cl-6.2", "UP-C3-001#cl-6.2"
    c = Cluster(gov, UP, "2023-02-06", "2026-09-10")
    return _dt_cluster(c, gov, "UP-C3-002#cl-5.1", {}, old, [
        ("CLEAN", 100, 50, 5, 6, "residential", []),
        ("CLEAN", 100, 72, 6, 8, "residential", []),
        ("F3", 100, 20, 5, 6, "residential", [(F3, old, False)]),
        ("F3", 250, 100, 30, 40, "commercial", [(F3, old, False)]),
        ("F2", 100, 72, 6, 8, "residential", [(F2, "KA-C5-006#cl-4", False)]),
        ("F2", 200, 140, 20, 25, "commercial", [(F2, "GJ-C3-003#cl-5-proviso", False)]),
        ("F2", 160, 110, 15, 20, "commercial", [(F2, "TN-C5-002#cl-VII.3", False)]),
        ("F6", 100, 73, 4, 5, "residential", [(F6, "F6", False)]),
        ("F9", None, 0, 5, 6, "residential", []),
        ("MULTI", 100, 74, 4, 5, "residential", [(F2, "KA-C5-006#cl-4", False), (F6, "F6", False)]),
        ("CLEAN", 500, 200, 100, 150, "commercial", []),
        ("F4", 100, 30, 6, 5, "residential", [(F4, "UP-C3-002#cl-5.1", False)]),
    ])


# ==============================================================================================
# Capacity clusters
# ==============================================================================================
def _cap_cluster(c: Cluster, gov: str, slots: list[tuple[Any, ...]], stage: str = TECH, **common: Any) -> list[Scenario]:
    """slots: (probed, sanctioned, proposed, cat, traps[(class, rule|'F6:<connected>', same)], kwargs)."""
    for probed, sl, p, cat, traps, kw in slots:
        kw = {"details": [], **common, **kw}
        flags ={k: kw.pop(k) for k in ("sld_paid", "ground_mounted") if k in kw}
        if sl is None or p is None:
            what = "sanctioned load on the bill" if sl is None else "proposed capacity"
            c.add("F9", None, stage=stage, root="", decisive=[gov], sl=sl, p=p, cat=cat,
                  reason=f"F9 missing: the {what} is unreadable", details=kw.pop("details", []),
                  faults=[Fault(F9, f"{what} unreadable", ["sanctioned_load_kw" if sl is None else "proposed_capacity_kw"],
                                "Abstain until legible")], **kw)
            continue
        v = r3.capacity(gov, sl, p, **flags)
        faults = []
        for cls, rule, same in traps:
            if rule.startswith("F6:"):
                cl = float(rule[3:])
                faults.append(T(F6, v.ok, r3.capacity(gov, cl, p, **flags).ok, ["sanctioned_load_kw"],
                                "binding connected load as sanctioned load", f"Bind sanctioned load ({sl} kW)", same))
                kw["cl"] = cl
            elif rule == "TN-C5-002#cl-I.3a":
                faults.append(T(cls, v.ok, r3.gross_metering_size(rule, p).ok, [rule],
                                "gross-metering size band applied to a net feed-in request", f"Apply {gov}", same))
            else:
                trap = r3.capacity(rule, sl, p, **flags).ok
                what = {F3: "superseded", F2: "other-state", F5: "inapplicable"}[cls]
                faults.append(T(cls, v.ok, trap, [rule], f"{what} {rule} applied to the capacity limit",
                                f"Apply {gov}", same))
        c.add(probed, v.ok, stage=stage, root="capacity_limit_exceeded", decisive=[gov], sl=sl, p=p, cat=cat,
              faults=faults, computed=v.computed, **kw)
    return c.out


def gj_cap() -> list[Scenario]:
    gov, old, rec, alien = "GJ-C3-004#cl-6.2c-i", "GJ-C3-001#cl-6.2", "GJ-C3-004#cl-6.2c-iii", "UP-C3-002#cl-5.1"
    c = Cluster(gov, GJ, "2024-10-07", "2026-09-15")
    no_rec = {"extra": ["Renewable Energy Certificate (REC) mechanism: Not opted"]}
    soc = {"premises": PremisesType.RWA_COMMON,
           "extra": ["Applicant: Housing society common utilities billed at residential tariff"]}
    det = {"details": ["Distribution Transformer Rating: 250 kVA", "Existing Solar on Transformer: 40.0 kW"]}
    return _cap_cluster(c, gov, [
        ("CLEAN", 3, 5, "residential", [], {}),
        ("CLEAN", 8, 6, "residential", [], {}),
        ("CLEAN", 2, 0.8, "residential", [], {}),
        ("CLEAN", 1500, 1200, "residential", [], soc),
        ("F3", 4, 3, "residential", [(F3, old, False)], {}),
        ("F3", 2, 4.5, "residential", [(F3, old, False)], {}),
        ("F2", 5, 7, "residential", [(F2, alien, False)], {}),
        ("F5", 6, 9, "residential", [(F5, rec, False)], no_rec),
        ("F9", 4, None, "residential", [], {}),
        ("MULTI", 3, 4, "residential", [(F3, old, False), (F2, alien, False)], {}),
        ("CLEAN", 10, 18, "residential", [], {}),
        ("F5", 120, 160, "residential", [(F5, rec, False)], {**soc, "extra": [*soc["extra"], *no_rec["extra"]]}),
    ], details=det["details"])


def tn_cap() -> list[Scenario]:
    gov, old, gj = "TN-C5-002#cl-I.2", "TN-C5-001#cl-2", "GJ-C3-004#cl-6.2c-i"
    c = Cluster(gov, TN, "2022-02-14", "2025-11-20")
    return _cap_cluster(c, gov, [
        ("CLEAN", 10, 8, "residential", [], {}),
        ("CLEAN", 1100, 1000, "industrial", [], {}),
        ("CLEAN", 1500, 1200, "industrial", [], {}),
        ("F3", 1200, 1100, "industrial", [(F3, old, False)], {}),
        ("F3", 2000, 1500, "industrial", [(F3, old, False)], {}),
        ("F2", 4, 6, "residential", [(F2, gj, False)], {}),
        ("F5", 150, 120, "commercial", [(F5, "TN-C5-002#cl-I.3a", False)], {"metering": "Net Feed-in"}),
        ("F5", 100, 90, "commercial", [(F5, "TN-C5-002#cl-I.3a", False)], {"metering": "Net Feed-in"}),
        ("F6", 8, 10, "residential", [(F6, "F6:12", False)], {}),
        ("F9", None, 5, "residential", [], {}),
        ("MULTI", 1300, 1005, "industrial", [(F3, old, False), (F2, gj, True)], {}),
        ("CLEAN", 500, 450, "commercial", [], {}),
    ], metering="Net Billing")


def up_cap() -> list[Scenario]:
    gov, old, roc, tn = "UP-C3-002#cl-5.1", "UP-C3-001#cl-5.1", "IN-C3-004#cl-11.4", "TN-C5-002#cl-I.2"
    c = Cluster(gov, UP, "2023-03-13", "2026-09-21")
    out = _cap_cluster(c, gov, [
        ("CLEAN", 10, 8, "residential", [], {}),
        ("CLEAN", 4, 5, "residential", [], {}),
        ("CLEAN", 3000, 2500, "industrial", [], {}),
        ("F3", 2600, 2200, "industrial", [(F3, old, False)], {}),
        ("F3", 2, 1.0, "residential", [(F3, old, False)], {}),
        ("F5", 900, 800, "industrial", [(F5, roc, False)], {}),
        ("F5", 1500, 1200, "industrial", [(F5, roc, False)], {}),
        ("F2", 1600, 1400, "industrial", [(F2, tn, False)], {}),
        ("F9", None, 6, "residential", [], {}),
        ("MULTI", 2500, 2100, "industrial", [(F3, old, False), (F5, roc, True)], {}),
        ("CLEAN", 2000, 2000, "industrial", [], {}),
    ])
    # F8 (low confidence, for legal reading): ROC 2024 rule 11(7A) has the licensee enhance the sanctioned load
    # for systems up to 10 kW; UPERC Reg 5.1 caps capacity at 100% of connected/contracted demand.
    c.add("F8", None, stage=TECH, root="", decisive=[gov, "IN-C3-001#cl-11.7A"], sl=4, p=6, date="2024-06-17",
          reason="F8 conflict: ROC 2024 rule 11(7A) (licensee enhances sanctioned load up to 10 kW) versus UPERC "
                 "Reg 5.1 (cap at 100% of contracted demand); needs a legal reading", confidence=ConfidenceLevel.LOW,
          details=["Application Completeness: Complete in all respects"],
          faults=[Fault(F8, "central rule 11(7A) and UPERC Reg 5.1 give opposite outcomes for a 6 kW system on a "
                        "4 kW connection", [gov, "IN-C3-001#cl-11.7A"], "Abstain and flag the conflict")])
    return out


def ka_sl10() -> list[Scenario]:
    gov, tn, up, roc = "KA-C4-001#cl-1", "TN-C5-002#cl-I.2", "UP-C3-002#cl-5.1", "IN-C3-004#cl-11.4"
    c = Cluster(gov, KA, "2025-01-06", "2026-08-14")
    out = _cap_cluster(c, gov, [
        ("CLEAN", 3, 5, "residential", [], {}),
        ("CLEAN", 8, 10, "residential", [], {}),
        ("CLEAN", 9, 12, "residential", [], {}),
        ("CLEAN", 6, 4, "residential", [], {}),
        ("F2", 4, 6, "residential", [(F2, tn, False)], {}),
        ("F2", 2, 3, "residential", [(F2, up, False)], {}),
        ("F5", 5, 7.5, "residential", [(F5, roc, False)], {}),
        ("F9", 4, None, "residential", [], {}),
        ("MULTI", 3, 6, "residential", [(F2, tn, False), (F5, roc, False)], {}),
        ("CLEAN", 10, 11.5, "residential", [], {}),
        ("CLEAN", 7, 9.72, "residential", [], {}),
    ])
    v, dt = r3.capacity(gov, 5, 8), r3.dt_limit("KA-C5-006#cl-4", 63, 45, 8)
    c.add("F4", v.ok and dt.ok, stage=TECH, root="dt_hosting_limit_exceeded", decisive=[gov, "KA-C5-006#cl-4"], sl=5,
          p=8, date="2026-02-09", details=dt_lines(63, 45, 8), computed=dt.computed,
          faults=[Fault(F4, "KA-C5-006#cl-4 (80% DT limit) also decides the case", ["KA-C5-006#cl-4"],
                        f"Cite and apply KA-C5-006#cl-4 as well as {gov}")])
    return out


def dl_sld() -> list[Scenario]:
    gov, up, tn, roc = "DL-C3-001#cl-5.4", "UP-C3-002#cl-5.1", "TN-C5-002#cl-I.2", "IN-C3-004#cl-11.4"
    c = Cluster(gov, DL, "2024-08-05", "2026-09-18")

    def sld(paid: bool | None) -> dict[str, Any]:
        text = {True: "Paid at registration", False: "Not paid", None: "[UNREADABLE - receipt smudged]"}[paid]
        return {"sld_paid": bool(paid), "details": [f"SLD Differential Charges (Reg 5(4)): {text}"]}

    out = _cap_cluster(c, gov, [
        ("CLEAN", 15, 25, "commercial", [], sld(True)),
        ("CLEAN", 40, 30, "commercial", [], sld(False)),
        ("CLEAN", 20, 35, "commercial", [], sld(False)),
        ("F2", 12, 20, "commercial", [(F2, up, False)], sld(True)),
        ("F2", 30, 45, "commercial", [(F2, tn, False)], sld(True)),
        ("F5", 50, 80, "commercial", [(F5, roc, False)], sld(True)),
        ("F5", 600, 550, "industrial", [(F5, roc, False)], sld(False)),
        ("MULTI", 10, 18, "commercial", [(F2, up, False), (F5, roc, False)], sld(True)),
        ("CLEAN", 25, 26, "commercial", [], sld(False)),
        ("CLEAN", 100, 180, "industrial", [], sld(True)),
    ], stage=REG, portal="Registration")
    c.add("F9", None, stage=REG, root="", decisive=[gov], sl=20, p=30, cat="commercial", portal="Registration",
          details=sld(None)["details"], reason="F9 missing: whether the SLD differential was paid is unreadable",
          faults=[Fault(F9, "SLD payment status unreadable", ["sld_paid"], "Abstain until the receipt is legible")])
    feas = "DL-C3-016#cl-g3-stage1-lapse"
    c.add("F4", False, stage=TECH, root="feasibility_not_established", decisive=[gov, feas], sl=40, p=30,
          cat="commercial", date="2026-08-24", details=["Technical Feasibility Outcome: Not feasible: distribution transformer loading",
                                     "Days Elapsed Since Registration/Acknowledgement: 9"],
          faults=[Fault(F4, f"{feas} (feasibility outcome) also decides the case", [feas],
                        f"Cite and apply {feas} as well as {gov}")])
    return out


def dl_vnm() -> list[Scenario]:
    gov, old, roc, up = "DL-C3-009#cl-3.8", "DL-C3-004#cl-3.8", "IN-C3-004#cl-11.4", "UP-C3-002#cl-5.1"
    c = Cluster(gov, DL, "2024-04-15", "2026-09-24")
    g: dict[str, Any] = {"ground_mounted": True, "metering": "Group Net Metering (ground-mounted RE system)"}
    r: dict[str, Any] = {"ground_mounted": False, "metering": "Group Net Metering (rooftop solar)"}
    out = _cap_cluster(c, gov, [
        ("CLEAN", 100, 400, "commercial", [], g),
        ("CLEAN", 100, 600, "commercial", [], r),
        ("CLEAN", 100, 600, "commercial", [], g),
        ("CLEAN", 3000, 12000, "industrial", [], g),
        ("F3", 2000, 6000, "industrial", [(F3, old, False)], g),
        ("F3", 50, 300, "commercial", [(F3, old, False)], g),
        ("F3", 2, 4, "residential", [(F3, old, False)], g),
        ("F5", 80, 300, "commercial", [(F5, roc, False)], g),
        ("F2", 60, 200, "commercial", [(F2, up, False)], g),
        ("CLEAN", 120, 90, "commercial", [], g),
        ("MULTI", 1500, 5500, "industrial", [(F3, old, False), (F5, roc, False)], g),
    ], stage=METER_MODE, portal="Metering Arrangement Approval", mode=MeteringMode.NET)
    # F5: the rooftop "no capping" sentence applied to a ground-mounted system
    v = r3.capacity(gov, 120, 800, ground_mounted=True)
    c.add("F5", v.ok, stage=METER_MODE, root="capacity_limit_exceeded", decisive=[gov], sl=120, p=800, cat="commercial",
          metering=g["metering"], portal="Metering Arrangement Approval", details=[], computed=v.computed,
          faults=[T(F5, v.ok, r3.capacity(gov, 120, 800, ground_mounted=False).ok, [gov],
                    "the rooftop no-cap sentence applied to a ground-mounted system", "Apply the 5x sanctioned load cap")])
    c.add("F9", None, stage=METER_MODE, root="", decisive=[gov], sl=100, p=700, cat="commercial", portal="Metering Arrangement Approval",
          metering="Group Net Metering (mounting type [UNREADABLE])", details=[],
          reason="F9 missing: whether the system is ground-mounted or rooftop (which decides the cap) is unreadable",
          faults=[Fault(F9, "mounting type unreadable", ["metering_mode"], "Abstain until the mounting type is known")])
    return out


# ==============================================================================================
# Feasibility clusters
# ==============================================================================================
def _feas_lines(days: int | None, outcome: str | None, lag: int = 0, extra: list[str] | None = None) -> list[str]:
    o = {None: "Not communicated by the licensee", "feasible": "Technically feasible",
         "infeasible": "Not feasible: distribution transformer loading"}[outcome]
    return [f"Days Elapsed Since Submission: {days + lag}" if days is not None else
            "Days Elapsed Since Submission: [DATE FIELD CORRUPTED]",
            f"Days Elapsed Since Registration/Acknowledgement: {days}" if days is not None else
            "Days Elapsed Since Registration/Acknowledgement: [DATE FIELD CORRUPTED]",
            "Application Completeness: Complete in all respects", f"Technical Feasibility Outcome: {o}", *(extra or [])]


def _feas_cluster(c: Cluster, gov_of: Callable[[float, bool], str], slots: list[tuple[Any, ...]]) -> list[Scenario]:
    """slots: (probed, kW, sanctioned, days, outcome, cat, traps[(class, rule, same)], same_supply, lag)."""
    for probed, kw, sl, days, outcome, cat, traps, same_supply, lag in slots:
        gov = gov_of(kw if kw is not None else 50.0, same_supply)
        extra = [] if c.state != DL else [f"Supply Type Change Required: {'No (same supply type)' if same_supply else 'Yes (1-phase to 3-phase)'}"]
        if days is None or kw is None:
            c.add("F9", None, stage=TECH, root="", decisive=[gov_of(kw or 50.0, same_supply)], sl=sl, p=kw, cat=cat,
                  details=_feas_lines(days, outcome, extra=extra),
                  reason="F9 missing: " + ("the proposed capacity (which decides the route) is unreadable" if kw is None
                                           else "the registration date needed for the study window is corrupted"),
                  faults=[Fault(F9, "decisive field unreadable", ["proposed_capacity_kw" if kw is None else "days_elapsed"],
                                "Abstain until the field is legible")])
            continue
        v = r3.feasibility(gov, kw, days, outcome, same_supply)
        faults = []
        for cls, rule, same in traps:
            if rule == "F6":
                trap = r3.feasibility(gov, kw, days + lag, outcome, same_supply).ok
                faults.append(T(F6, v.ok, trap, ["days_elapsed"], "counting days from submission instead of from the "
                                "complete application", f"Count from registration ({days} days)", same))
                continue
            # misapplying a deemed-acceptance clause outside its reach means treating the application as accepted
            trap_ok = True if cls == F5 and r3.FEAS[rule][0] is not None else \
                r3.feasibility(rule, kw, days, outcome, True).ok
            what = {F3: "superseded", F2: "other-state", F5: "inapplicable"}[cls]
            faults.append(T(cls, v.ok, trap_ok, [rule], f"{what} {rule} applied to a {kw} kW application",
                            f"Apply {gov}", same))
        c.add(probed, v.ok, stage=TECH, root="feasibility_not_established", decisive=[gov], sl=sl, p=kw, cat=cat,
              details=_feas_lines(days, outcome, lag, extra), faults=faults, computed=v.computed)
    return c.out


def gj_feas() -> list[Scenario]:
    prov, row4, old, ka = "GJ-C3-005#cl-7-proviso", "GJ-C3-005#cl-7-row4", "GJ-C3-001#cl-7-row4", "KA-C5-006#cl-4-note-ii"
    c = Cluster(prov, GJ, "2024-09-23", "2026-09-07")

    def gov(kw: float, _s: bool) -> str:
        return prov if kw <= 10 else row4

    return _feas_cluster(c, gov, [
        ("CLEAN", 5, 3, 4, None, "residential", [], True, 0),
        ("CLEAN", 40, 50, 12, "feasible", "commercial", [], True, 0),
        ("CLEAN", 60, 80, 14, "infeasible", "commercial", [], True, 0),
        ("F3", 8, 10, 7, None, "residential", [(F3, old, False)], True, 0),
        ("F3", 9.5, 4, 3, None, "residential", [(F3, old, False)], True, 0),
        ("F2", 30, 40, 9, None, "commercial", [(F2, ka, False)], True, 0),
        ("F2", 120, 150, 20, None, "commercial", [(F2, ka, False)], True, 0),
        ("F5", 12, 15, 6, None, "residential", [(F5, prov, False)], True, 0),
        ("F5", 6, 4, 2, None, "residential", [(F5, row4, False)], True, 0),
        ("F9", None, 5, 3, None, "residential", [], True, 0),
        ("MULTI", 7, 5, 5, None, "residential", [(F3, old, False), (F5, row4, False)], True, 0),
        ("CLEAN", 25, 30, 3, None, "commercial", [], True, 0),
    ])


def ka_feas() -> list[Scenario]:
    gov, hi, old, gj = "KA-C5-006#cl-4-note-ii", "KA-C3-001#cl-l-feasibility", "KA-C5-001#cl-26", "GJ-C3-005#cl-7-proviso"
    c = Cluster(gov, KA, "2025-12-03", "2026-08-15")

    def g(kw: float, _s: bool) -> str:
        return gov if kw <= 150 else hi

    out = _feas_cluster(c, g, [
        ("CLEAN", 100, 120, 3, None, "commercial", [], True, 0),
        ("CLEAN", 6, 4, 2, None, "residential", [], True, 0),
        ("CLEAN", 200, 250, 6, None, "industrial", [], True, 0),
        ("CLEAN", 300, 400, 9, "infeasible", "industrial", [], True, 0),
        ("F3", 60, 80, 4, None, "commercial", [(F3, old, False)], True, 0),
        ("F3", 9, 5, 2, None, "residential", [(F3, old, False)], True, 0),
        ("F5", 180, 200, 5, None, "industrial", [(F5, gov, False)], True, 0),
        ("F9", None, 50, 4, None, "commercial", [], True, 0),
        ("MULTI", 30, 30, 3, None, "commercial", [(F3, old, False), (F2, gj, False)], True, 0),
        ("CLEAN", 250, 300, 8, "feasible", "industrial", [], True, 0),
        ("CLEAN", 160, 180, 4, None, "industrial", [], True, 0),
    ])
    # F2: GJ's 10 kW deemed-acceptance ceiling applied to a 40 kW KA application (GJ routes it to a TFR)
    v = r3.feasibility(gov, 40, 5, None)
    c.add("F2", v.ok, stage=TECH, root="feasibility_not_established", decisive=[gov], sl=50, p=40, cat="commercial",
          details=_feas_lines(5, None), computed=v.computed,
          faults=[T(F2, v.ok, r3.feasibility("GJ-C3-005#cl-7-row4", 40, 5, None).ok, [gj],
                    f"other-state {gj} (deemed only up to 10 kW) applied to a 40 kW application", f"Apply {gov}")])
    return out


def dl_feas() -> list[Scenario]:
    deemed, lapse, old, ka = ("DL-C3-016#cl-g3-stage1-deemed", "DL-C3-016#cl-g3-stage1-lapse", "DL-C3-002#cl-g3.3",
                              "KA-C5-006#cl-4-note-ii")
    c = Cluster(lapse, DL, "2026-07-20", "2026-09-28")

    def gov(kw: float, same: bool) -> str:
        return deemed if kw <= 10 and same else lapse

    return _feas_cluster(c, gov, [
        ("CLEAN", 6, 4, 2, None, "residential", [], True, 0),
        ("CLEAN", 30, 40, 18, None, "commercial", [], True, 0),
        ("CLEAN", 30, 40, 9, None, "commercial", [], True, 0),
        ("CLEAN", 50, 60, 12, "infeasible", "commercial", [], True, 0),
        ("F3", 25, 30, 20, None, "commercial", [(F3, old, False)], True, 0),
        ("F3", 8, 5, 3, None, "residential", [(F3, old, False)], True, 0),
        ("F5", 8, 6, 5, None, "residential", [(F5, deemed, False)], False, 0),
        ("F5", 9, 7, 4, None, "residential", [(F5, lapse, False)], True, 0),
        ("F6", 20, 30, 12, None, "commercial", [(F6, "F6", False)], True, 5),
        ("F9", 30, 40, None, None, "commercial", [], True, 0),
        ("MULTI", 7, 5, 2, None, "residential", [(F3, old, False), (F5, lapse, False)], True, 0),
        ("F2", 40, 50, 6, None, "commercial", [(F2, ka, False)], True, 0),
    ])


# ==============================================================================================
# Metering and connectivity clusters
# ==============================================================================================
def _meter_extra(check: bool | None = None, solar: str | None = None, net: str | None = None) -> list[str]:
    out = []
    if check is not None:
        out.append(f"Solar Check Meter: {'Provided (CT-operated, ESCOM-approved vendor)' if check else 'Not provided'}")
    if solar is not None:
        out.append(f"Solar Generation Meter: accuracy class {solar}")
    if net is not None:
        out.append(f"Net Meter: accuracy class {net}")
    return out


def _check_cluster(c: Cluster, gov: str, slots: list[tuple[Any, ...]], extra_rule: str | None = None) -> list[Scenario]:
    """slots: (probed, kW, sanctioned, check provided or None, cat, traps, premises)."""
    for probed, kw, sl, check, cat, traps, prem in slots:
        if check is None:
            c.add("F9", None, stage=EQUIP, root="", decisive=[gov], sl=sl, p=kw, cat=cat, portal="Meter Installation",
                  details=[], extra=["Solar Check Meter: [UNREADABLE - field blank on scanned form]"], premises=prem,
                  reason="F9 missing: whether a check meter is provided is unreadable",
                  faults=[Fault(F9, "check meter field unreadable", ["check_meter"], "Abstain until known")])
            continue
        v = r3.check_meter(gov, kw, check)
        faults = [T(cls, v.ok, r3.check_meter(rule, kw, check).ok, [rule],
                    f"{'superseded' if cls == F3 else 'other-state'} {rule} check-meter threshold applied",
                    f"Apply {gov}", same) for cls, rule, same in traps]
        c.add(probed, v.ok, stage=EQUIP, root="check_meter_missing", decisive=[gov], sl=sl, p=kw, cat=cat,
              portal="Meter Installation", details=[], extra=_meter_extra(check), faults=faults, computed=v.computed,
              premises=prem)
    return c.out


def gj_chk() -> list[Scenario]:
    gov, ka, ka_old, old = "GJ-C3-003#cl-13.5-check", "KA-C5-006#cl-18", "KA-C5-001#cl-15", "GJ-C3-001#cl-13.5-check"
    c = Cluster(gov, GJ, "2024-10-21", "2026-09-01")
    ind, soc = PremisesType.INDIVIDUAL, PremisesType.RWA_COMMON
    out = _check_cluster(c, gov, [
        ("CLEAN", 25, 20, True, "residential", [], ind),
        ("CLEAN", 15, 10, False, "residential", [], ind),
        ("CLEAN", 30, 40, False, "commercial", [], ind),
        ("F2", 35, 40, False, "commercial", [(F2, ka, False)], ind),
        ("F2", 45, 30, False, "residential", [(F2, ka, False)], soc),
        ("F2", 18, 12, False, "residential", [(F2, ka_old, False)], ind),
        ("F9", 28, 30, None, "commercial", [], ind),
        ("CLEAN", 20, 25, False, "commercial", [], ind),
        ("CLEAN", 120, 150, False, "residential", [], soc),
        ("MULTI", 40, 30, False, "residential", [(F2, ka, False), (F3, old, True)], soc),
        ("CLEAN", 60, 50, True, "residential", [], soc),
    ])
    mc = "GJ-C3-003#cl-13.5-class"
    v, m = r3.check_meter(gov, 12, False), r3.meter_class(mc, 2.0, 0.5)
    c.add("F4", v.ok and m.ok, stage=EQUIP, root="meter_accuracy_class_not_compliant", decisive=[gov, mc], sl=15, p=12,
          portal="Meter Installation", details=[], extra=_meter_extra(False, "2.0", "0.5S"), computed=m.computed,
          faults=[Fault(F4, f"{mc} (meter accuracy class) also decides the case", [mc], f"Cite and apply {mc}")])
    return out


def ka_chk() -> list[Scenario]:
    gov, old, gj = "KA-C5-006#cl-18", "KA-C5-001#cl-15", "GJ-C3-003#cl-13.5-check"
    c = Cluster(gov, KA, "2025-12-04", "2026-08-17")
    ind = PremisesType.INDIVIDUAL
    out = _check_cluster(c, gov, [
        ("CLEAN", 40, 50, False, "commercial", [], ind),
        ("CLEAN", 8, 5, False, "residential", [], ind),
        ("CLEAN", 80, 100, False, "commercial", [], ind),
        ("F3", 30, 40, False, "commercial", [(F3, old, False)], ind),
        ("F3", 18, 25, False, "commercial", [(F3, old, False)], ind),
        ("F2", 25, 30, False, "commercial", [(F2, gj, False)], ind),
        ("CLEAN", 120, 150, True, "industrial", [], ind),
        ("F9", 45, 60, None, "commercial", [], ind),
        ("MULTI", 35, 40, False, "commercial", [(F3, old, False), (F2, gj, False)], ind),
        ("CLEAN", 55, 60, False, "commercial", [], ind),
        ("CLEAN", 50, 50, False, "commercial", [], ind),
    ])
    dt = r3.dt_limit("KA-C5-006#cl-4", 100, 50, 45)
    c.add("F4", dt.ok, stage=TECH, root="dt_hosting_limit_exceeded", decisive=[gov, "KA-C5-006#cl-4"], sl=60, p=45,
          cat="commercial", portal="Meter Installation", details=dt_lines(100, 50, 45), extra=_meter_extra(False),
          computed=dt.computed, faults=[Fault(F4, "KA-C5-006#cl-4 (80% DT limit) also decides the case",
                                              ["KA-C5-006#cl-4"], "Cite and apply the DT limit")])
    return out


def gj_mtr() -> list[Scenario]:
    gov, old, chk = "GJ-C3-003#cl-13.5-class", "GJ-C3-001#cl-13.5-class", "GJ-C3-003#cl-13.5-check"
    c = Cluster(gov, GJ, "2024-11-11", "2026-09-14")
    cls_of = {"0.2S": 0.2, "0.5S": 0.5, "1.0": 1.0, "2.0": 2.0}
    soc = PremisesType.RWA_COMMON
    for probed, kw, sl, solar, net, traps, prem in [
        ("CLEAN", 5, 3, "1.0", "0.5S", [], None), ("CLEAN", 10, 12, "0.5S", "0.2S", [], None),
        ("CLEAN", 4, 5, "2.0", "0.5S", [], None), ("CLEAN", 6, 4, "1.0", "1.0", [], None),
        ("F3", 3, 2, "1.0", "0.5S", [(F3, old)], None), ("F3", 15, 20, "0.5S", "0.5S", [(F3, old)], None),
        ("F3", 7, 10, "0.2S", "1.0", [(F3, old)], None), ("F9", 6, 5, None, "0.5S", [], None),
        ("CLEAN", 8, 5, "0.2S", "0.2S", [], None), ("CLEAN", 80, 100, "1.0", "0.5S", [], soc),
        ("F3", 12, 8, "1.0", "0.2S", [(F3, old)], None),
    ]:
        if solar is None:
            c.add("F9", None, stage=EQUIP, root="", decisive=[gov], sl=sl, p=kw, portal="Meter Installation", details=[],
                  extra=["Solar Generation Meter: accuracy class [UNREADABLE]", f"Net Meter: accuracy class {net}"],
                  reason="F9 missing: the solar meter's accuracy class is unreadable",
                  faults=[Fault(F9, "meter class unreadable", ["solar_meter_class"], "Abstain until known")])
            continue
        v = r3.meter_class(gov, cls_of[solar], cls_of[net])
        faults = [T(cl, v.ok, r3.meter_class(rule, cls_of[solar], cls_of[net]).ok, [rule],
                    f"superseded {rule} (0.2s solar meter) applied", f"Apply {gov}") for cl, rule in traps]
        c.add(probed, v.ok, stage=EQUIP, root="meter_accuracy_class_not_compliant", decisive=[gov], sl=sl, p=kw,
              portal="Meter Installation", details=[], extra=_meter_extra(None, solar, net), faults=faults,
              computed=v.computed, premises=prem or PremisesType.INDIVIDUAL)
    v, k = r3.meter_class(gov, 1.0, 0.5), r3.check_meter(chk, 25, False)
    c.add("F4", v.ok and k.ok, stage=EQUIP, root="check_meter_missing", decisive=[gov, chk], sl=30, p=25,
          portal="Meter Installation", details=[], extra=_meter_extra(False, "1.0", "0.5S"), computed=k.computed,
          faults=[Fault(F4, f"{chk} (check meter above 20 kW) also decides the case", [chk], f"Cite and apply {chk}")])
    return c.out


def ka_phase() -> list[Scenario]:
    gov, old, tn = "KA-C3-001#cl-6a", "KA-C3-001#cl-6a-2016-quoted", "TN-C5-001#cl-3"
    c = Cluster(gov, KA, "2025-12-10", "2026-08-11")
    label = {"LT-1ph": "230 V single phase (LT)", "LT-3ph": "400 V three phase (LT)", "HT": "11 kV (HT)"}
    for probed, kw, sl, req, cat, traps in [
        ("CLEAN", 4, 3, "LT-1ph", "residential", []), ("CLEAN", 30, 40, "LT-3ph", "commercial", []),
        ("CLEAN", 200, 250, "LT-3ph", "industrial", []), ("F3", 80, 100, "LT-3ph", "commercial", [(F3, old)]),
        ("F3", 140, 150, "LT-3ph", "commercial", [(F3, old)]), ("F2", 125, 130, "LT-3ph", "commercial", [(F2, tn)]),
        ("F6", 60, 160, "LT-3ph", "commercial", [(F6, "sl")]), ("F9", 90, 100, None, "commercial", []),
        ("MULTI", 130, 150, "LT-3ph", "commercial", [(F3, old), (F2, tn)]),
        ("CLEAN", 160, 180, "LT-3ph", "industrial", []), ("CLEAN", 7, 5, "LT-3ph", "residential", []),
    ]:
        if req is None:
            c.add("F9", None, stage=TECH, root="", decisive=[gov], sl=sl, p=kw, cat=cat, details=[],
                  extra=["Requested Connectivity: [UNREADABLE - section torn]"],
                  reason="F9 missing: the requested connectivity voltage is unreadable",
                  faults=[Fault(F9, "requested voltage unreadable", ["connectivity_level"], "Abstain until known")])
            continue
        v = r3.voltage_level(gov, kw, req)
        faults = []
        for cl, rule in traps:
            if rule == "sl":
                faults.append(T(F6, v.ok, r3.voltage_level(gov, sl, req).ok, ["proposed_capacity_kw"],
                                "binding sanctioned load instead of plant capacity to the voltage table",
                                f"Bind the plant capacity ({kw} kW)"))
            else:
                faults.append(T(cl, v.ok, r3.voltage_level(rule, kw, req).ok, [rule],
                                f"{'superseded' if cl == F3 else 'other-state'} {rule} voltage table applied",
                                f"Apply {gov}"))
        c.add(probed, v.ok, stage=TECH, root="connectivity_voltage_level_mismatch", decisive=[gov], sl=sl, p=kw,
              cat=cat, details=[], extra=[f"Requested Connectivity: {label[req]}"], faults=faults, computed=v.computed)
    dt = r3.dt_limit("KA-C5-006#cl-4", 250, 120, 100)
    c.add("F4", dt.ok and r3.voltage_level(gov, 100, "LT-3ph").ok, stage=TECH, root="dt_hosting_limit_exceeded",
          decisive=[gov, "KA-C5-006#cl-4"], sl=120, p=100, cat="commercial", details=dt_lines(250, 120, 100),
          extra=[f"Requested Connectivity: {label['LT-3ph']}"], computed=dt.computed,
          faults=[Fault(F4, "KA-C5-006#cl-4 (80% DT limit) also decides the case", ["KA-C5-006#cl-4"],
                        "Cite and apply the DT limit")])
    return c.out


# ==============================================================================================
# Central clusters: ALMM List-II window, PM Surya Ghar Phase-II claim window; UP augmentation charge
# ==============================================================================================
def in_almm2() -> list[Scenario]:
    gov, giu, btm, old, old2, l1 = ("IN-C2-013#cl-1b", "IN-C2-013#cl-1b-giu", "IN-C2-013#cl-1e", "IN-C2-008#cl-8",
                                    "IN-C2-011#cl-7", "IN-C2-002#cl-1")
    c = Cluster(gov, GJ, "2026-08-05", "2026-09-28")

    def extra(l2: bool | None, comm: str, giu_case: bool) -> list[str]:
        cells = {True: "ALMM List-II enlisted (domestic cells)", False: "Not in ALMM List-II (imported cells)",
                 None: "[UNREADABLE - datasheet page missing]"}[l2]
        return [f"Solar PV Cells: {cells}", f"Scheduled Commissioning Date: {comm}",
                "Scheme: PM Surya Ghar 'Give It Up' subsidy option, applied on the PMSG National Portal" if giu_case
                else "Scheme: none (self-financed net-metering project)"]

    for probed, st, cat, sl, p, l2, comm, giu_case, traps, modules in [
        ("CLEAN", GJ, "residential", 3, 5, False, "2026-11-20", False, [], True),
        ("CLEAN", KA, "residential", 6, 8, True, "2027-02-10", False, [], True),
        ("CLEAN", DL, "commercial", 60, 50, False, "2027-01-15", False, [], True),
        ("CLEAN", UP, "commercial", 40, 30, False, "2027-02-01", False, [], True),
        ("F3", GJ, "residential", 6, 10, False, "2026-09-30", False, [(F3, old, False)], True),
        ("F3", DL, "commercial", 50, 40, False, "2026-12-15", False, [(F3, old2, False)], True),
        ("F5", UP, "commercial", 30, 25, False, "2027-02-20", False, [(F5, giu, False)], True),
        ("F5", KA, "residential", 4, 6, False, "2027-03-10", True, [(F5, "nogiu", False)], True),
        ("F5", GJ, "residential", 8, 12, False, "2027-01-10", False, [(F5, btm, False)], True),
        ("F9", DL, "commercial", 40, 30, None, "2027-01-20", False, [], True),
        ("MULTI", DL, "commercial", 25, 20, False, "2027-03-01", False, [(F5, giu, False), (F3, old, True)], True),
        ("CLEAN", UP, "residential", 5, 4, False, "2026-10-30", False, [], True),
        ("F4", KA, "residential", 5, 7, True, "2027-01-05", False, [(F4, l1, False)], False),
    ]:
        decisive = [gov, giu] if giu_case else [gov]
        if l2 is None:
            c.add("F9", None, stage=EQUIP, root="", decisive=decisive, sl=sl, p=p, cat=cat, state=st,
                  portal="Equipment Verification", details=[], extra=extra(l2, comm, giu_case), dcr=False,
                  reason="F9 missing: whether the cells are on ALMM List-II is unreadable",
                  faults=[Fault(F9, "cell enlistment unreadable", ["cells_list2"], "Abstain until known")])
            continue
        v = r3.almm_list2(gov, comm, l2, giu_residential=giu_case)
        ok = v.ok and modules
        faults = []
        for cl, rule, same in traps:
            if cl == F4:
                decisive = [*decisive, rule]
                faults.append(Fault(F4, f"{rule} (ALMM List-I modules) also decides the case", [rule],
                                    "Cite and apply ALMM List-I for modules"))
                continue
            if rule == "nogiu":
                trap, ev, what = r3.almm_list2(gov, comm, l2, giu_residential=False).ok, [gov], \
                    "the general 31.12.2026 net-metering window applied to a Give It Up residential case"
            else:
                trap, ev = r3.almm_list2(rule, comm, l2, giu_residential=False).ok, [rule]
                what = {F3: f"superseded {rule} (List-II from 01.06.2026)", F5: f"inapplicable {rule}"}[cl]
            faults.append(T(cl, ok, trap and modules, ev, what, f"Apply {gov}", same))
        c.add(probed, ok, stage=EQUIP, root="almm_list2_cells_required" if not v.ok else "non_almm_modules",
              decisive=decisive, sl=sl, p=p, cat=cat, state=st, portal="Equipment Verification", details=[],
              extra=extra(l2, comm, giu_case), almm=modules, dcr=l2, faults=faults, computed=v.computed,
              nfos=[("currency", f"{gov} is in force at the case date"),
                    ("jurisdiction", "ALMM orders are central and govern every state")])
    return c.out


def in_pmsg() -> list[Scenario]:
    gov, old, split, dcr = ("IN-C1-001#cl-annex1-ii-amended", "IN-C1-011#cl-annex-phase2-claims",
                            "IN-C1-001#cl-phase2-pmsg-split", "IN-C1-001#cl-5.1m")
    c = Cluster(gov, GJ, "2025-07-14", "2026-09-22")

    def extra(app: str, claim: str | None, installed: bool, phase2: bool) -> list[str]:
        prog = "Rooftop Solar Programme Phase-II" if phase2 else "PM Surya Ghar: Muft Bijli Yojana"
        return [f"Programme: {prog} (application submitted {app})",
                f"CFA Claim Received On: {claim or '[UNREADABLE - stamp illegible]'}",
                f"Installation Status as on 01.04.2025: {'Installed and inspected' if installed else 'Not installed'}"]

    for probed, st, sl, p, app, claim, inst, dcr_ok, traps in [
        ("CLEAN", GJ, 2, 3, "2023-11-10", "2025-08-20", True, True, []),
        ("CLEAN", KA, 4, 3, "2023-09-04", "2026-01-15", True, True, []),
        ("CLEAN", DL, 3, 2, "2024-01-22", "2025-09-10", False, True, []),
        ("F3", UP, 5, 3, "2023-12-18", "2025-03-05", True, True, [(F3, old)]),
        ("F3", GJ, 3, 5, "2023-10-02", "2025-11-28", True, True, [(F3, old)]),
        ("F5", KA, 3, 4, "2024-05-20", "2026-02-10", True, True, [(F5, gov)]),
        ("F5", DL, 4, 3, "2024-09-01", "2026-06-30", True, True, [(F5, gov)]),
        ("F6", GJ, 2, 4, "2023-12-05", "2026-02-16", True, True, [(F6, "app")]),
        ("F9", UP, 3, 2, "2023-08-28", None, True, True, []),
        ("CLEAN", UP, 2, 2, "2024-01-20", "2025-12-31", True, True, []),
        ("F4", KA, 3, 3, "2024-07-11", "2025-10-06", True, False, [(F4, dcr)]),
        ("CLEAN", GJ, 6, 4, "2023-07-17", "2026-04-01", True, True, []),
    ]:
        phase2 = app < "2024-02-13"
        governing = gov if phase2 else split
        k = len(c.out)
        when = (c.start + _dt.timedelta(days=(k * 37) % c.span)).isoformat()
        after = (_dt.date.fromisoformat(claim or "2025-06-01") + _dt.timedelta(days=30)).isoformat()
        date = max(when, after)
        decisive = [governing]
        if claim is None:
            c.add("F9", None, stage=SUBSIDY, root="", decisive=decisive, sl=sl, p=p, state=st, subsidy=True, date=date,
                  portal="Subsidy Claim Review", details=["Scheme: CFA for residential rooftop solar"],
                  extra=extra(app, claim, inst, phase2), reason="F9 missing: the claim receipt date is unreadable",
                  faults=[Fault(F9, "claim date unreadable", ["claim_date"], "Abstain until known")])
            continue
        v = r3.phase2_claim(governing, app, claim, inst)
        ok = v.ok and dcr_ok
        faults = []
        for cl, rule in traps:
            if cl == F4:
                decisive.append(rule)
                faults.append(Fault(F4, f"{rule} (DCR condition) also decides the case", [rule], "Cite and apply DCR"))
            elif rule == "app":
                faults.append(T(F6, ok, r3.phase2_claim(gov, app, app, inst).ok, ["claim_date"],
                                "binding the application date as the claim date", f"Bind the claim date ({claim})"))
            else:
                trap = r3.phase2_claim(rule, app, claim, inst).ok
                what = (f"superseded {rule} (claims till October 2024)" if cl == F3 else
                        "Phase-II claim window applied to a PM Surya Ghar application")
                faults.append(T(cl, ok, trap, [rule], what, f"Apply {governing}"))
        c.add(probed, ok, stage=SUBSIDY, root="cfa_claim_not_admissible" if v.ok is False else "non_dcr_modules_for_cfa",
              decisive=decisive, sl=sl, p=p, state=st, subsidy=True, dcr=dcr_ok, portal="Subsidy Claim Review", date=date,
              details=["Scheme: CFA for residential rooftop solar"], extra=extra(app, claim, inst, phase2),
              faults=faults, computed=v.computed,
              nfos=[("currency", f"{governing} is in force at the case date"),
                    ("jurisdiction", "PM Surya Ghar guidelines are central and govern every state")])
    return c.out


def up_aug() -> list[Scenario]:
    gov, cap = "UP-C3-002#cl-6.2-proviso2", "UP-C3-002#cl-5.1"
    c = Cluster(gov, UP, "2023-04-03", "2026-09-25")

    def lines(aug: bool, paid: int) -> list[str]:
        return [f"Augmentation of DT/Network Required: {'Yes' if aug else 'No'}",
                f"One-time Augmentation Charge Paid: Rs {paid:,}"]

    for probed, kw, sl, aug, paid, traps in [
        ("CLEAN", 15, 20, True, 5000, []), ("CLEAN", 16, 20, True, 5000, []),
        ("CLEAN", 25, 30, True, 10000, []), ("CLEAN", 40, 50, False, 0, []),
        ("F6", 18, 25, True, 8000, ["F6"]), ("F6", 12, 15, True, 2000, ["F6"]),
        ("F5", 30, 40, False, 0, ["F5"]), ("F9", None, 20, True, 3000, []),
        ("CLEAN", 60, 80, True, 0, []), ("CLEAN", 10, 10, True, 0, []), ("CLEAN", 11, 15, True, 0, []),
    ]:
        if kw is None:
            c.add("F9", None, stage=REG, root="", decisive=[gov], sl=sl, p=kw, portal="Registration",
                  details=lines(aug, paid), reason="F9 missing: the capacity that sets the charge is unreadable",
                  faults=[Fault(F9, "capacity unreadable", ["proposed_capacity_kw"], "Abstain until legible")])
            continue
        v = r3.up_augmentation(gov, kw, aug, paid)
        faults = []
        for t in traps:
            if t == "F6":
                faults.append(T(F6, v.ok, paid >= 1000 * kw, ["proposed_capacity_kw"],
                                "charging Rs 1000/kWp on the whole capacity instead of the capacity beyond 10 kWp",
                                "Charge only the capacity beyond 10 kWp"))
            else:
                faults.append(T(F5, v.ok, r3.up_augmentation(gov, kw, True, paid).ok, [gov],
                                "the augmentation charge applied where no augmentation is required",
                                "No charge when augmentation is not required"))
        c.add(probed, v.ok, stage=REG, root="augmentation_charge_unpaid", decisive=[gov], sl=sl, p=kw,
              cat="commercial" if kw > 10 else "residential", portal="Registration", details=lines(aug, paid),
              faults=faults, computed=v.computed)
    v, k = r3.up_augmentation(gov, 12, True, 2000), r3.capacity(cap, 10, 12)
    c.add("F4", v.ok and k.ok, stage=TECH, root="capacity_limit_exceeded", decisive=[gov, cap], sl=10, p=12,
          portal="Registration", details=lines(True, 2000), computed=k.computed,
          faults=[Fault(F4, f"{cap} (capacity cap) also decides the case", [cap], f"Cite and apply {cap}")])
    return c.out


# ==============================================================================================
# Rule groups added for the v3 candidate (T1, 2026-10-04; D38): staging clauses whose predecessor has a link in
# the non-gold registry, explicit links first. Each is built so that at least four applications can carry an
# outdated-rule pair (the anchor decides the case and the predecessor is superseded at the case date).
# ==============================================================================================
def gj_band() -> list[Scenario]:
    gov, free, old, up = "GJ-C3-004#cl-6.2a", "GJ-C3-004#cl-6.2c-ii", "GJ-C3-003#cl-6.2", "UP-C3-002#cl-5.1"
    c = Cluster(gov, GJ, "2024-10-14", "2026-09-21")
    captive = ["Use of Generation: Captive consumption under net metering (non-residential)"]
    for probed, sl, p, cat, traps in [
        ("CLEAN", 40, 15, "commercial", []), ("CLEAN", 100, 80, "industrial", []),
        ("CLEAN", 600, 1200, "industrial", []), ("CLEAN", 10, 0.5, "commercial", []),
        ("F3", 30, 25, "commercial", [(F3, old, False)]), ("F3", 200, 180, "industrial", [(F3, old, False)]),
        ("F3", 50, 60, "commercial", [(F3, old, False)]), ("F2", 20, 30, "commercial", [(F2, up, False)]),
        ("F9", 60, None, "commercial", []), ("CLEAN", 300, 120, "industrial", []),
        ("MULTI", 80, 70, "commercial", [(F3, old, False), (F2, up, True)]),
    ]:
        if p is None:
            c.add("F9", None, stage=TECH, root="", decisive=[gov, free], sl=sl, p=p, cat=cat, details=[], extra=captive,
                  reason="F9 missing: the proposed capacity is unreadable",
                  faults=[Fault(F9, "proposed capacity unreadable", ["proposed_capacity_kw"], "Abstain until legible")])
            continue
        v = r3.capacity(gov, sl, p)
        faults = [T(cls, v.ok, r3.capacity(rule, sl, p).ok, [rule],
                    f"{'superseded' if cls == F3 else 'other-state'} {rule} applied to the capacity limit",
                    f"Apply {gov} with {free}", same) for cls, rule, same in traps]
        c.add(probed, v.ok, stage=TECH, root="capacity_limit_exceeded", decisive=[gov, free], sl=sl, p=p, cat=cat,
              details=[], extra=captive, faults=faults, computed=v.computed)
    return c.out


def up_feas() -> list[Scenario]:
    gov, old, ka = "IN-C3-001#cl-11.7", "IN-C3-002#cl-11.7", "KA-C5-006#cl-4-note-ii"
    c = Cluster(gov, UP, "2024-03-04", "2026-09-15")
    # UPERC's 2019 regulations set no feasibility period, so the central rule decides; only systems above 10 kW,
    # which rule 11(7A) does not deem accepted.
    return _feas_cluster(c, lambda _kw, _s: gov, [
        ("CLEAN", 25, 30, 18, None, "commercial", [], True, 0),
        ("CLEAN", 40, 50, 9, None, "commercial", [], True, 0),
        ("CLEAN", 60, 80, 12, "feasible", "commercial", [], True, 0),
        ("CLEAN", 15, 20, 20, "infeasible", "commercial", [], True, 0),
        ("F3", 30, 40, 19, None, "commercial", [(F3, old, False)], True, 0),
        ("F3", 80, 100, 25, None, "industrial", [(F3, old, False)], True, 0),
        ("F3", 12, 15, 16, None, "residential", [(F3, old, False)], True, 0),
        ("F2", 50, 60, 10, None, "commercial", [(F2, ka, False)], True, 0),
        ("F6", 20, 25, 14, None, "commercial", [(F6, "F6", False)], True, 3),
        ("F9", 30, 40, None, None, "commercial", [], True, 0),
        ("MULTI", 35, 40, 21, None, "commercial", [(F3, old, False), (F2, ka, True)], True, 0),
        ("CLEAN", 150, 200, 30, "feasible", "industrial", [], True, 0),
    ])


VNM_TYPES = {  # consumer type -> (tariff category, line on the proposal)
    "domestic": ("residential", "Participating consumers: domestic connections in one housing society"),
    "charitable": ("commercial", "Participating consumers: school run by a registered charitable trust"),
    "government": ("commercial", "Participating consumers: offices of a Government department"),
    "commercial": ("commercial", "Participating consumers: commercial shops in one market association"),
    "industrial": ("industrial", "Participating consumers: industrial units in one estate"),
}


def dl_vnm_all() -> list[Scenario]:
    gov, old, cap = "DL-C3-015#cl-3.2", "DL-C3-006#cl-3.2", "DL-C3-009#cl-3.8"
    c = Cluster(gov, DL, "2026-01-26", "2026-09-25")
    common: dict[str, Any] = {"stage": METER_MODE, "portal": "Metering Arrangement Approval",
                              "metering": "Virtual Net Metering (ground-mounted RE system)"}
    for probed, kind, sl, p, traps in [
        ("CLEAN", "domestic", 40, 150, []), ("CLEAN", "government", 100, 300, []),
        ("F3", "commercial", 60, 200, [(F3, old, False)]), ("F3", "industrial", 300, 900, [(F3, old, False)]),
        ("F3", "commercial", 30, 120, [(F3, old, False)]), ("CLEAN", "charitable", 50, 200, []),
        ("CLEAN", "industrial", 200, 700, []), ("CLEAN", "commercial", 20, 150, []),
        ("CLEAN", "domestic", 30, 200, []), ("F9", None, 50, 150, []),
        ("F3", "commercial", 80, 500, [(F3, old, True)]),
    ]:
        if kind is None:
            c.add("F9", None, root="", decisive=[gov], sl=sl, p=p, cat="commercial", details=[],
                  extra=["Participating consumers: [UNREADABLE - category column blank]"],
                  reason="F9 missing: the participating consumers' category is unreadable",
                  faults=[Fault(F9, "consumer category unreadable", ["consumer_category"], "Abstain until legible")],
                  **common)
            continue
        cat, line = VNM_TYPES[kind]
        v, k = r3.vnm_applicability(gov, kind), r3.capacity(cap, sl, p, ground_mounted=True)
        ok = v.ok and k.ok
        decisive = [gov] if k.ok else [gov, cap]
        faults = [T(F3, ok, r3.vnm_applicability(rule, kind).ok and k.ok, [rule],
                    f"superseded {rule} applied to VNM eligibility", f"Apply {gov}", same) for _, rule, same in traps]
        c.add(probed, ok, root="vnm_not_applicable" if not v.ok else "capacity_limit_exceeded", decisive=decisive,
              sl=sl, p=p, cat=cat, details=[], extra=[line], faults=faults, computed={**v.computed, **k.computed},
              **common)
    return c.out


def dl_vnm_change() -> list[Scenario]:
    gov, old = "DL-C3-015#cl-9.2b", "DL-C3-004#cl-9.2b"
    c = Cluster(gov, DL, "2026-02-02", "2026-09-28")

    def lines(n: int | None, notice: int) -> list[str]:
        return ["Request: add a participating service connection to the existing VNM arrangement (MoU on file)",
                f"Share/Participant Changes Already Made This Financial Year: {n if n is not None else '[ILLEGIBLE]'}",
                f"Advance Notice Given: {notice} months"]

    for probed, n, notice, traps in [
        ("CLEAN", 0, 2, []), ("CLEAN", 0, 3, []), ("CLEAN", 0, 1, []), ("CLEAN", 2, 2, []),
        ("F3", 1, 2, [(F3, old, False)]), ("F3", 1, 3, [(F3, old, False)]), ("F3", 1, 4, [(F3, old, False)]),
        ("F9", None, 2, []), ("CLEAN", 1, 1, []), ("CLEAN", 2, 3, []), ("F3", 0, 2, [(F3, old, True)]),
    ]:
        common: dict[str, Any] = {"stage": METER_MODE, "portal": "VNM Arrangement Modification", "sl": 50, "p": 150,
                                  "cat": "commercial", "details": lines(n, notice),
                                  "metering": "Virtual Net Metering (ground-mounted RE system)"}
        if n is None:
            c.add("F9", None, root="", decisive=[gov], reason="F9 missing: the number of changes already made this "
                  "financial year is illegible", faults=[Fault(F9, "change count illegible", ["changes_this_fy"],
                                                               "Abstain until legible")], **common)
            continue
        v = r3.vnm_change(gov, n, notice)
        faults = [T(F3, v.ok, r3.vnm_change(rule, n, notice).ok, [rule], f"superseded {rule} applied to the number of "
                    "changes allowed in a financial year", f"Apply {gov}", same) for _, rule, same in traps]
        c.add(probed, v.ok, root="vnm_change_not_permitted", decisive=[gov], faults=faults, computed=v.computed,
              **common)
    return c.out


def dl_sld_waiver() -> list[Scenario]:
    gov, old = "DL-C3-015#cl-3.6", "DL-C3-009#cl-3.6"
    c = Cluster(gov, DL, "2026-01-27", "2026-09-26")
    for probed, paid, mw, ht, traps in [
        ("CLEAN", False, 60, False, []), ("F3", False, 80, False, [(F3, old, False)]),
        ("F3", False, 95, False, [(F3, old, False)]), ("CLEAN", True, 120, False, []),
        ("CLEAN", False, 130, False, []), ("F3", False, 70, False, [(F3, old, False)]),
        ("CLEAN", False, 50, True, []), ("CLEAN", False, 40, False, []),
        ("F9", False, None, False, []), ("CLEAN", False, 105, False, []),
        ("F3", False, 100, False, [(F3, old, False)]), ("F3", True, 90, False, [(F3, old, True)]),
    ]:
        discom = DISCOMS[DL][len(c.out) % len(DISCOMS[DL])].value  # the DISCOM Cluster.add assigns to this slot
        details = [f"Connection Voltage of RE System: {'33 kV' if ht else '11 kV'}",
                   f"Cumulative VNM/GNM Capacity in {discom} incl. this project: "
                   + (f"{mw} MW" if mw is not None else "[NOT PUBLISHED ON PORTAL]"),
                   f"Service Line cum Development (SLD) Charges: {'Paid' if paid else 'Not paid'}"]
        common: dict[str, Any] = {"stage": REG, "portal": "Registration", "sl": 100, "p": 400, "cat": "commercial",
                                  "details": details, "metering": "Group Net Metering (ground-mounted RE system)"}
        if mw is None:
            c.add("F9", None, root="", decisive=[gov], reason="F9 missing: the DISCOM's cumulative VNM/GNM capacity, "
                  "which decides the SLD waiver, is not published", faults=[Fault(
                      F9, "cumulative capacity unknown", ["cumulative_vnm_gnm_mw"], "Abstain until known")], **common)
            continue
        v = r3.sld_waiver(gov, discom, mw, paid, not ht)
        faults = [T(F3, v.ok, r3.sld_waiver(rule, discom, mw, paid, not ht).ok, [rule],
                    f"superseded {rule} applied to the SLD waiver cap", f"Apply {gov}", same) for _, rule, same in traps]
        c.add(probed, v.ok, root="sld_charges_unpaid", decisive=[gov], faults=faults, computed=v.computed, **common)
    return c.out


BUILDERS_V3: dict[str, Callable[[], list[Scenario]]] = {
    "GJ-C3-004#cl-6.2c-i": gj_cap, "GJ-C3-003#cl-5-proviso": gj_dt, "GJ-C3-005#cl-7-proviso": gj_feas,
    "GJ-C3-003#cl-13.5-check": gj_chk, "GJ-C3-003#cl-13.5-class": gj_mtr,
    "KA-C3-001#cl-6a": ka_phase, "KA-C5-006#cl-18": ka_chk, "KA-C5-006#cl-4-note-ii": ka_feas,
    "KA-C5-006#cl-4": ka_dt, "KA-C4-001#cl-1": ka_sl10,
    "TN-C5-002#cl-I.2": tn_cap, "TN-C5-002#cl-VII.3": tn_dt,
    "DL-C3-016#cl-g3-stage1-lapse": dl_feas, "DL-C3-009#cl-3.8": dl_vnm, "DL-C3-001#cl-5.4": dl_sld,
    "UP-C3-002#cl-6.2": up_dt, "UP-C3-002#cl-5.1": up_cap, "UP-C3-002#cl-6.2-proviso2": up_aug,
    "IN-C2-013#cl-1b": in_almm2, "IN-C1-001#cl-annex1-ii-amended": in_pmsg,
}
TEST_V3_CLUSTERS = list(BUILDERS_V3)  # the 20 rule groups of the candidate v2 split (its ids depend on this list)
# Added for the candidate v3 split (D38); generated under their own seed so the v2 ids above never move.
ADDED_V3_CLUSTERS = {
    "GJ-C3-004#cl-6.2a": gj_band, "IN-C3-001#cl-11.7": up_feas, "DL-C3-015#cl-3.2": dl_vnm_all,
    "DL-C3-015#cl-9.2b": dl_vnm_change, "DL-C3-015#cl-3.6": dl_sld_waiver,
}
BUILDERS_V3.update(ADDED_V3_CLUSTERS)
# Dropped 2026-10-01 (R3 report, R3-INTEGRATION-REPORT): this F5 trap plants a sentence of the governing clause
# DL-C3-009#cl-3.8 itself, so evidence-level scoring cannot tell trap from anchor. The slot still draws its id,
# so every other case keeps its id and position. (cluster, fault trigger) pairs.
DROPPED_SLOTS = {
    ("DL-C3-009#cl-3.8", "the rooftop no-cap sentence applied to a ground-mounted system"),
    # Same defect, dropped by the orchestrator 2026-10-01 (R3-INTEGRATION-REPORT): each plants its own deciding clause.
    ("UP-C3-002#cl-6.2-proviso2", "the augmentation charge applied where no augmentation is required"),
    ("IN-C2-013#cl-1b", "the general 31.12.2026 net-metering window applied to a Give It Up residential case"),
}


def load_r3_graph() -> SupersessionGraph:
    with open(CORPUS_R3_DIR / "graph" / "supersession.json", encoding="utf-8") as f:
        return SupersessionGraph.model_validate(json.load(f))


def generate_v3_cases(graph: SupersessionGraph, clusters: list[str] | None = None, seed: str = V3_SEED) -> list[BenchmarkCase]:
    """Opaque seeded ids, shuffled slots within and across clusters (D13), cluster_id set (hidden from arms)."""
    clusters = clusters or TEST_V3_CLUSTERS
    rng = random.Random(f"{seed}|{'|'.join(clusters)}")
    pairs = []
    for n in clusters:
        scs = BUILDERS_V3[n]()
        rng.shuffle(scs)
        pairs += [(n, i, sc) for i, sc in enumerate(scs, start=1)]
    rng.shuffle(pairs)
    ids: set[str] = set()
    cases = []
    for n, i, sc in pairs:
        cid = f"SB-{rng.getrandbits(32):08x}"
        while cid in ids:
            cid = f"SB-{rng.getrandbits(32):08x}"
        ids.add(cid)
        if any((n, f.trigger) in DROPPED_SLOTS for f in sc.faults):
            continue
        cases.append(_render(n, i, sc, graph, opaque_id=cid, corpus_version=CORPUS_VERSION_R3, names=NAMES[sc.state]))
    validate_benchmark_suite(cases)
    return cases


V3_ADDED_SEED = "SuryaBench-v3-test-candidate-added-2026-10"


def generate_v3_pool(graph: SupersessionGraph) -> list[BenchmarkCase]:
    """Every case the candidate v3 split draws from: the 20 v2 rule groups (their v2 ids unchanged) and the groups
    added in D38 (their own seed)."""
    pool = generate_v3_cases(graph) + generate_v3_cases(graph, list(ADDED_V3_CLUSTERS), seed=V3_ADDED_SEED)
    assert len({c.case_id for c in pool}) == len(pool), "case id collision between the v2 and the added groups"
    return pool


def save_candidate(output_dir: Path | None = None) -> str:
    """Write the candidate test split and its sha256 file; returns the digest. Not sealed: labels provisional."""
    out_dir = output_dir or BENCHMARK_DIR
    text = json.dumps([c.model_dump(mode="json") for c in generate_v3_cases(load_r3_graph())], indent=2)
    (out_dir / CANDIDATE_FILE).write_text(text, encoding="utf-8", newline="\n")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    (out_dir / CANDIDATE_FILE.replace(".json", ".sha256")).write_text(f"{digest}  {CANDIDATE_FILE}\n",
                                                                      encoding="utf-8", newline="\n")
    return digest
