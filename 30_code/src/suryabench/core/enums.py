"""Controlled vocabularies and enumerations for SuryaBench."""

from enum import StrEnum


class JurisdictionLevel(StrEnum):
    """Jurisdiction level."""

    STATE = "state"
    CENTRAL = "central"


class StateCode(StrEnum):
    """State or national jurisdiction codes."""

    MH = "MH"
    RJ = "RJ"
    IN = "IN"
    # Corpus r3 staging jurisdictions (2026-10-01)
    GJ = "GJ"
    KA = "KA"
    TN = "TN"
    DL = "DL"
    UP = "UP"


class DiscomCode(StrEnum):
    """Target DISCOM identifier."""

    MSEDCL = "MSEDCL"
    JVVNL = "JVVNL"
    AVVNL = "AVVNL"
    JDVVNL = "JdVVNL"
    # Corpus r3 staging DISCOMs (2026-10-01)
    UGVCL = "UGVCL"
    MGVCL = "MGVCL"
    BESCOM = "BESCOM"
    HESCOM = "HESCOM"
    TANGEDCO = "TANGEDCO"
    BRPL = "BRPL"
    TPDDL = "TPDDL"
    PVVNL = "PVVNL"
    MVVNL = "MVVNL"


class DocumentClass(StrEnum):
    """Document authority classes C1–C6 per protocol §2."""

    C1 = "C1"  # Central scheme guidelines (PM Surya Ghar)
    C2 = "C2"  # Central technical lists (ALMM, DCR)
    C3 = "C3"  # State regulatory commission regulations / tariff orders
    C4 = "C4"  # State regulatory commission orders / adjudications
    C5 = "C5"  # DISCOM operational circulars / procedures
    C6 = "C6"  # State nodal agency instructions (MEDA, RRECL)


class AuthorityRank(StrEnum):
    """Operational conflict-resolution rank A1–A6 per protocol §3."""

    A1 = "A1"  # Statute / SERC regulation (C3)
    A2 = "A2"  # SERC order (C4)
    A3 = "A3"  # Central scheme guideline (C1)
    A4 = "A4"  # Central technical list (C2)
    A5 = "A5"  # Nodal agency instruction (C6)
    A6 = "A6"  # DISCOM procedural circular (C5)


class EffectiveDateBasis(StrEnum):
    """Effective date derivation rules E1–E9 per protocol §5."""

    E1 = "E1"  # Explicit date stated in text
    E2 = "E2"  # 'With immediate effect' -> gazette date else doc date
    E3 = "E3"  # Tied to financial year -> 1 April of that FY
    E4 = "E4"  # Effective on publication -> gazette date
    E5 = "E5"  # Silent, gazette date present -> gazette date
    E6 = "E6"  # Silent, only doc date present -> doc date
    E7 = "E7"  # Amendment with no date of its own -> parent's date if high confidence
    E8 = "E8"  # Prospective, conditional on an external event -> UNKNOWN
    E9 = "E9"  # No usable date derivable -> UNKNOWN


class ConfidenceLevel(StrEnum):
    """Confidence levels."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class NodeStatus(StrEnum):
    """Clause status at snapshot date per protocol §6."""

    IN_FORCE = "in_force"
    SUPERSEDED = "superseded"
    PARTIALLY_SUPERSEDED = "partially_superseded"
    UNKNOWN = "unknown"


class CurrencyVerdict(StrEnum):
    """Verdict returned by currency oracle in_force(node, date)."""

    IN_FORCE = "in_force"
    SUPERSEDED = "superseded"
    PARTIALLY_SUPERSEDED = "partially_superseded"
    NOT_YET_IN_FORCE = "not_yet_in_force"
    UNDETERMINED = "undetermined"


class EdgeRelation(StrEnum):
    """Supersession graph edge relations per protocol §6."""

    SUPERSEDED_BY = "superseded_by"
    AMENDED_BY = "amended_by"
    CLARIFIED_BY = "clarified_by"
    CONSOLIDATED_INTO = "consolidated_into"
    CONFLICTS_WITH = "conflicts_with"
    IMPLEMENTS = "implements"


class EdgeEvidenceType(StrEnum):
    """Edge evidence provenance per protocol §6."""

    EXPLICIT = "explicit"  # Later document names earlier clause/order
    IMPLICIT = "implicit"  # Same issuer, subject, later date, no cross-reference
    INFERRED = "inferred"  # Interpretive judgment


class FaultClass(StrEnum):
    """SuryaBench F1–F9 failure taxonomy."""

    F1 = "F1"  # Fabrication: clause does not exist in corpus
    F2 = "F2"  # Jurisdiction: wrong state jurisdiction applied
    F3 = "F3"  # Currency: superseded or amended clause cited
    F4 = "F4"  # Omission: applicable rule omitted (F4-R or F4-C)
    F5 = "F5"  # Applicability: rule applied outside boundary conditions
    F6 = "F6"  # Input binding: correct rule fed wrong case facts
    F7 = "F7"  # Arithmetic/Unit: math or unit conversion failure
    F8 = "F8"  # Abstention: authoritative conflict requires abstention
    F9 = "F9"  # Abstention: missing mandatory case facts require abstention


class FaultSubtype(StrEnum):
    """Subtypes for omission (F4) errors."""

    F4_R = "F4-R"  # Retrieval omission: rule was not retrieved
    F4_C = "F4-C"  # Citation/Reasoning omission: rule was retrieved but omitted from answer


class IndependenceConfig(StrEnum):
    """Verifier independence lattice configurations (I1, I2, I3)."""

    I000 = "000"  # Shared evidence verifier (Arm 3)
    I100 = "100"  # Independent retrieval verifier
    I111 = "111"  # Independent retrieval + structured registry + currency verification (Arm 4)
    I110 = "110"  # Independent retrieval + structured registry
    I100N = "100-neutral"  # Independent retrieval, neutral (non-audit) query wording (RD3)


class Discoverability(StrEnum):
    """Document discoverability mode per protocol §2."""

    NAV = "nav"
    SITE_SEARCH = "site_search"
    WEB_SEARCH = "web_search"
    LINKED = "linked"
    ORPHAN = "orphan"


class TextLayer(StrEnum):
    """Corpus text extraction layer."""

    NATIVE = "native"
    OCR = "ocr"
    NONE = "none"


class ConsumerCategory(StrEnum):
    """Consumer category in case-facts vocabulary."""

    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    AGRICULTURAL = "agricultural"
    INDUSTRIAL = "industrial"


class PremisesType(StrEnum):
    """Premises type in case-facts vocabulary."""

    INDIVIDUAL = "individual"
    GROUP_HOUSING = "group_housing"
    RWA_COMMON = "rwa_common"


class MeteringMode(StrEnum):
    """Metering mode in case-facts vocabulary."""

    NET = "net"
    GROSS = "gross"
    NET_BILLING = "net_billing"


class AlmmStatus(StrEnum):
    """ALMM module enlistment status."""

    LISTED = "listed"
    NOT_LISTED = "not_listed"
    UNKNOWN = "unknown"


class ExpectedDecision(StrEnum):
    """Expected benchmark decision."""

    ANSWER = "ANSWER"
    ABSTAIN = "ABSTAIN"


class SubjectTag(StrEnum):
    """Controlled 20-30 term subject vocabulary per protocol §6 & §0.2.1."""

    NET_METERING_CAPACITY_CAP = "net_metering_capacity_cap"
    GROSS_METERING_CAPACITY_CAP = "gross_metering_capacity_cap"
    DT_TRANSFORMER_CAPACITY_LIMIT = "dt_transformer_capacity_limit"
    SANCTIONED_LOAD_RATIO = "sanctioned_load_ratio"
    CONNECTED_LOAD_RESTRICTION = "connected_load_restriction"
    SUBSIDY_CFA_CENTRAL_RESIDENTIAL = "subsidy_cfa_central_residential"
    SUBSIDY_CFA_GROUP_HOUSING = "subsidy_cfa_group_housing"
    SUBSIDY_DISBURSEMENT_PROCESS = "subsidy_disbursement_process"
    ALMM_MODULE_ENLISTMENT = "almm_module_enlistment"
    DCR_CELL_MODULE_REQUIREMENT = "dcr_cell_module_requirement"
    INTERCONNECTION_FEASIBILITY_STAGE = "interconnection_feasibility_stage"
    METER_PHASE_THRESHOLD = "meter_phase_threshold"
    APPLICATION_FEE_TARIFF = "application_fee_tariff"
    COMMISSIONING_REPORT_PROCEDURE = "commissioning_report_procedure"
    BILLING_SETTLEMENT_PERIOD = "billing_settlement_period"
    GRID_INVERTER_SAFETY_STANDARD = "grid_inverter_safety_standard"
    SURPLUS_ENERGY_PURCHASE_RATE = "surplus_energy_purchase_rate"
    DISCOM_APPROVAL_TIMELINE = "discom_approval_timeline"
    LOAD_ENHANCEMENT_REQUIREMENT = "load_enhancement_requirement"
    THIRD_PARTY_PPA_RESIDENTIAL = "third_party_ppa_residential"
