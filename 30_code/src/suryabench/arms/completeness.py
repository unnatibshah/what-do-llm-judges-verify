"""Affirmative completeness checklist over the rule space (F4 safeguard, protocol §13).

Verification checks the claims a generator produced; it cannot see what was left out. This mechanism
derives, from the application documents alone (the parsed facsimile, never gold facts), which
regulatory *subjects* the application's workflow stage must address, then looks up the in-force
clauses on each subject in the case's jurisdiction (state + central). Each uncovered subject is flagged:

- F4-R: no retrieved chunk contains any in-force clause on that subject
- F4-C: such a clause was retrieved but none on that subject was cited

Fixed 2026-10-01 (plan item 1.11): cited chunk ids are expanded to the clauses they contain (before, a
chunk-id citation never covered a subject, so every case was flagged), the subjects follow the stage
(a subsidy claim is not asked for transformer limits), and facts come from the facsimile.
"""

from dataclasses import dataclass, field

from suryabench.arms.tools.case_reader import ParsedCaseFacts
from suryabench.core.enums import CurrencyVerdict
from suryabench.graph.oracle import in_force
from suryabench.graph.schema import SupersessionGraph


def required_subjects(parsed: ParsedCaseFacts) -> list[str]:
    """Subjects an application at its workflow stage must address, from the application documents. Corpus-r3
    stages and subjects added 2026-10-01 (N18): meter installation (check meter, meter class), metering
    arrangement, registration (capacity, augmentation), CFA claim windows, and voltage level at feasibility."""
    stage = (parsed.application_stage or "").lower()
    if "subsidy" in stage:
        subjects = ["subsidy_cfa_group_housing" if (parsed.households or 0) > 1 else "subsidy_cfa_residential",
                    "almm_module_compliance", "subsidy_disbursement_process"]
        return subjects + (["dcr_compliance"] if parsed.dcr_compliant is not None else [])
    if "equipment" in stage:
        return ["almm_module_compliance", "dcr_compliance"]
    if "meter installation" in stage:
        return ["meter_phase_threshold"]
    if "metering arrangement" in stage:
        return ["net_metering_capacity_cap"]
    if "registration" in stage:
        return ["net_metering_capacity_cap", "dt_capacity_limit"]
    subjects = ["feasibility_sanction_stage", "dt_capacity_limit", "meter_phase_threshold"]
    if parsed.metering_mode in {"net", "net_billing"}:
        subjects.append("net_metering_capacity_cap")
    return subjects


@dataclass
class CompletenessCheckResult:
    """Output of the affirmative completeness checklist for one case."""

    case_id: str
    is_complete: bool
    checklist: list[str]
    flags: list[str] = field(default_factory=list)  # "F4-R:<subject>:<node>|<node>"
    f4_r_subjects: list[str] = field(default_factory=list)
    f4_c_subjects: list[str] = field(default_factory=list)


def check_rule_completeness(
    case_id: str,
    parsed: ParsedCaseFacts,
    graph: SupersessionGraph,
    retrieved_chunk_ids: list[str],
    cited_rules: list[str],
    chunk_clauses: dict[str, set[str]],
) -> CompletenessCheckResult:
    """Flag every required subject the generator neither cited nor (for F4-R) retrieved."""
    state = parsed.state or "IN"
    case_date = parsed.case_date
    retrieved_nodes = set(retrieved_chunk_ids).union(*(chunk_clauses.get(cid, set()) for cid in retrieved_chunk_ids))
    cited = set(cited_rules).union(*(chunk_clauses.get(c, set()) for c in cited_rules))

    checklist = required_subjects(parsed)
    flags: list[str] = []
    f4_r: list[str] = []
    f4_c: list[str] = []
    for subject in checklist:
        candidates = sorted(
            nid
            for nid, node in graph.nodes.items()
            if str(node.subject) == subject
            and str(getattr(node.jurisdiction.code, "value", node.jurisdiction.code)) in {state, "IN"}
            and (case_date is None or in_force(nid, case_date, graph) == CurrencyVerdict.IN_FORCE)
        )
        if not candidates or cited & set(candidates):
            continue  # nothing in the registry to demand, or the subject is covered
        kind = "F4-C" if retrieved_nodes & set(candidates) else "F4-R"
        (f4_c if kind == "F4-C" else f4_r).append(subject)
        flags.append(f"{kind}:{subject}:{'|'.join(candidates)}")

    return CompletenessCheckResult(
        case_id=case_id,
        is_complete=not flags,
        checklist=checklist,
        flags=flags,
        f4_r_subjects=f4_r,
        f4_c_subjects=f4_c,
    )
