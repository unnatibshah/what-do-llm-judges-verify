"""Deterministic lookup and validator for MNRE ALMM List-I and DCR compliance."""

from dataclasses import dataclass


@dataclass
class EquipmentComplianceResult:
    """Compliance verification for solar photovoltaic modules and cells."""

    is_compliant: bool
    module_make: str
    almm_enlisted: bool
    dcr_compliant: bool
    commissioning_date: str
    almm_required: bool
    rejection_reason: str | None = None


# Known ALMM List-I manufacturers in India
ALMM_LIST_I_MANUFACTURERS = {
    "waaree",
    "tata power",
    "vikram solar",
    "adani solar",
    "renewsys",
    "premier energies",
    "goldi solar",
    "rayzon solar",
    "gautam solar",
    "satvik",
}


def check_almm_and_dcr(
    module_make: str | None,
    dcr_claimed: bool = True,
    case_date: str = "2024-06-15",
    subsidy_claimed: bool = True,
) -> EquipmentComplianceResult:
    """Evaluate equipment compliance under MNRE ALMM orders and DCR mandates.

    Statutory Mandates:
    - ALMM Reimposition Order (2024-03-29): Mandates ALMM List-I for all government and subsidy-backed projects from 2024-04-01.
    - DCR Mandate: Central Financial Assistance requires 100% domestic cells and wafers.
    """
    make_clean = (module_make or "").lower()
    is_almm = (
        any(m in make_clean for m in ALMM_LIST_I_MANUFACTURERS)
        or "almm" in make_clean
        or "listed" in make_clean
    )

    # If unlisted / foreign module without ALMM enlistment
    if (
        "unlisted" in make_clean
        or "not_listed" in make_clean
        or "imported tier-1" in make_clean
        or "non-almm" in make_clean
    ):
        is_almm = False

    # ALMM is mandatory post 2024-04-01
    almm_mandatory = case_date >= "2024-04-01"

    if almm_mandatory and not is_almm:
        return EquipmentComplianceResult(
            is_compliant=False,
            module_make=module_make or "Unknown",
            almm_enlisted=False,
            dcr_compliant=dcr_claimed,
            commissioning_date=case_date,
            almm_required=True,
            rejection_reason=(
                f"Proposed module make '{module_make}' is not enlisted under MNRE ALMM List-I. "
                "Per MNRE Order dated 2024-03-29, ALMM enlistment is strictly mandatory for all "
                "grid-connected rooftop solar installations from 2024-04-01."
            ),
        )

    # DCR check for subsidy applications
    if subsidy_claimed and not dcr_claimed:
        return EquipmentComplianceResult(
            is_compliant=False,
            module_make=module_make or "Unknown",
            almm_enlisted=is_almm,
            dcr_compliant=False,
            commissioning_date=case_date,
            almm_required=almm_mandatory,
            rejection_reason=(
                "Application claims Central Financial Assistance subsidy, but proposed solar modules "
                "do not use domestically manufactured cells/wafers (non-DCR compliant)."
            ),
        )

    return EquipmentComplianceResult(
        is_compliant=True,
        module_make=module_make or "Waaree (ALMM Enlisted)",
        almm_enlisted=True,
        dcr_compliant=dcr_claimed,
        commissioning_date=case_date,
        almm_required=almm_mandatory,
        rejection_reason=None,
    )
