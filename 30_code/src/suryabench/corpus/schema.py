"""Corpus document inventory and manifest schemas."""

from pydantic import BaseModel, ConfigDict, Field

from suryabench.core.enums import (
    ConfidenceLevel,
    Discoverability,
    DocumentClass,
    EffectiveDateBasis,
    JurisdictionLevel,
    StateCode,
    TextLayer,
)


class Jurisdiction(BaseModel):
    """Document or node jurisdiction specification."""

    model_config = ConfigDict(extra="forbid")

    level: JurisdictionLevel
    code: StateCode
    discom: str | None = None


class DocumentInventory(BaseModel):
    """Inventory record for a single regulatory document in the corpus."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    doc_id: str = Field(..., description="Unique document ID, e.g. MH-C3-004")
    title: str = Field(..., description="Title as printed on the document")
    doc_class: DocumentClass = Field(..., alias="class", description="Authority class C1–C6")
    issuer: str = Field(..., description="Exact issuing body")
    jurisdiction: Jurisdiction
    doc_number: str | None = Field(None, description="Document/circular number if printed")
    doc_date: str = Field(..., description="Printed document date (YYYY-MM-DD)")
    effective_date: str = Field(..., description="Derived effective date or 'UNKNOWN'")
    effective_date_basis: EffectiveDateBasis = Field(..., description="Derivation rule E1–E9")
    effective_date_confidence: ConfidenceLevel = Field(
        ..., description="Confidence: high/medium/low"
    )
    retrieved_url: str | None = Field(None, description="URL where document was located")
    retrieved_via: Discoverability = Field(..., description="Access route")
    retrieved_at: str = Field(..., description="ISO 8601 download timestamp")
    sha256: str = Field(..., description="SHA-256 hash of immutable raw file")
    pages: int = Field(..., ge=1, description="Total page count")
    text_layer: TextLayer = Field(..., description="native, ocr, or none")
    status: str = Field(..., description="presumed_current, presumed_superseded, or unknown")
    discoverability: Discoverability = Field(
        ..., description="nav, site_search, web_search, linked, orphan"
    )
    notes: str | None = Field(None, description="Researcher audit notes or anomalies")
    # Corpus r3 staging fields (absent, i.e. None, for every r2 document).
    verification_status: str | None = Field(
        None, description="UNVERIFIED until a human checks the document against its official source"
    )
    source_class: str | None = Field(
        None,
        description="regulator_original, government_mirror, discom_original or discom_copy (D23)",
    )
    provenance_file: str | None = Field(
        None, description="Provenance record, relative to the corpus directory"
    )


class CorpusManifest(BaseModel):
    """Corpus manifest representing the complete inventory of frozen documents."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    corpus_version: str = Field(
        ..., description="Corpus version, e.g. SuryaBench-Corpus-2026.11-gate0"
    )
    created_at: str = Field(..., description="ISO 8601 manifest creation timestamp")
    documents: list[DocumentInventory] = Field(
        default_factory=list, description="List of inventory records"
    )
