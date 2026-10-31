"""Synthetic benchmark case, fault events, and non-fault opportunities schemas."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from suryabench.applicability.schema import CaseFacts
from suryabench.core.enums import (
    ConfidenceLevel,
    ExpectedDecision,
    FaultClass,
    FaultSubtype,
)

# Closed label space for ExpectedAnswer.blocking_stage (task definition, from the case generator).
# Correctness on non-compliant cases requires the arm to name the matching stage.
BLOCKING_STAGES: tuple[str, ...] = (
    "technical_feasibility", "jurisdiction_check", "subsidy_approval", "equipment_verification",
    "metering_mode_selection", "deemed_approval", "discom_rejection_appeal",
    "discom_restriction_appeal", "portal_registration", "data_validation",
)

class FaultEvent(BaseModel):
    """Structured fault event embedded in a benchmark case per protocol §7A."""

    model_config = ConfigDict(extra="forbid")

    fault_event_id: str = Field(..., description="Unique fault event ID, e.g. MH-T1-017#fe-1")
    case_id: str = Field(..., description="Parent case ID")
    fault_class: FaultClass = Field(..., description="Failure class F1–F9")
    fault_subtype: FaultSubtype | None = Field(
        default=None, description="F4-R or F4-C where fault_class is F4; null otherwise"
    )
    gold_trigger: str = Field(..., description="Ground-truth condition triggering this fault")
    gold_evidence: list[str] = Field(..., description="Governing clause node IDs or evidence")
    expected_behavior: str = Field(..., description="Action agent/verifier should have taken")
    verifier_flag: bool | None = Field(default=None, description="Flagged by verifier during eval")
    verifier_evidence: list[str] | None = Field(
        default=None, description="Evidence cited by verifier"
    )

    @model_validator(mode="after")
    def validate_f4_subtype(self) -> "FaultEvent":
        """Assert that F4 fault events have F4-R or F4-C subtype, and others have None."""
        if self.fault_class == FaultClass.F4:
            if self.fault_subtype not in {FaultSubtype.F4_R, FaultSubtype.F4_C}:
                raise ValueError(
                    "FaultEvent with fault_class='F4' must specify fault_subtype ('F4-R' or 'F4-C')"
                )
        else:
            if self.fault_subtype is not None:
                raise ValueError(f"fault_subtype must be None for fault_class='{self.fault_class}'")
        return self


class NonFaultOpportunity(BaseModel):
    """Explicitly enumerated non-fault opportunity required to compute specificity per protocol §7A."""

    model_config = ConfigDict(extra="forbid")

    opportunity_id: str = Field(..., description="Unique opportunity ID, e.g. MH-T1-017#nfo-1")
    case_id: str = Field(..., description="Parent case ID")
    target_property: str = Field(
        ..., description="Property evaluated (e.g. currency, jurisdiction, applicability)"
    )
    claim_text: str = Field(..., description="Statement/claim that is factually sound")
    gold_valid: bool = Field(
        default=True, description="Ground-truth validity (always True for NFO)"
    )


class ApplicableRuleReference(BaseModel):
    """Reference to an applicable regulatory rule grounding a case."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str = Field(..., description="Clause node ID, e.g. MH-C3-004#cl-7.2")
    clause: str = Field(..., description="Clause number")
    effective_date: str = Field(..., description="Effective date at snapshot")
    jurisdiction: str = Field(..., description="Jurisdiction code (MH, RJ, IN)")
    applicability_basis: str = Field(..., description="Reason this rule applies to the case facts")


class CaseInputs(BaseModel):
    """Surface facsimiles exposed to the agent as task inputs."""

    model_config = ConfigDict(extra="forbid")

    bill: str = Field(..., description="Electricity bill facsimile text")
    proposal: str = Field(..., description="Installer solar proposal facsimile text")
    portal_state: str = Field(
        ..., description="DISCOM interconnection portal status facsimile text"
    )


class ExpectedAnswer(BaseModel):
    """Deterministic expected answer outputs for a case."""

    model_config = ConfigDict(extra="forbid")

    blocking_stage: str | None = Field(
        default=None, description="Stage blocking interconnection, if any"
    )
    root_cause: str | None = Field(default=None, description="Primary regulatory root cause")
    next_action: str | None = Field(default=None, description="Required next operational action")
    prohibited_actions: list[str] = Field(default_factory=list, description="Prohibited actions")
    computed: list[dict[str, Any]] = Field(
        default_factory=list, description="Deterministic numeric or tabular computations"
    )


class GroundTruthProvenance(BaseModel):
    """Provenance supporting ground truth labels."""

    model_config = ConfigDict(extra="forbid")

    basis: str = Field(..., description="e.g. explicit_applicability, explicit_supersession")
    confidence: ConfidenceLevel = Field(..., description="high, medium, or low")


class BenchmarkCase(BaseModel):
    """A complete benchmark case record per protocol §7A."""

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(..., description="Unique case identifier, e.g. MH-T1-017")
    corpus_version: str = Field(..., description="Corpus version defining experimental context")
    cluster_id: str | None = Field(
        default=None, description="Generating clause (analysis unit); gold, hidden from arms. v2 cases only"
    )
    facts: CaseFacts = Field(..., description="Closed vocabulary case facts")
    inputs: CaseInputs = Field(..., description="Surface facsimiles provided to agent")
    applicable_rules: list[ApplicableRuleReference] = Field(
        default_factory=list, description="List of governing applicable rules"
    )
    expected_answer: ExpectedAnswer = Field(
        ..., description="Expected diagnostic decision & computed outputs"
    )
    ground_truth_provenance: GroundTruthProvenance
    failure_class_probed: str = Field(
        ..., description="Probed condition: 'CLEAN', 'F1'..'F9', or 'MULTI'"
    )
    expected_decision: ExpectedDecision = Field(..., description="ANSWER or ABSTAIN")
    abstention_reason: str | None = Field(
        default=None, description="Reason for abstention when expected_decision is ABSTAIN"
    )
    fault_events: list[FaultEvent] = Field(
        default_factory=list, description="Structured fault events present in this case"
    )
    non_fault_opportunities: list[NonFaultOpportunity] = Field(
        default_factory=list, description="Explicit checkable claims that are non-faults"
    )
