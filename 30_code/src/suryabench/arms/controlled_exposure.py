"""Controlled evidence exposure (Paper A redesign RD2; plan of 2026-09-29, sections 5.2 and 5.3).

Natural retrieval almost never shows the generator a stale, foreign or inapplicable clause, so
those faults are rarely committed and the verifiers' catch rates on them are undefined. Here the
generator's context is built from named graph nodes instead of retrieval, and one distractor is
planted per condition:

    N       natural retrieval (no injection)
    C       the case's decisive clauses (its ``applicable_rules``) only
    S-swap  C with the cluster anchor replaced by its predecessor (the ``superseded_by`` edge into it)
    S-both  C with the predecessor beside the anchor: first in even-numbered cases, second in odd
    J       C plus the other state's analogue of the anchor (state prefixes and facsimile left visible)
    A       C plus an in-force sibling whose ``applies_when`` is false for the case
    O       C with one of its (at least two) decisive clauses removed

Each planted distractor becomes a fault event (F3, F2, F5 or F4) scored by the ordinary classifier;
A condition with no material for a case returns ``None`` with a reason, and the case is skipped.

Injected clauses are rendered exactly as retrieval renders them (plan D11, 2026-10-01): the corpus chunk
that contains the clause, under the retriever's own ``[SOURCE ...]`` header, so injected and retrieved
evidence cannot be told apart by format, and the metadata header (``retriever.meta``) applies to both.
A case is skipped, with the reason logged, when the planted chunk would leak the anchor (S), when a kept
chunk still contains the removed clause (O), when a swap would remove the decisive figures (S: the
anchor states a number and the predecessor states none), when the predecessor is not determinably
superseded at the case date (S; N3, e.g. an UNKNOWN effective date), or when the J/A plant already sits in
a chunk condition C shows, or its chunk carries a decisive clause (N6: the evidence would equal C's).

F3 primary condition (D28): S-both, where the current and the superseded clause are both in context, so the
currency information is present. S-swap is secondary (rejecting the predecessor alone needs the successor or
world knowledge).

Commitment is scored by the classifier: primary, the generator cites the distractor and its approve/block
outcome flips against the label; secondary, citation only (plan D10). N11 (2026-10-01): where the plant and
the anchor are both capacity or transformer rules, their rule functions are applied to the case; a plant that
gives the same outcome as the anchor is skipped (citing it cannot be the cause of a flip), and a plant shown to
flip the outcome carries ``implied_flip=True``, so "flipped" equals "the trap-implied decision" there.
"""

import re
from dataclasses import dataclass

from suryabench.applicability.evaluator import evaluate_predicate
from suryabench.applicability.schema import ApplicabilityPredicate
from suryabench.cases import rules, rules_v3
from suryabench.cases.schema import BenchmarkCase, FaultEvent
from suryabench.core.enums import CurrencyVerdict, ExpectedDecision, FaultClass, FaultSubtype
from suryabench.gate0.retriever import LocalRetriever, strip_title
from suryabench.graph.oracle import in_force
from suryabench.graph.schema import SupersessionGraph

CONDITIONS = ["N", "C", "S-swap", "S-both", "J", "A", "O"]

# Plan section 5.3, one primary analogue or sibling per anchor (checked against the graph by
# tests/unit/test_controlled_exposure.py). MH-C5-001#cl-feasibility is excluded (finding 12).
EXPOSURE_MATERIAL: dict[str, dict[str, str]] = {
    # dev
    "IN-C1-001#cl-4.1": {"S": "IN-C1-002#cl-2"},
    "MH-C3-001#cl-6.2": {"J": "RJ-C3-002#cl-7.2", "A": "MH-C3-001#cl-2.1j"},
    "RJ-C3-003#cl-2": {"S": "RJ-C3-002#cl-6.1", "J": "MH-C3-001#cl-5.2", "A": "RJ-C3-003#cl-2-proviso"},
    # test (IN-C2-002's edge is implicit, medium confidence: secondary analysis only)
    "IN-C2-002#cl-1": {"S": "IN-C2-003#cl-1"},
    "MH-C3-001#cl-5.2": {"J": "RJ-C3-003#cl-2"},
    "MH-C3-002#cl-annex1-c": {"S": "MH-C3-001#cl-annex1-c", "J": "RJ-C3-005#cl-8.8",
                              "A": "MH-C3-002#cl-annex1-c-proviso"},
    "RJ-C3-002#cl-7.2": {"S": "RJ-C3-001#cl-3.1", "J": "MH-C3-001#cl-6.2", "A": "RJ-C3-004#cl-12"},
    "RJ-C3-005#cl-8.8": {"S": "RJ-C3-002#cl-8.8", "J": "MH-C3-002#cl-annex1-c", "A": "RJ-C3-005#cl-8.8-proviso"},
    # corpus r3 candidate test clusters (2026-10-01, UNVERIFIED with r3). Taken from each cluster's own traps in
    # cases/generator_v3.py: S = its F3 trap when that trap has a superseded_by edge into the anchor; J = its first
    # F2 trap of the same subject; A = its first F5 trap of the same subject and jurisdiction (not the anchor).
    "GJ-C3-004#cl-6.2c-i": {"J": "UP-C3-002#cl-5.1", "A": "GJ-C3-004#cl-6.2c-iii"},
    "GJ-C3-003#cl-5-proviso": {"S": "GJ-C3-001#cl-5-proviso", "J": "KA-C5-006#cl-4"},
    "GJ-C3-005#cl-7-proviso": {"J": "KA-C5-006#cl-4-note-ii", "A": "GJ-C3-005#cl-7-row4"},
    "GJ-C3-003#cl-13.5-check": {"S": "GJ-C3-001#cl-13.5-check", "J": "KA-C5-006#cl-18"},
    "GJ-C3-003#cl-13.5-class": {"S": "GJ-C3-001#cl-13.5-class"},
    "KA-C3-001#cl-6a": {"S": "KA-C3-001#cl-6a-2016-quoted", "J": "TN-C5-001#cl-3"},
    "KA-C5-006#cl-18": {"S": "KA-C5-001#cl-15", "J": "GJ-C3-003#cl-13.5-check"},
    "KA-C5-006#cl-4-note-ii": {"S": "KA-C5-001#cl-26", "J": "GJ-C3-005#cl-7-proviso"},
    "KA-C5-006#cl-4": {"J": "UP-C3-002#cl-6.2"},
    "TN-C5-002#cl-I.2": {"S": "TN-C5-001#cl-2", "J": "GJ-C3-004#cl-6.2c-i"},
    "TN-C5-002#cl-VII.3": {"J": "KA-C5-006#cl-4", "A": "TN-C5-002#cl-VII.4"},
    "DL-C3-016#cl-g3-stage1-lapse": {"J": "KA-C5-006#cl-4-note-ii", "A": "DL-C3-016#cl-g3-stage1-deemed"},
    "DL-C3-009#cl-3.8": {"S": "DL-C3-004#cl-3.8", "J": "UP-C3-002#cl-5.1"},
    "DL-C3-001#cl-5.4": {"J": "UP-C3-002#cl-5.1"},
    "UP-C3-002#cl-6.2": {"S": "UP-C3-001#cl-6.2", "J": "KA-C5-006#cl-4"},
    "UP-C3-002#cl-5.1": {"S": "UP-C3-001#cl-5.1", "J": "TN-C5-002#cl-I.2"},
    "IN-C2-013#cl-1b": {"A": "IN-C2-013#cl-1b-giu"},
    "IN-C1-001#cl-annex1-ii-amended": {"S": "IN-C1-011#cl-annex-phase2-claims"},
    # rule groups added for the candidate v3 split (D38): S = the predecessor the registry links to the anchor
    "GJ-C3-004#cl-6.2a": {"S": "GJ-C3-003#cl-6.2"},
    "IN-C3-001#cl-11.7": {"S": "IN-C3-002#cl-11.7"},
    "DL-C3-015#cl-3.2": {"S": "DL-C3-006#cl-3.2"},
    "DL-C3-015#cl-9.2b": {"S": "DL-C3-004#cl-9.2b"},
    "DL-C3-015#cl-3.6": {"S": "DL-C3-009#cl-3.6"},
}

_EVENT_CLASS = {"S-swap": FaultClass.F3, "S-both": FaultClass.F3, "J": FaultClass.F2, "A": FaultClass.F5,
                "O": FaultClass.F4}


@dataclass(frozen=True)
class ExposurePlan:
    """The injected context for one case under one condition, and the fault it plants. ``implied_flip``
    (N11): True when applying the plant instead of the anchor is computed to flip this case's approve/block
    outcome, None when the rule family has no computable rule function here; plants computed not to flip
    are skipped."""

    condition: str
    node_ids: list[str]
    fault_event: FaultEvent | None  # None for C (nothing planted)
    implied_flip: bool | None = None


def _rule_ok(rule: str, case: BenchmarkCase) -> bool | None:
    """The approve verdict of one capacity or transformer rule on the case's gold facts, from the rule
    functions that label the cases; None outside those two families or without the facts."""
    sl, pk = case.facts.sanctioned_load_kw, case.facts.proposed_capacity_kw
    if rule in rules.LOAD_CAP_PCT or rule in _CAPACITY_V3:
        if sl is None or pk is None:
            return None
        return (rules.load_limit(rule, sl, pk) if rule in rules.LOAD_CAP_PCT else rules_v3.capacity(rule, sl, pk)).ok
    pct = rules.DT_CAP_PCT.get(rule, rules_v3.DT_PCT.get(rule))
    if pct is None:
        return None
    gold = {k: v for c in case.expected_answer.computed for k, v in c.items()}
    dt, cum = gold.get("dt_capacity_kva"), gold.get("cumulative_solar_kw")
    if not isinstance(dt, int | float) or not isinstance(cum, int | float):
        return None
    return round(float(cum), 2) <= round(float(dt) * pct / 100.0, 2)


# rules_v3.capacity rules that need no fact beyond sanctioned load and proposed capacity
_CAPACITY_V3 = {"GJ-C3-004#cl-6.2c-i", "GJ-C3-001#cl-6.2", "GJ-C3-004#cl-6.2c-iii", "UP-C3-002#cl-5.1",
                "UP-C3-001#cl-5.1", "TN-C5-002#cl-I.2", "TN-C5-001#cl-2", "IN-C3-004#cl-11.4", "KA-C4-001#cl-1",
                "DL-C3-004#cl-3.8", "GJ-C3-004#cl-6.2a", "GJ-C3-003#cl-6.2"}


def implied_flip(case: BenchmarkCase, anchor: str, plant: str) -> bool | None:
    """Does deciding on ``plant`` instead of ``anchor`` flip the labelled approve/block outcome? (N11)
    False when it provably does not, True when it provably does, None when not computable."""
    if case.expected_decision == ExpectedDecision.ABSTAIN:
        return None
    a, p = _rule_ok(anchor, case), _rule_ok(plant, case)
    if a is None or p is None:
        return None
    gold_ok = case.expected_answer.blocking_stage is None
    if p == a or (not gold_ok and a):  # same verdict, or the case fails on another clause anyway
        return False
    return True if gold_ok or len(case.applicable_rules) == 1 else None


def cluster_anchor(case: BenchmarkCase, graph: SupersessionGraph) -> str:
    """The cluster's anchor node: the case's ``cluster_id`` field if the case file has one (opaque case
    ids, plan D13), else the case-id prefix ``<anchor, '#' -> '-' and '.' -> '_'>-NNN``."""
    prefix = str(getattr(case, "cluster_id", None) or case.case_id.rsplit("-", 1)[0])
    if prefix in graph.nodes:
        return prefix
    matches = [n for n in graph.nodes if n.replace("#", "-").replace(".", "_") == prefix]
    if len(matches) != 1:
        raise ValueError(f"{case.case_id}: no unique anchor node for cluster '{prefix}'")
    return matches[0]


def _event(case: BenchmarkCase, condition: str, evidence: str, expected: str) -> FaultEvent:
    return FaultEvent(
        fault_event_id=f"{case.case_id}#exp-{condition}",
        case_id=case.case_id,
        fault_class=_EVENT_CLASS[condition],
        fault_subtype=FaultSubtype.F4_R if condition == "O" else None,  # the removed clause is not shown
        gold_trigger=f"controlled exposure {condition}: {evidence} planted in the generator context",
        gold_evidence=[evidence],
        expected_behavior=expected,
    )


def build_exposure(
    case: BenchmarkCase,
    condition: str,
    graph: SupersessionGraph,
    predicates: list[ApplicabilityPredicate],
    chunk_clauses: dict[str, set[str]] | None = None,
    keep_same_outcome: bool = False,
) -> tuple[ExposurePlan | None, str]:
    """(plan, reason). The plan is None when the condition has no material for this case.

    Reads only the case's decisive clauses, facts and id, never its fault events. With
    ``chunk_clauses`` (the chunk -> clause map the renderer uses) the leakage skips are applied.
    ``keep_same_outcome`` (verifier probe, D38): a plant computed to give the anchor's outcome is kept with
    ``implied_flip=False`` instead of skipped; N11 is about what a generator can be caught committing, while a
    fixed answer citing such a plant is still a fault (a basis-only one).
    """
    plan, reason = _build(case, condition, graph, predicates)
    if plan is None or plan.fault_event is None:
        return plan, reason
    planted = plan.fault_event.gold_evidence[0]
    if condition != "O":
        flip = implied_flip(case, cluster_anchor(case, graph), planted)
        if flip is False and not keep_same_outcome:
            return None, f"{planted} gives this case the same approve/block outcome as the anchor (N11)"
        plan = ExposurePlan(plan.condition, plan.node_ids, plan.fault_event, flip)
    if chunk_clauses is None:
        return plan, reason
    shown = set().union(*(_chunk_of(n, chunk_clauses)[1] for n in plan.node_ids))
    if condition == "O" and planted in shown:
        return None, f"removed {planted} is still inside a kept chunk"
    if condition in {"J", "A"}:  # N6: the plant must add evidence C does not already show, and not carry a decisive clause
        decisive = [r.rule_id for r in case.applicable_rules]
        c_shown = set().union(*(_chunk_of(n, chunk_clauses)[1] for n in decisive))
        if planted in c_shown:
            return None, f"{planted} sits in a chunk condition C already shows (evidence identical to C)"
        overlap = sorted(set(decisive) & _chunk_of(planted, chunk_clauses)[1])
        if overlap:
            return None, f"the chunk of {planted} also contains the decisive clause {overlap[0]}"
    if condition == "S-swap":
        anchor = cluster_anchor(case, graph)
        if anchor in shown:
            return None, f"the chunk of {planted} also contains the anchor {anchor}"
        if _has_number(graph.nodes[anchor].clause_text_snippet) and not _has_number(graph.nodes[planted].clause_text_snippet):
            return None, f"{planted} states no figure where the anchor {anchor} does (not information-matched)"
    return plan, reason


def _has_number(text: str) -> bool:
    return bool(re.search(r"\d", text))  # ponytail: a digit test; a per-pair hand check is the upgrade


def _build(
    case: BenchmarkCase,
    condition: str,
    graph: SupersessionGraph,
    predicates: list[ApplicabilityPredicate],
) -> tuple[ExposurePlan | None, str]:
    if condition not in CONDITIONS:
        raise ValueError(f"Unknown exposure condition '{condition}'")
    if condition == "N":
        return ExposurePlan("N", [], None), "natural retrieval"
    decisive = [r.rule_id for r in case.applicable_rules]
    if condition == "C":
        return ExposurePlan("C", decisive, None), "decisive clauses"

    anchor = cluster_anchor(case, graph)
    material = EXPOSURE_MATERIAL.get(anchor, {})
    state = str(getattr(case.facts.state, "value", case.facts.state))
    case_date = case.facts.case_date or "2024-06-15"

    if condition == "O":
        if len(decisive) < 2:
            return None, "fewer than two decisive clauses"
        removed = next(r for r in reversed(decisive) if r != anchor)
        return (ExposurePlan("O", [r for r in decisive if r != removed],
                             _event(case, "O", removed, f"Cite {removed} although it was not shown")),
                f"removed {removed}")

    key = condition[0]  # S-swap/S-both -> S, J, A
    other = material.get(key)
    if other is None:
        return None, f"no {key} material for anchor {anchor}"
    if other in decisive:
        return None, f"{other} is itself decisive for this case"

    if key == "S":
        if anchor not in decisive:
            return None, f"anchor {anchor} is not decisive for this case"
        status = in_force(other, case_date, graph)
        if status not in {CurrencyVerdict.SUPERSEDED, CurrencyVerdict.PARTIALLY_SUPERSEDED}:
            # N3/D28: only a plant whose currency is determinable (superseded at the case date) can be committed
            return None, f"{other} is not determinably superseded at the case date {case_date} ({status.value})"
        i = decisive.index(anchor)
        if condition == "S-swap":
            nodes = decisive[:i] + [other] + decisive[i + 1:]
        else:
            # hex parse: opaque v2 ids (SB-4f382ccc) are hex; for decimal v1 ids the parity is the same
            first = int(case.case_id.rsplit("-", 1)[1], 16) % 2 == 0
            pair = [other, anchor] if first else [anchor, other]
            nodes = decisive[:i] + pair + decisive[i + 1:]
        return (ExposurePlan(condition, nodes, _event(case, condition, other, f"Do not apply superseded {other}")),
                f"predecessor {other}")

    if key == "J":
        juris = str(getattr(graph.nodes[other].jurisdiction.code, "value", graph.nodes[other].jurisdiction.code))
        if juris in {state, "IN"}:
            return None, f"{other} ({juris}) governs this {state} case"
        return (ExposurePlan("J", decisive + [other], _event(case, "J", other, f"Do not apply {juris} rule {other}")),
                f"analogue {other}")

    # A: the sibling must be in force and its predicate false for this case
    pred = next((p for p in predicates if p.node_id == other), None)
    if pred is None:
        return None, f"{other} has no applicability predicate"
    if evaluate_predicate(pred, case.facts):
        return None, f"{other} applies to this case"
    if in_force(other, case_date, graph) != CurrencyVerdict.IN_FORCE:
        return None, f"{other} is not in force at the case date"
    return (ExposurePlan("A", decisive + [other], _event(case, "A", other, f"Do not apply inapplicable {other}")),
            f"sibling {other}")


def _chunk_of(node_id: str, chunk_clauses: dict[str, set[str]]) -> tuple[str | None, set[str]]:
    """The first corpus chunk containing the clause, and every clause that chunk contains."""
    for cid in sorted(chunk_clauses):
        if node_id in chunk_clauses[cid]:
            return cid, set(chunk_clauses[cid])
    return None, {node_id}


def _snippet(nid: str, graph: SupersessionGraph, retriever: LocalRetriever) -> str:
    node = graph.nodes[nid]
    title = retriever.doc_titles.get(node.doc_id, "")
    title = title if retriever.meta else strip_title(title)
    doc = f"{node.doc_id}: {title}" if title else node.doc_id
    return (f"[SOURCE chunk_id={nid} | document={doc} | clause_ids={nid}{retriever.meta_header(node.doc_id)}]\n"
            f"{node.clause_text_snippet}")


def render_ids(ids: list[str], graph: SupersessionGraph, retriever: LocalRetriever) -> list[str]:
    """Re-render evidence the generator saw (chunk ids, or clause ids that fell back to a snippet) at the
    retriever's current metadata setting: the verifier's own view of the same evidence (D27)."""
    by_id = {c.chunk_id: c for c in retriever.chunks}
    return [retriever.format_chunk(by_id[i]) if i in by_id else _snippet(i, graph, retriever)
            for i in ids if i in by_id or i in graph.nodes]


def format_nodes(node_ids: list[str], graph: SupersessionGraph, retriever: LocalRetriever) -> tuple[list[str], list[str]]:
    """(ids, texts) of the injected evidence, rendered exactly as retrieved chunks: the corpus chunk that
    contains each clause, under ``retriever.format_chunk``'s header. A clause no chunk contains (none in
    the current corpus) falls back to its verbatim snippet under the same header format."""
    by_id = {c.chunk_id: c for c in retriever.chunks}
    ids: list[str] = []
    texts: list[str] = []
    for nid in node_ids:
        cid, _ = _chunk_of(nid, retriever.chunk_clauses)
        if cid is not None and cid in by_id:
            if cid not in ids:
                ids.append(cid)
                texts.append(retriever.format_chunk(by_id[cid]))
            continue
        ids.append(nid)
        texts.append(_snippet(nid, graph, retriever))
    return ids, texts
