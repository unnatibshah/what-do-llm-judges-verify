"""Applicability predicates and closed case-facts vocabulary schemas."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from suryabench.core.enums import (
    AlmmStatus,
    ConfidenceLevel,
    ConsumerCategory,
    DiscomCode,
    MeteringMode,
    PremisesType,
    StateCode,
)


class CaseFacts(BaseModel):
    """Closed case-facts vocabulary per protocol §7."""

    model_config = ConfigDict(extra="forbid")

    state: StateCode = Field(..., description="Target state/jurisdiction code (MH, RJ, IN)")
    discom: DiscomCode | None = Field(default=None, description="DISCOM code if applicable")
    consumer_category: ConsumerCategory = Field(..., description="residential, commercial, etc.")
    tariff_slab: str | None = Field(default=None, description="State-specific tariff slab")
    sanctioned_load_kw: float | None = Field(
        default=None, ge=0.0, description="Sanctioned/contract demand load in kW"
    )
    connected_load_kw: float | None = Field(
        default=None, ge=0.0, description="Connected load in kW"
    )
    proposed_capacity_kw: float | None = Field(
        default=None, ge=0.0, description="Proposed solar PV capacity in kW"
    )
    premises_type: PremisesType | None = Field(
        default=None, description="individual, group_housing, or rwa_common"
    )
    metering_mode: MeteringMode | None = Field(
        default=None, description="net, gross, or net_billing"
    )
    module_almm_status: AlmmStatus | None = Field(
        default=None, description="listed, not_listed, or unknown"
    )
    dcr_claimed: bool | None = Field(
        default=None, description="Whether domestic content requirement is claimed"
    )
    subsidy_claimed: bool | None = Field(default=None, description="Whether CFA subsidy is claimed")
    application_stage: str | None = Field(default=None, description="Stage of application process")
    install_before_feasibility: bool | None = Field(
        default=None, description="Flag indicating premature physical install"
    )
    case_date: str | None = Field(default=None, description="Date of case interaction (YYYY-MM-DD)")


OperatorType = Literal["eq", "neq", "in", "not_in", "gt", "gte", "lt", "lte"]


class ConditionLeaf(BaseModel):
    """Leaf condition testing a field against a value with an operator."""

    model_config = ConfigDict(extra="forbid")

    field: str = Field(..., description="Field name in CaseFacts")
    op: OperatorType = Field(..., description="Comparison operator")
    value: Any = Field(..., description="Expected value or set of values")


class ConditionGroup(BaseModel):
    """Logical grouping of conditions with 'all' (AND) or 'any' (OR)."""

    model_config = ConfigDict(extra="forbid")

    all: list["Condition"] | None = Field(default=None, description="Logical AND of sub-conditions")
    any: list["Condition"] | None = Field(default=None, description="Logical OR of sub-conditions")


Condition = ConditionLeaf | ConditionGroup


class ApplicabilityPredicate(BaseModel):
    """Predicate determining whether a rule clause applies to a specific case."""

    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(..., description="Rule node ID this predicate evaluates for")
    applies_when: Condition = Field(..., description="Executable condition tree")
    applicability_basis: str = Field(..., description="Prose rationale grounding the predicate")
    basis_span: list[int] | None = Field(
        None,
        min_length=2,
        max_length=2,
        description="[start, end] character span in regulatory text",
    )
    confidence: ConfidenceLevel = Field(
        default=ConfidenceLevel.HIGH, description="Confidence in predicate logic"
    )
