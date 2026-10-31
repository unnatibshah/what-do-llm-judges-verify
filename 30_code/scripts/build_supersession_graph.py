"""Build 40_data/corpus/graph/supersession.json and applicability.json from authentic clause text.

Each node's `clause_text_snippet` is cut from `40_data/corpus/text/<doc_id>.txt` between a verbatim
start anchor and end anchor (whitespace collapsed), so every snippet is guaranteed to exist
in the corpus. Every explicit edge's evidence quote is likewise verified to occur in the
superseding document's text. The script fails loudly if any anchor or quote is missing.
"""

import json
import re

from suryabench.graph.oracle import validate_graph
from suryabench.graph.schema import SupersessionGraph
from suryabench.paths import CORPUS_DIR

TEXT = CORPUS_DIR / "text"
OUT = CORPUS_DIR / "graph"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def span(doc_id: str, start: str, end: str) -> str:
    """Verbatim text from `start` through `end` (both whitespace-insensitive)."""
    text = _norm((TEXT / f"{doc_id}.txt").read_text(encoding="utf-8"))
    i = text.find(_norm(start))
    assert i >= 0, f"{doc_id}: start anchor not found: {start!r}"
    j = text.find(_norm(end), i)
    assert j >= 0, f"{doc_id}: end anchor not found after start: {end!r}"
    return text[i : j + len(_norm(end))]


def quote(doc_id: str, q: str) -> str:
    text = _norm((TEXT / f"{doc_id}.txt").read_text(encoding="utf-8"))
    assert _norm(q) in text, f"{doc_id}: evidence quote not found: {q!r}"
    return _norm(q)


def J(level: str, code: str, discom: str | None = None) -> dict:
    return {"level": level, "code": code, "discom": discom}


IN, MH, RJ = J("central", "IN"), J("state", "MH"), J("state", "RJ")
MSEDCL = J("state", "MH", "MSEDCL")

# (node_id, doc_id, clause_ref, subject, jurisdiction, effective_date, status, rank, start, end)
NODES = [
    # --- central ------------------------------------------------------------------------
    ("IN-C1-001#cl-4.1", "IN-C1-001", "e) table rows 1-3", "subsidy_cfa_residential", IN, "2024-02-13",
     "in_force", "A3", "| 1. | Residential Sector (first 2 kW of RTS capacity p", "beyond 3 kW ) p | No additional CFA"),
    ("IN-C1-001#cl-4.gh", "IN-C1-001", "e) table row 4", "subsidy_cfa_group_housing", IN, "2024-02-13",
     "in_force", "A3", "| 4. | Group Housing Societies/ Residential Welfare Associations (GHS/RWA) etc, for common "
     "facilities including EV charging up to 500 kW p", "| Rs 18,000/kWp"),
    ("IN-C1-001#cl-5.1m", "IN-C1-001", "m)", "dcr_compliance", IN, "2024-02-13", "in_force", "A3",
     "m) Domestic Content Requirement:", "shall render the installation ineligible for CFA."),
    ("IN-C1-002#cl-2", "IN-C1-002", "2", "subsidy_cfa_residential", IN, "2019-09-03", "superseded", "A3",
     "Accordingly, it is clarified that subsidy for individual residential household", "20% for balance"),
    ("IN-C2-002#cl-1", "IN-C2-002", "1", "almm_module_compliance", IN, "2024-04-01", "in_force", "A3",
     "Vide MNRE", "1st April, 2024"),
    ("IN-C2-003#cl-1", "IN-C2-003", "1", "almm_module_compliance", IN, "2024-02-15", "superseded", "A3",
     "The undersigned is directed to convey that the O.M. of even no. dated 9th February, 2024",
     "is hereby held in abeyance till further orders."),
    ("IN-C3-001#cl-11.7", "IN-C3-001", "rule 11(7)", "feasibility_sanction_stage", IN, "2024-02-22", "in_force",
     "A2", "(7) For installation of roof top solar photo voltaic systems, the technical feasibility study",
     "technically feasible."),
    ("IN-C3-002#cl-11.7", "IN-C3-002", "rule 11(7)", "feasibility_sanction_stage", IN, "2020-12-31", "superseded",
     "A2", "(7) The technical feasibility study shall be completed within the time period specified by the",
     "intimated to the applicant."),
    ("IN-C3-002#cl-11.4", "IN-C3-002", "rule 11(4)", "net_metering_capacity_cap", IN, "2020-12-31", "in_force",
     "A2", "(4) The regulations on Grid Interactive Roof top Solar PV system", "loads above ten kW."),
    # --- Maharashtra -------------------------------------------------------------------
    ("MH-C3-001#cl-2.1j", "MH-C3-001", "2.1(j)", "net_metering_capacity_cap", MH, "2019-12-30", "in_force", "A1",
     "(j) “Eligible Consumer” means", "the capacity limit of 1 MW shall not apply;"),
    ("MH-C3-001#cl-5.2", "MH-C3-001", "5.2", "dt_capacity_limit", MH, "2019-12-30", "in_force", "A1",
     "The cumulative capacity of all Renewable Energy Generating Systems", "70% of its rated capacity:"),
    ("MH-C3-001#cl-6.2", "MH-C3-001", "6.2", "net_metering_capacity_cap", MH, "2019-12-30", "in_force", "A1",
     "6.2 The capacity of the Renewable Energy Generating System to be connected", "as applicable."),
    ("MH-C3-001#cl-annex1-c", "MH-C3-001", "Annexure-1 c", "feasibility_sanction_stage", MH, "2019-12-30",
     "superseded", "A1", "c. The Distribution Licensee shall conduct a technical feasibility study within 15 working days",
     "from the registration of the Application"),
    ("MH-C3-002#cl-2", "MH-C3-002", "2 (4th-5th provisos to 2.1(j))", "net_metering_capacity_cap", MH, "2024-08-29",
     "in_force", "A1", "Provided also that Residential consumer in multi storied building", "Virtual Net-Metering Arrangement:"),
    ("MH-C3-002#cl-annex1-c", "MH-C3-002", "6 (Annexure-1 c)", "feasibility_sanction_stage", MH, "2024-08-29",
     "in_force", "A1", "c For installation of Renewable Energy Generating Systems, the technical feasibility",
     "presumed that the proposal is technically feasible:"),
    ("MH-C3-002#cl-annex1-c-proviso", "MH-C3-002", "6 (Annexure-1 c, proviso)", "feasibility_sanction_stage", MH,
     "2024-08-29", "in_force", "A1", "Provided that the applications for Renewable Energy Generating Systems upto 10 kW",
     "shall be carried out by the Distribution Licensee."),
    # MSEDCL circulars are DISCOM procedural documents: rank A6 (protocol hierarchy table). Until
    # 2026-09-30 these three nodes were ranked A4 and anchored on a title, a subject line and a
    # reference header; they are now anchored on each circular's operative text (00_tracking DECISIONS).
    ("MH-C5-001#cl-feasibility", "MH-C5-001", "9.3", "feasibility_sanction_stage", MSEDCL, "2020-01-20",
     "in_force", "A6", "9.3 MSEDCL shall register the Application on first come first served basis",
     "of any deficiency or incompleteness."),
    ("MH-C5-004#cl-open-access", "MH-C5-004", "12.7 (inserted into CC 258, clause 12)", "net_metering_capacity_cap",
     MSEDCL, "2018-08-10", "superseded", "A6", "12.7. Net metering & Open Access cannot be availed",
     "by the same consumer."),
    ("MH-C5-005#cl-phase2", "MH-C5-005", "3.1-5 (Illustration for CFA)", "subsidy_cfa_residential", MSEDCL,
     "2021-01-15", "in_force", "A6", "3.1-5 lllustration for CFA", "No subsidy beyond 10 KW capacity"),
    # --- Rajasthan ----------------------------------------------------------------------
    ("RJ-C3-001#cl-3.1", "RJ-C3-001", "3.1", "net_metering_capacity_cap", RJ, "2015-02-26", "superseded", "A1",
     "The maximum Rooftop PV Solar Power Plant capacity", "contract demand of the consumer."),
    ("RJ-C3-002#cl-6.1", "RJ-C3-002", "6.1", "dt_capacity_limit", RJ, "2021-06-15", "superseded", "A1",
     "6.1 The cumulative capacity of Renewable Energy generating system to be allowed at a",
     "stipulated by the Commission from time to time"),
    ("RJ-C3-002#cl-7.2", "RJ-C3-002", "7.2", "net_metering_capacity_cap", RJ, "2021-06-15", "in_force", "A1",
     "7.2 The maximum Renewable Energy generating system capacity to be installed at any",
     "Demand of the consumer:"),
    ("RJ-C3-002#cl-8.8", "RJ-C3-002", "8.8", "feasibility_sanction_stage", RJ, "2021-06-15", "superseded", "A1",
     "8.8 Within twenty (20) days from the issuance of acknowledgement", "generating system."),
    ("RJ-C3-003#cl-2", "RJ-C3-003", "2 (substituted 6.1)", "dt_capacity_limit", RJ, "2023-10-06", "in_force", "A1",
     '"6.1 The cumulative capacity of Renewable Energy generating system to be allowed at a particular',
     "stipulated by the Commission from time to time:"),
    ("RJ-C3-003#cl-2-proviso", "RJ-C3-003", "2 (substituted 6.1, second proviso)", "dt_capacity_limit", RJ,
     "2023-10-06", "in_force", "A1", "Provided further that, in case of HT consumers where the distribution transformer",
     "shall not be applicable."),
    ("RJ-C3-004#cl-12", "RJ-C3-004", "12", "net_metering_capacity_cap", RJ, "2024-02-07", "in_force", "A1",
     "orders that henceforth net metering arrangement shall be", "for all categories of the"),
    ("RJ-C3-005#cl-8.8", "RJ-C3-005", "3(1) (substituted 8.8)", "feasibility_sanction_stage", RJ, "2024-08-30",
     "in_force", "A1", "“For installation of Renewable Energy Generating systems, the technical feasibility",
     "proposal is technically feasible."),
    ("RJ-C3-005#cl-8.8-proviso", "RJ-C3-005", "3(1) (substituted 8.8, proviso)", "feasibility_sanction_stage", RJ,
     "2024-08-30", "in_force", "A1", "Provided that the applications for Renewable Energy Generating systems upto 10 kW",
     "Distribution Licensee.”"),
]

# (from, to, relation, from_date, evidence_type, confidence, quote_doc, quote)
EDGES = [
    ("IN-C1-002#cl-2", "IN-C1-001#cl-4.1", "superseded_by", "2024-02-13", "explicit", "high", "IN-C1-001",
     "subsumed into the new scheme, and the new scheme funds shall be utilized for meeting"),
    ("IN-C2-003#cl-1", "IN-C2-002#cl-1", "superseded_by", "2024-03-29", "implicit", "medium", "IN-C2-002",
     "1st April, 2024"),
    ("IN-C3-002#cl-11.7", "IN-C3-001#cl-11.7", "superseded_by", "2024-02-22", "explicit", "high", "IN-C3-001",
     "for sub-rule (7), the following sub-rule shall be substituted"),
    ("MH-C3-001#cl-annex1-c", "MH-C3-002#cl-annex1-c", "superseded_by", "2024-08-29", "explicit", "high", "MH-C3-002",
     "Substitution of Clause C of Annexure-1 of the Principal Regulations"),
    ("MH-C5-004#cl-open-access", "MH-C5-001#cl-feasibility", "superseded_by", "2020-01-20", "explicit", "high",
     "MH-C5-001", "Procedure for Application, methodology for Metering"),
    ("RJ-C3-001#cl-3.1", "RJ-C3-002#cl-7.2", "superseded_by", "2021-06-15", "explicit", "high", "RJ-C3-002",
     "shall be governed as per the"),
    ("RJ-C3-002#cl-6.1", "RJ-C3-003#cl-2", "superseded_by", "2023-10-06", "explicit", "high", "RJ-C3-003",
     "The existing sub-regulation 6.1 shall be substituted with the following"),
    ("RJ-C3-002#cl-8.8", "RJ-C3-005#cl-8.8", "superseded_by", "2024-08-30", "explicit", "high", "RJ-C3-005",
     "The existing sub regulation 8.8 shall be substituted with the following"),
]

# Instruments superseded in their entirety (every clause), with the backing edge's source clause.
SUPERSEDED_DOCUMENTS = {
    "RJ-C3-001": ("2021-06-15", "RJ-C3-001#cl-3.1"),  # 2015 net-metering regulations -> RERC DRE Regulations 2021
    "IN-C1-002": ("2024-02-13", "IN-C1-002#cl-2"),  # Phase-II subsidy clarification -> PM Surya Ghar
    "MH-C5-004": ("2020-01-20", "MH-C5-004#cl-open-access"),  # CC 310 (2015 regulations) -> CC 322
    "IN-C2-003": ("2024-03-29", "IN-C2-003#cl-1"),  # abeyance OM -> 29.03.2024 OM (implicit edge)
}

# Applicability predicates over the closed case-facts vocabulary (used by Arm 0).
PREDICATES = {
    "IN-C1-001#cl-4.1": ({"all": [{"field": "consumer_category", "op": "eq", "value": "residential"},
                                  {"field": "premises_type", "op": "eq", "value": "individual"},
                                  {"field": "subsidy_claimed", "op": "eq", "value": True}]},
                         "PM Surya Ghar residential slabs: individual residential consumers claiming CFA"),
    "IN-C1-001#cl-4.gh": ({"all": [{"field": "premises_type", "op": "in", "value": ["group_housing", "rwa_common"]},
                                   {"field": "subsidy_claimed", "op": "eq", "value": True}]},
                          "PM Surya Ghar GHS/RWA row: common facilities of housing societies"),
    "IN-C1-001#cl-5.1m": ({"all": [{"field": "subsidy_claimed", "op": "eq", "value": True}]},
                          "DCR is an essential condition for CFA eligibility"),
    "IN-C2-002#cl-1": ({"all": [{"field": "subsidy_claimed", "op": "eq", "value": True},
                                {"field": "case_date", "op": "gte", "value": "2024-04-01"}]},
                       "ALMM List-I in effect from 01.04.2024 for subsidised rooftop projects"),
    "MH-C3-001#cl-5.2": ({"all": [{"field": "state", "op": "eq", "value": "MH"}]},
                         "MERC DT hosting limit: all net-metering / net-billing systems in Maharashtra"),
    "MH-C3-001#cl-6.2": ({"all": [{"field": "state", "op": "eq", "value": "MH"},
                                  {"field": "proposed_capacity_kw", "op": "lt", "value": 1000}]},
                         "MERC individual capacity limit (Eligible Consumer systems below 1 MW)"),
    "MH-C3-001#cl-2.1j": ({"all": [{"field": "state", "op": "eq", "value": "MH"},
                                   {"field": "proposed_capacity_kw", "op": "gte", "value": 1000}]},
                          "MERC Eligible Consumer definition: net-metering systems must be below 1 MW"),
    "MH-C3-002#cl-annex1-c": ({"all": [{"field": "state", "op": "eq", "value": "MH"},
                                       {"field": "proposed_capacity_kw", "op": "gt", "value": 10}]},
                              "MERC 2024 feasibility study: 15 days, presumed feasible if not intimated"),
    "MH-C3-002#cl-annex1-c-proviso": ({"all": [{"field": "state", "op": "eq", "value": "MH"},
                                               {"field": "proposed_capacity_kw", "op": "lte", "value": 10}]},
                                      "MERC 2024 proviso: up to 10 kW deemed accepted"),
    "RJ-C3-002#cl-7.2": ({"all": [{"field": "state", "op": "eq", "value": "RJ"},
                                  {"field": "proposed_capacity_kw", "op": "lte", "value": 1000}]},
                         "RERC individual capacity limit: 100% of sanctioned load / contract demand"),
    "RJ-C3-004#cl-12": ({"all": [{"field": "state", "op": "eq", "value": "RJ"},
                                 {"field": "proposed_capacity_kw", "op": "gt", "value": 1000}]},
                        "RERC 07.02.2024 order: net metering up to 1 MW"),
    "RJ-C3-003#cl-2": ({"all": [{"field": "state", "op": "eq", "value": "RJ"},
                                {"field": "consumer_category", "op": "neq", "value": "industrial"}]},
                       "RERC DT hosting limit 80% (not HT consumers with their own transformer)"),
    "RJ-C3-003#cl-2-proviso": ({"all": [{"field": "state", "op": "eq", "value": "RJ"},
                                        {"field": "consumer_category", "op": "eq", "value": "industrial"}]},
                               "RERC proviso: 80% DT limit not applicable to HT consumers' own transformers"),
    "RJ-C3-005#cl-8.8": ({"all": [{"field": "state", "op": "eq", "value": "RJ"},
                                  {"field": "proposed_capacity_kw", "op": "gt", "value": 10}]},
                         "RERC 2024 feasibility study: 15 days, presumed feasible if not intimated"),
    "RJ-C3-005#cl-8.8-proviso": ({"all": [{"field": "state", "op": "eq", "value": "RJ"},
                                          {"field": "proposed_capacity_kw", "op": "lte", "value": 10}]},
                                 "RERC 2024 proviso: up to 10 kW deemed accepted"),
}


def main() -> None:
    nodes = {}
    for nid, doc, ref, subject, jur, eff, status, rank, start, end in NODES:
        nodes[nid] = {
            "node_id": nid, "doc_id": doc, "clause_ref": ref, "clause_text_snippet": span(doc, start, end),
            "subject": subject, "jurisdiction": jur, "effective_date": eff, "effective_date_basis": "E1",
            "effective_date_confidence": "high", "status_at_snapshot": status, "authority_rank": rank,
        }
    edges = [
        {"from": f, "to": t, "relation": rel, "from_date": d, "confidence": conf,
         "evidence": {"type": et, "quote_text": quote(qdoc, q), "doc_id": qdoc}}
        for f, t, rel, d, et, conf, qdoc, q in EDGES
    ]
    sources = {e["from"]: e["from_date"] for e in edges if e["relation"] == "superseded_by"}
    for doc, (date, clause) in SUPERSEDED_DOCUMENTS.items():
        assert sources.get(clause) == date, f"{doc}: no superseded_by edge from {clause} dated {date}"
    graph = {"nodes": nodes, "edges": edges,
             "superseded_documents": {d: date for d, (date, _) in SUPERSEDED_DOCUMENTS.items()}}
    validate_graph(SupersessionGraph.model_validate(graph))
    (OUT / "supersession.json").write_text(json.dumps(graph, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    preds = [
        {"node_id": nid, "applies_when": cond, "applicability_basis": basis, "basis_span": None, "confidence": "high"}
        for nid, (cond, basis) in PREDICATES.items()
    ]
    (OUT / "applicability.json").write_text(json.dumps(preds, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"graph: {len(nodes)} nodes, {len(edges)} edges; {len(preds)} predicates")


if __name__ == "__main__":
    main()
