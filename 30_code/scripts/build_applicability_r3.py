"""Write 40_data/corpus_r3/graph/applicability.json: the r2 predicates plus predicates for the r3 clause nodes
used by the new clusters (decisive clauses, F5 traps, controlled-exposure A siblings).

Same schema and convention as r2 (``applicability/schema.py``; ``build_supersession_graph.py``): a predicate
states when the clause governs a case, over the closed CaseFacts vocabulary. Where a condition of the clause has
no CaseFacts field (REC mechanism, ground mounting, supply-type change, Give It Up option, behind-the-meter),
the predicate keeps only what the facts can express and is marked ``medium`` (or ``low``) confidence. It is
written so that ``false`` means "clearly does not apply": exposure condition A plants a sibling only where its
predicate is false, so an inexpressible condition errs towards "applies" (the case is then skipped).

UNVERIFIED like every r3 item: predicates follow the agent's reading of the clause text quoted in
``supersession.json``; they are checked by ``tests/unit/test_r3_integration.py`` against the rule-function
labels (every decisive clause's predicate holds on every case it decides).

Run after ``build_corpus_r3.py`` (which copies r2's file):
    python 30_code/scripts/build_applicability_r3.py
"""

import json
from typing import Any

from suryabench.applicability.schema import ApplicabilityPredicate
from suryabench.paths import CORPUS_DIR, CORPUS_R3_DIR

NET_MODES = ["net", "net_billing"]
ALL_GRID_MODES = ["net", "gross", "net_billing"]


def leaf(field: str, op: str, value: Any) -> dict[str, Any]:
    return {"field": field, "op": op, "value": value}


def st(code: str) -> dict[str, Any]:
    return leaf("state", "eq", code)


def kw(op: str, value: float) -> dict[str, Any]:
    return leaf("proposed_capacity_kw", op, value)


# node_id: (conditions (AND), basis, confidence)
R3_PREDICATES: dict[str, tuple[list[dict[str, Any]], str, str]] = {
    # Gujarat (GERC)
    "GJ-C3-004#cl-6.2c-i": ([st("GJ"), leaf("consumer_category", "eq", "residential")],
                            "GERC 2022: residential rooftop projects allowed irrespective of sanctioned load", "high"),
    "GJ-C3-004#cl-6.2c-iii": ([st("GJ"), leaf("consumer_category", "in", ["commercial", "industrial"])],
                              "GERC 2022: REC-mechanism captive / third-party projects capped at sanctioned load "
                              "(REC participation is not a case fact; residential rooftop is never under it)", "medium"),
    "GJ-C3-004#cl-6.2a": ([st("GJ"), leaf("metering_mode", "eq", "net")],
                          "GERC 2022: net-metering rooftop systems of 1 kW up to 1000 kW", "high"),
    "GJ-C3-003#cl-5-proviso": ([st("GJ")], "GERC 2020: cumulative capacity on a DT up to the DT capacity", "high"),
    "GJ-C3-005#cl-7-proviso": ([st("GJ"), kw("lte", 10)],
                               "GERC 2024 proviso: applications up to 10 kW deemed accepted without a feasibility study",
                               "high"),
    "GJ-C3-005#cl-7-row4": ([st("GJ"), kw("gt", 10)],
                            "GERC 2024 timeline row 4: registration letter for the TFR (applications above 10 kW, "
                            "which are not deemed accepted)", "medium"),
    "GJ-C3-003#cl-13.5-check": ([st("GJ")], "GERC 2020: check meter mandatory above 20 kW (the threshold decides "
                                "compliance, the clause governs every GJ rooftop meter installation)", "high"),
    "GJ-C3-003#cl-13.5-class": ([st("GJ")], "GERC 2020: accuracy class of the solar and net meters", "high"),
    # Karnataka (KERC, BESCOM)
    "KA-C3-001#cl-6a": ([st("KA"), kw("lte", 2000)], "KERC 2023: voltage level of interconnection by capacity, up to "
                        "2000 kW", "high"),
    "KA-C3-001#cl-6f": ([st("KA"), kw("gt", 150)], "KERC 2023: plants above 150 kW connect to the 11 kV system; "
                        "80% feeder limit", "high"),
    "KA-C3-001#cl-l-feasibility": ([st("KA"), kw("gt", 150)], "KERC 2023 timeline: site verification / feasibility "
                                   "within 10 working days (plants above 150 kW, which are not deemed feasible)", "medium"),
    "KA-C4-001#cl-1": ([st("KA"), leaf("consumer_category", "eq", "residential")],
                       "KERC 05.12.2024: domestic consumers may install up to 10 kW with automatic sanctioned-load "
                       "enhancement (the 10 kW bound decides compliance)", "medium"),
    "KA-C5-006#cl-18": ([st("KA")], "BESCOM 2025: check meter for DSPV systems above 50 kWp (threshold decides "
                        "compliance)", "high"),
    "KA-C5-006#cl-4": ([st("KA"), kw("lte", 150)], "BESCOM 2025: 80% DT limit, applicable only to LT plants up to "
                       "150 kW", "high"),
    "KA-C5-006#cl-4-note-ii": ([st("KA"), kw("lte", 150)], "BESCOM 2025: plants up to 150 kW deemed feasible", "high"),
    # Tamil Nadu (TANGEDCO)
    "TN-C5-002#cl-I.2": ([st("TN"), leaf("consumer_category", "neq", "agricultural"),
                          leaf("metering_mode", "in", NET_MODES)],
                         "TANGEDCO 2021: all categories except hut and agriculture, net billing / net feed-in, up to "
                         "the sanctioned load and 999 kW", "high"),
    "TN-C5-002#cl-I.3a": ([st("TN"), leaf("metering_mode", "eq", "gross")],
                          "TANGEDCO 2021: gross metering mechanism, 151 kWp up to 999 kW", "high"),
    "TN-C5-002#cl-VII.3": ([st("TN"), leaf("metering_mode", "in", NET_MODES)],
                           "TANGEDCO 2021: 90% DT limit for net metering / net billing systems", "high"),
    "TN-C5-002#cl-VII.4": ([st("TN"), leaf("metering_mode", "eq", "gross")],
                           "TANGEDCO 2021: 70% power-transformer limit for HT gross metering", "high"),
    # Delhi (DERC)
    "DL-C3-016#cl-g3-stage1-deemed": ([st("DL"), kw("lte", 10)],
                                      "DERC 2026: no feasibility analysis up to 10 kW on the same supply type (supply "
                                      "type is not a case fact)", "medium"),
    "DL-C3-016#cl-g3-stage1-lapse": ([st("DL")], "DERC 2026: feasibility deemed granted when the outcome is not "
                                     "communicated in time", "high"),
    "DL-C3-009#cl-3.8": ([st("DL")], "DERC GNM/VNM Fifth Amendment 2024: ground-mounted systems up to 5x sanctioned "
                         "load, 10 MW (mounting type is not a case fact)", "medium"),
    "DL-C3-001#cl-5.4": ([st("DL")], "DERC net metering: SLD differential charges when capacity exceeds the "
                         "sanctioned load", "high"),
    # Uttar Pradesh (UPERC)
    "UP-C3-002#cl-6.2": ([st("UP")], "UPERC 2019: capacity on a DT up to 75% of the DT", "high"),
    "UP-C3-002#cl-5.1": ([st("UP")], "UPERC 2019: capacity up to 100% of connected / contracted demand", "high"),
    "UP-C3-002#cl-6.2-proviso2": ([st("UP")], "UPERC 2019: augmentation charge Rs 1000/kWp beyond 10 kWp", "high"),
    # Central
    "IN-C3-001#cl-11.7A": ([kw("lte", 10)], "Electricity (Rights of Consumers) Amendment 2024 rule 11(7A): up to "
                           "10 kW deemed accepted", "high"),
    "IN-C3-004#cl-11.4": ([leaf("state", "in", [])], "ROC 2021 rule 11(4) proviso: only where state regulations do "
                          "not provide for net metering; every state in the corpus has such regulations", "medium"),
    "IN-C2-013#cl-1b": ([leaf("metering_mode", "in", ALL_GRID_MODES)],
                        "ALMM List-II order 2026: net-metering and open-access projects commissioned by 31.12.2026 "
                        "exempt", "high"),
    "IN-C2-013#cl-1b-giu": ([leaf("consumer_category", "eq", "residential")],
                            "ALMM List-II order 2026: PM Surya Ghar 'Give It Up' residential cases exempt to 31.03.2027 "
                            "(the scheme option is not a case fact)", "medium"),
    "IN-C2-013#cl-1e": ([leaf("metering_mode", "eq", None)],
                        "ALMM order 2026: List-I/II do not apply to behind-the-meter captive plants (no grid metering "
                        "mode)", "low"),
    "IN-C1-001#cl-annex1-ii-amended": ([leaf("subsidy_claimed", "eq", True), leaf("consumer_category", "eq", "residential")],
                                       "PM Surya Ghar amended OM 07.07.2025: Phase-II CFA claim window", "high"),
    "IN-C1-001#cl-phase2-pmsg-split": ([leaf("subsidy_claimed", "eq", True),
                                        leaf("consumer_category", "eq", "residential")],
                                       "PM Surya Ghar: applications on or after 13.02.2024 fall under PMSG", "high"),
}


def build() -> list[dict[str, Any]]:
    r2 = json.loads((CORPUS_DIR / "graph" / "applicability.json").read_text(encoding="utf-8"))
    r2_ids = {p["node_id"] for p in r2}
    assert not r2_ids & set(R3_PREDICATES), "an r2 predicate is redefined"
    new = [{"node_id": n, "applies_when": {"all": conds}, "applicability_basis": basis, "basis_span": None,
            "confidence": conf} for n, (conds, basis, conf) in R3_PREDICATES.items()]
    out = r2 + new
    for p in out:
        ApplicabilityPredicate.model_validate(p)
    return out


def main() -> None:
    preds = build()
    (CORPUS_R3_DIR / "graph" / "applicability.json").write_text(json.dumps(preds, indent=2) + "\n", encoding="utf-8",
                                                                newline="\n")
    print(f"{len(preds)} predicates ({len(R3_PREDICATES)} new)")


if __name__ == "__main__":
    main()
