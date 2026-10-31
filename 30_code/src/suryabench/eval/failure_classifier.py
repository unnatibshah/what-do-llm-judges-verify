"""Deterministic failure classifier for SuryaBench (F1–F9).

Implements rule-based, deterministic classification of agent/verifier errors
without LLM-as-a-judge per SURYA-BENCH-PROTOCOL §13 and §16.
Enforces the locked epistemological precedence hierarchy defined in 20_method/CLASS-PRECEDENCE.md.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from suryabench.cases.schema import BenchmarkCase, FaultEvent, NonFaultOpportunity
from suryabench.core.enums import (
    CurrencyVerdict,
    ExpectedDecision,
    FaultClass,
    FaultSubtype,
    StateCode,
)
from suryabench.corpus.schema import CorpusManifest
from suryabench.graph.oracle import in_force
from suryabench.graph.schema import SupersessionGraph

# Locked epistemological precedence order per 20_method/CLASS-PRECEDENCE.md
# Upstream failures invalidate the preconditions for evaluating downstream failures.
FAULT_PRECEDENCE: list[FaultClass] = [
    FaultClass.F1,  # 1. Fabrication: clause does not exist
    FaultClass.F2,  # 2. Jurisdiction: alien state rule
    FaultClass.F3,  # 3. Currency: superseded/repealed clause
    FaultClass.F8,  # 4a. Procedural: failed to abstain on genuine statutory conflict
    FaultClass.F9,  # 4b. Procedural: failed to abstain on missing mandatory telemetry
    FaultClass.F4,  # 5. Omission: applicable rule not retrieved (F4-R) or omitted (F4-C)
    FaultClass.F5,  # 6. Applicability: current in-jurisdiction rule applied to scenario it does not govern
    FaultClass.F6,  # 7. Input Binding: correct rule/tool, corrupted facsimile input values
    FaultClass.F7,  # 8. Computation: arithmetic or unit calculation failure
]


# Directly bound fields and the application field each is legally required to come from.
# F6 fires when recorded provenance names a different source, even if the numbers coincide.
REQUIRED_SOURCE_FIELD: dict[str, str] = {
    "sanctioned_kw": "sanctioned_load_kw",
    "connected_kw": "connected_load_kw",
    "proposed_kw": "proposed_capacity_kw",
    "dt_capacity_kva": "dt_capacity_kva",
}


# A non-fault opportunity asserts a property holds; flagging the class that property belongs to
# is a false alarm on it (verifier flags are class ids, not property names).
NFO_PROPERTY_CLASS: dict[str, str] = {
    "existence": "F1", "jurisdiction": "F2", "currency": "F3", "completeness": "F4",
    "applicability": "F5", "input_binding": "F6", "arithmetic": "F7",
}


class DetectedFault(BaseModel):
    """A detected regulatory or execution fault."""

    model_config = ConfigDict(extra="forbid")

    fault_class: FaultClass
    fault_subtype: FaultSubtype | None = None
    trigger: str
    evidence: list[str] = Field(default_factory=list)
    description: str


class CaseClassificationResult(BaseModel):
    """Evaluation outcome for a single benchmark case."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    cluster_clause_id: str = Field(
        ..., description="Governing clause identifier used as clustering unit for bootstrap CIs"
    )
    decision: ExpectedDecision
    invalid_output: bool = False
    expected_decision: ExpectedDecision
    is_correct: bool
    outcome_correct: bool = Field(
        default=False,
        description="Decision outcome alone is right: abstain when required, else approve vs block as labelled "
        "(no fault conditions). Commitment (primary) is a cited trap with a flipped outcome",
    )
    unsupported_correct: bool
    detected_faults: list[DetectedFault] = Field(default_factory=list)
    primary_fault_class: FaultClass | None = Field(
        default=None, description="Primary failure class determined by locked precedence order"
    )
    fault_event_committed: dict[str, bool] = Field(
        default_factory=dict,
        description="Primary (plan D10): the generator committed the fault AND its approve/block outcome is "
        "flipped against the label (abstention classes: it answered)",
    )
    fault_event_committed_citation: dict[str, bool] = Field(
        default_factory=dict,
        description="Secondary: the generator committed the fault (cited the trap clause, omitted the rule, "
        "misbound the value), whatever its outcome",
    )
    fault_event_matches: dict[str, bool] = Field(
        default_factory=dict,
        description="Primary (D32): a verifier finding names the event's planted clause (resolved through chunk "
        "ids) AND gives the reason of the event's class (F2 wrong_jurisdiction, F3 not_in_force, F4 missing_rule, "
        "F5 not_applicable); classes without a reason code match as in fault_event_matches_clause. Keyed over "
        "citation-committed events",
    )
    fault_event_matches_clause: dict[str, bool] = Field(
        default_factory=dict,
        description="Secondary (the D26 primary): a finding names the planted clause, whatever reason or class it "
        "gives; for F6/F7/F8/F9, which have no clause, the class",
    )
    fault_event_matches_class: dict[str, bool] = Field(
        default_factory=dict,
        description="Secondary (D26): class agreement, a finding names the planted clause AND the planted class",
    )
    nfo_matches: dict[str, bool] = Field(
        default_factory=dict,
        description="Maps non-fault opportunity_id to whether it was flagged (False = True Negative)",
    )
    avoided_trap_matches: dict[str, bool] = Field(
        default_factory=dict,
        description="Maps avoided fault_event_id to whether verifier falsely flagged it (False = True Negative)",
    )
    evidence_overlap_jaccard: float | None = Field(
        default=None,
        description="Jaccard overlap between generator and verifier retrieved/cited evidence",
    )
    independence_config: str | None = Field(
        default=None,
        description="Independence configuration (000, 100, 110, 111) evaluated for this case",
    )
    verifier_flags: list[str] = Field(default_factory=list)
    completeness_flags: list[str] = Field(
        default_factory=list,
        description="Affirmative completeness checklist flags (always recorded; scored only when applied)",
    )
    completeness_applied: bool = False
    omission_catches: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description=(
            "Per ground-truth omission (applicable rule not cited): subtype and whether "
            "claim verification and/or the completeness checklist flagged it (H3)"
        ),
    )


# Classes whose events name no clause: a verifier finding matches them by class alone.
CLAUSELESS_CLASSES = {FaultClass.F6, FaultClass.F7, FaultClass.F8, FaultClass.F9}


# D32: the reason a finding must give to catch an event of each class (right clause AND right reason).
CLASS_REASON: dict[FaultClass, str] = {FaultClass.F2: "wrong_jurisdiction", FaultClass.F3: "not_in_force",
                                       FaultClass.F4: "missing_rule", FaultClass.F5: "not_applicable"}
# Reasons that assert a validity fault: on a clean condition-C case, an exploratory false alarm (D32).
VALIDITY_REASONS = {"not_in_force", "wrong_jurisdiction", "not_applicable"}


def _split_flag(flag: str) -> tuple[str, str, str]:
    """``F3:IN-C1-002#cl-2:not_in_force`` -> (``F3``, ``IN-C1-002#cl-2``, ``not_in_force``); a flag without a
    reason (runs before D32) or a bare class gives "" for the missing parts."""
    cls, _, rest = flag.partition(":")
    clause, _, reason = rest.partition(":")
    return cls.strip().upper(), clause.strip(), reason.strip()


def compute_evidence_overlap(
    gen_evidence: list[str] | None,
    ver_evidence: list[str] | None,
) -> float | None:
    """Compute Jaccard similarity index between generator and verifier evidence."""
    if gen_evidence is None or ver_evidence is None:
        return None
    set_g = set(gen_evidence)
    set_v = set(ver_evidence)
    union = set_g | set_v
    if not union:
        return None  # both empty (e.g. early abstention): overlap undefined, not 1.0
    return len(set_g & set_v) / len(union)


class FailureClassifier:
    """Deterministic failure evaluator across F1–F9 taxonomy."""

    def __init__(
        self,
        graph: SupersessionGraph,
        manifest: CorpusManifest | None = None,
        chunk_clauses: dict[str, set[str]] | None = None,
    ) -> None:
        self.graph = graph
        self.manifest = manifest
        # chunk_id -> clause node_ids contained in that chunk (retriever.map_chunks_to_clauses)
        self.chunk_clauses: dict[str, set[str]] = chunk_clauses or {}
        # Pre-extract all known valid doc IDs and clause node IDs
        self.known_nodes: set[str] = set(graph.nodes.keys())
        self.known_docs: set[str] = (
            {doc.doc_id for doc in manifest.documents} if manifest else set()
        )
        self.doc_jurisdiction: dict[str, str] = {
            d.doc_id: str(getattr(d.jurisdiction.code, "value", d.jurisdiction.code)) for d in manifest.documents
        } if manifest else {}

    def extract_cluster_clause(self, case: BenchmarkCase) -> str:
        """Cluster unit for bootstrap CIs: the case's ``cluster_id`` field when the case file has one
        (opaque case ids, plan D13), else the case-id prefix naming the generating clause.

        Case ids are `<cluster clause, #->- and .->_>-NNN`. The first applicable rule is not
        used: in F5 cases the decisive rule is the sibling clause, not the cluster's clause.
        """
        return str(getattr(case, "cluster_id", None) or case.case_id.rsplit("-", 1)[0])

    def jurisdiction(self, ref: str) -> str | None:
        """Jurisdiction code of a cited clause, chunk or document: the graph node's, else its document's."""
        node = self.graph.nodes.get(ref)
        if node is not None:
            return str(getattr(node.jurisdiction.code, "value", node.jurisdiction.code))
        code = self.doc_jurisdiction.get(ref.split("#")[0])
        return code

    def _names(self, ref: str) -> set[str]:
        """A cited or flagged id and every registry clause it names (a chunk id names its clauses)."""
        return {ref, *self.chunk_clauses.get(ref, set())}

    def classify_case(
        self,
        case: BenchmarkCase,
        agent_output: Any,
        verifier_flags: list[str] | None = None,
        retrieved_chunk_ids: list[str] | None = None,
        verifier_chunk_ids: list[str] | None = None,
        independence_config: str | None = None,
        completeness_flags: list[str] | None = None,
        completeness_applied: bool = False,
    ) -> CaseClassificationResult:
        """Classify agent output and verifier flags against benchmark case ground truth."""
        cluster_clause_id = self.extract_cluster_clause(case)

        # Normalize agent output fields
        decision = getattr(agent_output, "decision", None)
        raw_decision = str(decision or "").strip().upper()
        invalid = raw_decision == "INVALID"  # D24: an unusable reply is never correct, never a flip or a commit
        if isinstance(decision, str):
            dec_upper = decision.upper()
            if dec_upper in {"ABSTAIN", "ABSTAINED"}:
                decision = ExpectedDecision.ABSTAIN
            else:
                decision = ExpectedDecision.ANSWER
        elif decision is None:
            decision = ExpectedDecision.ANSWER

        cited_rules: list[str] = getattr(agent_output, "cited_rules", []) or []
        # A cited chunk id cites the registry clauses that chunk contains.
        cited_rules = list(dict.fromkeys(
            [r for c in cited_rules for r in [c, *sorted(self.chunk_clauses.get(c, set()))]]
        ))
        root_cause = getattr(agent_output, "root_cause", None)
        blocking_stage = getattr(agent_output, "blocking_stage", None)
        computed = getattr(agent_output, "computed", []) or []
        # Arm 1 records field-level provenance ({"field", "value", "inputs", ...});
        # Arms 2/2-O record a flat trace. Detectors below read the flat form.
        provenance = [c for c in computed if "field" in c]
        computed = [{c["field"]: c["value"]} if "field" in c else c for c in computed]
        case_date = case.facts.case_date or "2024-06-15"
        state_str = (
            case.facts.state.value
            if hasattr(case.facts.state, "value")
            else str(case.facts.state)
        )

        detected_faults: list[DetectedFault] = []

        # -------------------------------------------------------------
        # F1: Fabrication — cited clause does not exist in graph or corpus
        # -------------------------------------------------------------
        for rule in cited_rules:
            doc_id = rule.split("#")[0] if "#" in rule else rule
            if rule not in self.known_nodes and (self.known_docs and doc_id not in self.known_docs):
                detected_faults.append(
                    DetectedFault(
                        fault_class=FaultClass.F1,
                        trigger=f"fabricated_clause_citation:{rule}",
                        evidence=[rule],
                        description=f"Cited clause '{rule}' does not exist in the regulatory corpus or supersession graph.",
                    )
                )

        # -------------------------------------------------------------
        # F2: Jurisdiction error — real rule, wrong jurisdiction
        # -------------------------------------------------------------
        # Generic (D25, 2026-10-01): the jurisdiction of the cited graph node, else of its document in the
        # manifest; central (IN) rules govern every state. Before, only MH<->RJ was detected.
        for rule in cited_rules:
            juris = self.jurisdiction(rule)
            if juris is not None and juris not in {state_str, StateCode.IN.value}:
                detected_faults.append(
                    DetectedFault(
                        fault_class=FaultClass.F2,
                        trigger=f"alien_jurisdiction_citation:{rule}",
                        evidence=[rule],
                        description=f"Applied {juris} rule '{rule}' to a {state_str} case.",
                    )
                )

        # -------------------------------------------------------------
        # F3: Currency error — real rule, right jurisdiction, superseded
        # -------------------------------------------------------------
        for rule in cited_rules:
            if rule in self.known_nodes:
                verdict = in_force(rule, case_date, self.graph)
                if verdict in {CurrencyVerdict.SUPERSEDED, CurrencyVerdict.PARTIALLY_SUPERSEDED}:
                    detected_faults.append(
                        DetectedFault(
                            fault_class=FaultClass.F3,
                            trigger=f"superseded_clause_cited:{rule}",
                            evidence=[rule],
                            description=f"Cited clause '{rule}' is superseded as of case snapshot date {case_date}.",
                        )
                    )

        # Cited chunks of a wholly superseded instrument are currency errors too.
        for rule in cited_rules:
            doc_id = rule.split("#")[0]
            since = self.graph.superseded_documents.get(doc_id)
            if "#chk-" in rule and since and since <= case_date:
                detected_faults.append(
                    DetectedFault(
                        fault_class=FaultClass.F3,
                        trigger=f"superseded_instrument_cited:{rule}",
                        evidence=[rule],
                        description=f"Cited '{rule}' from {doc_id}, superseded in full from {since}.",
                    )
                )

        # -------------------------------------------------------------
        # F8: Conflict abstention — failed to abstain on genuine conflict
        # -------------------------------------------------------------
        if case.failure_class_probed == "F8" and decision != ExpectedDecision.ABSTAIN:
            detected_faults.append(
                DetectedFault(
                    fault_class=FaultClass.F8,
                    trigger="failure_to_abstain_on_conflict",
                    evidence=[r.rule_id for r in case.applicable_rules],
                    description="Agent answered when genuine statutory conflict required abstention.",
                )
            )

        # -------------------------------------------------------------
        # F9: Missing information abstention — failed to abstain on missing facts
        # -------------------------------------------------------------
        if (
            case.failure_class_probed == "F9"
            or case.expected_decision == ExpectedDecision.ABSTAIN
        ) and decision != ExpectedDecision.ABSTAIN:
            detected_faults.append(
                DetectedFault(
                    fault_class=FaultClass.F9,
                    trigger="failure_to_abstain_on_missing_facts",
                    evidence=["unrecorded_facsimile_telemetry"],
                    description="Agent answered when missing mandatory case facts required epistemic abstention.",
                )
            )

        # -------------------------------------------------------------
        # F4: Omission — an applicable rule was never retrieved or cited
        # F4-R: not retrieved in top-k
        # F4-C: retrieved and available, but omitted from cited_rules
        # -------------------------------------------------------------
        gold_applicable_ids = [r.rule_id for r in case.applicable_rules]
        retrieved_set = set(retrieved_chunk_ids or [])

        for gold_rule in gold_applicable_ids:
            if gold_rule not in cited_rules:
                # Strict: the exact clause id was supplied (oracle arm), or a retrieved
                # chunk contains that clause. Same-document chunks do not count.
                was_retrieved = gold_rule in retrieved_set or any(
                    gold_rule in self.chunk_clauses.get(cid, ()) for cid in retrieved_set
                )

                if retrieved_chunk_ids is not None and not was_retrieved:
                    detected_faults.append(
                        DetectedFault(
                            fault_class=FaultClass.F4,
                            fault_subtype=FaultSubtype.F4_R,
                            trigger=f"retrieval_omission:{gold_rule}",
                            evidence=[gold_rule],
                            description=f"Applicable rule '{gold_rule}' was not retrieved in top-k chunks.",
                        )
                    )
                else:
                    detected_faults.append(
                        DetectedFault(
                            fault_class=FaultClass.F4,
                            fault_subtype=FaultSubtype.F4_C,
                            trigger=f"citation_omission:{gold_rule}",
                            evidence=[gold_rule],
                            description=f"Applicable rule '{gold_rule}' was omitted from agent citations.",
                        )
                    )

        # -------------------------------------------------------------
        # F5: Applicability error — Reconciled to Protocol §13:
        # "Current, in-jurisdiction rule applied to a case it does not govern."
        # Evaluated when a cited rule is in-force and in-jurisdiction, but
        # its substantive predicate does not match the case facts.
        # -------------------------------------------------------------
        for rule in cited_rules:
            # Check if this rule is non-F1, non-F2, non-F3
            is_valid_evidence = (
                rule in self.known_nodes
                and not any(f.fault_class in {FaultClass.F1, FaultClass.F2, FaultClass.F3} and rule in f.evidence for f in detected_faults)
            )
            if is_valid_evidence and rule not in gold_applicable_ids:
                # Substantive predicate mismatch checks:
                is_applicability_error = False
                reason = ""

                # Only seeded traps count (N18, 2026-10-01): the corpus-r2 string heuristics ("IN-C1-001" for a
                # non-residential consumer, "cl-6.2" for gross metering) matched unrelated r3 clauses.
                # 3. Seeded F5 trap: the cited rule is the inapplicable clause the trap names
                #    (citing some other valid clause is not an applicability error)
                f5_traps = {ev for fe in case.fault_events if fe.fault_class == FaultClass.F5
                            for ev in fe.gold_evidence}
                if rule in f5_traps:
                    is_applicability_error = True
                    reason = f"Cited rule '{rule}' does not govern case conditions."

                if is_applicability_error:
                    detected_faults.append(
                        DetectedFault(
                            fault_class=FaultClass.F5,
                            trigger=f"inapplicable_rule_cited:{rule}",
                            evidence=[rule],
                            description=reason,
                        )
                    )

        # -------------------------------------------------------------
        # F6: Input-binding error — correct rule and tool, wrong values
        # -------------------------------------------------------------
        # Gold value of every directly bound input: case facts, then gold computed quantities.
        gold_inputs: dict[str, float] = {
            k: v
            for k, v in {
                "sanctioned_kw": case.facts.sanctioned_load_kw,
                "proposed_kw": case.facts.proposed_capacity_kw,
            }.items()
            if v is not None
        }
        for gold_comp in (case.expected_answer.computed if case.expected_answer else []):
            for key in ("dt_capacity_kva", "cumulative_solar_kw", "days_elapsed"):
                if isinstance(gold_comp.get(key), int | float):
                    gold_inputs[key] = float(gold_comp[key])
        for comp in computed:
            for key, gold in gold_inputs.items():
                bound = comp.get(key)
                if isinstance(bound, int | float) and abs(bound - gold) > 0.01:
                    detected_faults.append(
                        DetectedFault(
                            fault_class=FaultClass.F6,
                            trigger=f"input_binding_mismatch:{key}",
                            evidence=[str(bound)],
                            description=f"'{key}' bound to {bound} instead of the true {gold}.",
                        )
                    )

        for rec in provenance:
            required = REQUIRED_SOURCE_FIELD.get(rec["field"])
            sources = list(rec.get("inputs") or {})
            if required and sources and required not in sources:
                detected_faults.append(
                    DetectedFault(
                        fault_class=FaultClass.F6,
                        trigger=f"input_binding_source_mismatch:{rec['field']}<-{','.join(sources)}",
                        evidence=sources,
                        description=f"'{rec['field']}' bound from {sources} instead of '{required}'.",
                    )
                )

        # -------------------------------------------------------------
        # F7: Computation error — arithmetic or math failure
        # -------------------------------------------------------------
        for gold_comp in case.expected_answer.computed:
            metric = gold_comp.get("metric")
            for comp in computed:
                if comp.get("metric") == metric:
                    for key in ["subsidy_inr", "subsidy_amount_inr", "saturation_pct", "excess_kw"]:
                        if (
                            key in gold_comp
                            and key in comp
                            and abs(comp[key] - gold_comp[key]) > 1.0
                        ):
                            detected_faults.append(
                                DetectedFault(
                                    fault_class=FaultClass.F7,
                                    trigger=f"arithmetic_mismatch:{key}",
                                    evidence=[f"expected={gold_comp[key]}, actual={comp[key]}"],
                                    description=f"Computation error in '{key}': expected {gold_comp[key]}, got {comp[key]}.",
                                )
                            )

        # -------------------------------------------------------------
        # Determine Precedence-Ranked Primary Failure Class
        # -------------------------------------------------------------
        primary_fault_class: FaultClass | None = None
        for fc in FAULT_PRECEDENCE:
            if any(f.fault_class == fc for f in detected_faults):
                primary_fault_class = fc
                break

        # -------------------------------------------------------------
        # Determine overall Case Correctness & Unsupported-Correct
        # -------------------------------------------------------------
        is_correct = False
        if case.expected_decision == ExpectedDecision.ABSTAIN:
            is_correct = decision == ExpectedDecision.ABSTAIN
        else:
            if decision == ExpectedDecision.ANSWER:
                if case.expected_answer.blocking_stage is None:
                    # Clean case: must approve without reasoning/arithmetic/epistemic errors
                    is_correct = (
                        blocking_stage is None
                        and (not root_cause or root_cause == "nominal_compliant")
                        and not any(f.fault_class in {FaultClass.F5, FaultClass.F6, FaultClass.F7} for f in detected_faults)
                    )
                else:
                    # Non-compliant case: must block with correct blocking stage
                    is_correct = (
                        blocking_stage is not None
                        and blocking_stage == case.expected_answer.blocking_stage
                        and not any(f.fault_class == FaultClass.F5 for f in detected_faults)
                    )

        if invalid:
            is_correct = False

        # Outcome alone (no fault conditions): what a trap flips. Approve = APPROVED and not blocked.
        gen_approved = raw_decision == "APPROVED" and blocking_stage is None
        exp_approved = case.expected_answer.blocking_stage is None
        if case.expected_decision == ExpectedDecision.ABSTAIN:
            outcome_correct = decision == ExpectedDecision.ABSTAIN
        else:
            outcome_correct = decision == ExpectedDecision.ANSWER and gen_approved == exp_approved
        outcome_flipped = decision == ExpectedDecision.ANSWER and gen_approved != exp_approved
        if invalid:
            outcome_correct = outcome_flipped = False

        # Unsupported-correct: Decision nominally correct, but evidence is invalid (F1, F2, or F3)
        has_evidence_fault = any(
            f.fault_class in {FaultClass.F1, FaultClass.F2, FaultClass.F3}
            for f in detected_faults
        )
        unsupported_correct = is_correct and has_evidence_fault

        # -------------------------------------------------------------
        # Determine Whether Generator Actually Committed Probed Faults
        # -------------------------------------------------------------
        fault_event_committed: dict[str, bool] = {}
        fault_event_committed_citation: dict[str, bool] = {}
        for fe in case.fault_events:
            committed = False
            if fe.fault_class == FaultClass.F1:
                committed = any(f.fault_class == FaultClass.F1 for f in detected_faults)
            elif fe.fault_class == FaultClass.F2:
                # the trap clause itself (not any other wrong-state citation)
                committed = any(f.fault_class == FaultClass.F2 and set(f.evidence) & set(fe.gold_evidence)
                                for f in detected_faults)
            elif fe.fault_class == FaultClass.F3:
                # the trap clause itself, or any part of the same superseded instrument
                trap_docs = {ev.split("#")[0] for ev in fe.gold_evidence}
                committed = any(
                    f.fault_class == FaultClass.F3
                    and any(e in fe.gold_evidence or e.split("#")[0] in trap_docs for e in f.evidence)
                    for f in detected_faults
                )
            elif fe.fault_class == FaultClass.F4:
                committed = any(
                    f.fault_class == FaultClass.F4 and any(ev in f.evidence for ev in fe.gold_evidence)
                    for f in detected_faults
                )
            elif fe.fault_class == FaultClass.F5:
                committed = any(f.fault_class == FaultClass.F5 and set(f.evidence) & set(fe.gold_evidence)
                                for f in detected_faults)
            elif fe.fault_class == FaultClass.F6:
                committed = any(f.fault_class == FaultClass.F6 for f in detected_faults)
            elif fe.fault_class == FaultClass.F7:
                committed = any(f.fault_class == FaultClass.F7 for f in detected_faults)
            elif fe.fault_class in {FaultClass.F8, FaultClass.F9}:
                committed = decision == ExpectedDecision.ANSWER and not invalid

            fault_event_committed_citation[fe.fault_event_id] = committed
            abstention = fe.fault_class in {FaultClass.F8, FaultClass.F9}
            fault_event_committed[fe.fault_event_id] = committed and (abstention or outcome_flipped)

        # -------------------------------------------------------------
        # Verifier Flag Evaluation over Committed Faults & NFOs
        # -------------------------------------------------------------
        fault_event_matches: dict[str, bool] = {}
        fault_event_matches_clause: dict[str, bool] = {}
        fault_event_matches_class: dict[str, bool] = {}
        avoided_trap_matches: dict[str, bool] = {}
        raw_flags = {str(flag) for flag in (verifier_flags or []) if flag is not None}
        findings = [_split_flag(f) for f in raw_flags]
        # Class and clause only (as before D32), for the class and NFO checks below.
        flags_set = {f"{c}:{cl}" if cl else c for c, cl, _ in findings}

        # Completeness flags name candidate clause ids, so they may only ever match F4 events.
        comp_flags = completeness_flags or []
        comp_ids = {i for flag in comp_flags for i in flag.split(":", 2)[-1].split("|")}
        for fe in case.fault_events:
            by_class = any(fe.fault_class.value in flag for flag in flags_set)
            gold_ids = set(fe.gold_evidence)
            gold_docs = {g.split("#")[0] for g in gold_ids}

            def names_planted(cls: str, clause: str, fe: FaultEvent = fe, gold_ids: set[str] = gold_ids,
                              gold_docs: set[str] = gold_docs) -> bool:
                if fe.fault_class in CLAUSELESS_CLASSES:  # no clause to name: the class must match
                    return cls == "ANY" or cls.split("-")[0] == fe.fault_class.value
                return bool(clause) and (bool(self._names(clause) & gold_ids)
                                         or (fe.fault_class == FaultClass.F3 and clause.split("#")[0] in gold_docs))

            # The completeness checklist names missing applicable rules: a missing_rule finding by construction.
            comp_hit = completeness_applied and fe.fault_class == FaultClass.F4 and bool(comp_ids & gold_ids)
            want = CLASS_REASON.get(fe.fault_class)
            # Secondary (the D26 primary): a finding names the planted clause, whatever reason or class it gives.
            by_evidence = any(names_planted(cls, clause) for cls, clause, _ in findings) or comp_hit
            # Primary (D32): that finding also gives the reason of the event's class; a missing or invalid reason
            # never matches. Classes without a reason code (F1, F6-F9) keep the clause/class rule.
            by_reason = by_evidence if want is None else (
                any(names_planted(cls, clause) and reason == want for cls, clause, reason in findings) or comp_hit)
            # Secondary: class agreement, i.e. that finding also gives the planted class (taxonomy ablation).
            by_evidence_class = any(names_planted(cls, clause) and cls.split("-")[0] == fe.fault_class.value
                                    for cls, clause, _ in findings) or comp_hit
            if fault_event_committed_citation.get(fe.fault_event_id, False):
                # Generator committed error: opportunity for verifier detection (Sensitivity)
                fault_event_matches[fe.fault_event_id] = by_reason
                fault_event_matches_clause[fe.fault_event_id] = by_evidence
                fault_event_matches_class[fe.fault_event_id] = by_evidence_class
            else:
                # Generator avoided error: a finding on the planted clause (or of its class) is a false alarm
                avoided_trap_matches[fe.fault_event_id] = by_evidence or by_class

        nfo_matches: dict[str, bool] = {}
        for nfo in case.non_fault_opportunities:
            cls = NFO_PROPERTY_CLASS.get(nfo.target_property)
            flagged = any(
                nfo.opportunity_id in flag
                or nfo.target_property in flag.lower()
                or (cls is not None and cls in flag)
                for flag in flags_set
            )
            nfo_matches[nfo.opportunity_id] = flagged

        # H3: for each ground-truth omission, did verification and/or completeness flag it?
        omission_catches = {
            f.evidence[0]: {
                "subtype": f.fault_subtype.value if f.fault_subtype else None,
                "verifier": any(cls in {"F4", "F4-R", "F4-C", "ANY"} and f.evidence[0] in self._names(clause)
                                for cls, clause, _ in findings),
                "verifier_class": any("F4" in flag for flag in flags_set),
                "completeness": f.evidence[0] in comp_ids,
            }
            for f in detected_faults
            if f.fault_class == FaultClass.F4 and f.evidence
        }

        # Compute empirical evidence overlap if verifier chunks supplied
        evidence_overlap_jaccard = compute_evidence_overlap(
            retrieved_chunk_ids, verifier_chunk_ids
        )

        return CaseClassificationResult(
            case_id=case.case_id,
            cluster_clause_id=cluster_clause_id,
            decision=decision,
            invalid_output=invalid,
            expected_decision=case.expected_decision,
            is_correct=is_correct,
            outcome_correct=outcome_correct,
            unsupported_correct=unsupported_correct,
            detected_faults=detected_faults,
            primary_fault_class=primary_fault_class,
            fault_event_committed=fault_event_committed,
            fault_event_committed_citation=fault_event_committed_citation,
            fault_event_matches=fault_event_matches,
            fault_event_matches_clause=fault_event_matches_clause,
            fault_event_matches_class=fault_event_matches_class,
            nfo_matches=nfo_matches,
            avoided_trap_matches=avoided_trap_matches,
            evidence_overlap_jaccard=evidence_overlap_jaccard,
            independence_config=independence_config,
            verifier_flags=sorted(raw_flags),
            completeness_flags=comp_flags,
            completeness_applied=completeness_applied,
            omission_catches=omission_catches,
        )


def evaluate_verifier_over_fault_events(
    fault_events: list[FaultEvent],
    committed_events: dict[str, bool],
    flagged_ids: set[str],
) -> dict[str, float]:
    """Calculate sensitivity strictly conditioned on the generator actually committing the fault."""
    committed_fes = [fe for fe in fault_events if committed_events.get(fe.fault_event_id, False)]
    if not committed_fes:
        return {"sensitivity": 1.0, "committed_count": 0.0}

    total = len(committed_fes)
    caught = sum(1 for fe in committed_fes if fe.fault_event_id in flagged_ids)
    return {"sensitivity": caught / total, "committed_count": float(total)}


def evaluate_verifier_over_nfos(
    nfos: list[NonFaultOpportunity],
    avoided_events: list[FaultEvent],
    flagged_ids: set[str],
) -> dict[str, float]:
    """Calculate specificity over non-fault opportunities and avoided trap opportunities."""
    total_opportunities = len(nfos) + len(avoided_events)
    if total_opportunities == 0:
        return {"specificity": 1.0, "total_opportunities": 0.0}

    true_negatives = sum(
        1 for nfo in nfos if nfo.opportunity_id not in flagged_ids
    ) + sum(
        1 for fe in avoided_events if fe.fault_event_id not in flagged_ids
    )

    return {
        "specificity": true_negatives / total_opportunities,
        "total_opportunities": float(total_opportunities),
    }
