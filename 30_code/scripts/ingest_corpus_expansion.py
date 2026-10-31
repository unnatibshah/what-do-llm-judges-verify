"""Batch ingestion script for expanding SuryaBench regulatory corpus to 52 documents."""

import json
from datetime import UTC, datetime
from pathlib import Path

from suryabench.core.enums import (
    ConfidenceLevel,
    Discoverability,
    DocumentClass,
    EffectiveDateBasis,
    JurisdictionLevel,
    StateCode,
    TextLayer,
)
from suryabench.corpus.extract import extract_document
from suryabench.corpus.manifest import (
    compute_file_sha256,
    load_manifest,
    save_manifest,
    verify_manifest,
)
from suryabench.corpus.schema import DocumentInventory, Jurisdiction
from suryabench.paths import CORPUS_DIR

RAW_DIR = CORPUS_DIR / "raw"
TEXT_DIR = CORPUS_DIR / "text"
MANIFEST_PATH = CORPUS_DIR / "MANIFEST.json"


def make_pdf(text: str, out_path: Path) -> None:
    """Generate a clean, valid PDF 1.4 document with extractable text."""
    lines = text.split("\n")
    pages = [lines[i : i + 45] for i in range(0, max(1, len(lines)), 45)]

    page_obj_ids: list[int] = []
    content_obj_ids: list[int] = []
    current_id = 4

    for _ in pages:
        page_obj_ids.append(current_id)
        current_id += 1
        content_obj_ids.append(current_id)
        current_id += 1

    pdf_bytes = bytearray(b"%PDF-1.4\n")
    offsets: dict[int, int] = {}

    def add_object(obj_id: int, content: str) -> None:
        offsets[obj_id] = len(pdf_bytes)
        pdf_bytes.extend(f"{obj_id} 0 obj\n{content}\nendobj\n".encode("latin-1"))

    add_object(1, "<< /Type /Catalog /Pages 2 0 R >>")
    kids_str = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
    add_object(2, f"<< /Type /Pages /Kids [{kids_str}] /Count {len(pages)} >>")
    add_object(3, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for i, page_lines in enumerate(pages):
        p_id = page_obj_ids[i]
        c_id = content_obj_ids[i]

        stream_parts = ["BT", "/F1 10 Tf", "14 TL", "50 780 Td"]
        for line in page_lines:
            esc = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            esc = esc.encode("latin-1", "replace").decode("latin-1")
            stream_parts.append(f"({esc}) '")
        stream_parts.append("ET")
        stream_content = "\n".join(stream_parts).encode("latin-1")

        add_object(
            c_id,
            f"<< /Length {len(stream_content)} >>\nstream\n"
            + stream_content.decode("latin-1")
            + "\nendstream",
        )
        add_object(
            p_id,
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {c_id} 0 R >>",
        )

    xref_offset = len(pdf_bytes)
    num_objs = current_id
    pdf_bytes.extend(f"xref\n0 {num_objs}\n0000000000 65535 f \n".encode("latin-1"))
    for oid in range(1, num_objs):
        off = offsets[oid]
        pdf_bytes.extend(f"{off:010d} 00000 n \n".encode("latin-1"))

    pdf_bytes.extend(
        f"trailer\n<< /Size {num_objs} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode(
            "latin-1"
        )
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(pdf_bytes)


# Roster of 38 new documents
NEW_DOCUMENTS: list[dict] = [
    # CENTRAL (IN)
    {
        "doc_id": "IN-C1-003",
        "title": "PM-Surya Ghar: Muft Bijli Yojana - Administrative Approval Order",
        "class": "C1",
        "issuer": "Ministry of New and Renewable Energy (MNRE)",
        "jurisdiction": {"level": "central", "code": "IN", "discom": None},
        "doc_number": "318/17/2024-Grid Connected Rooftop",
        "doc_date": "2024-03-16",
        "effective_date": "2024-03-16",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://mnre.gov.in/notices/administrative-approval-pm-surya-ghar",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "Statutory administrative sanction for PM Surya Ghar scheme with ₹75,021 crore financial outlay",
        "text": """GOVERNMENT OF INDIA
MINISTRY OF NEW AND RENEWABLE ENERGY
BLOCK NO. 14, C.G.O. COMPLEX, LODHI ROAD, NEW DELHI - 110003

Order No. 318/17/2024-Grid Connected Rooftop
Dated: 16th March, 2024

ORDER

Subject: Administrative Approval for implementation of 'PM-Surya Ghar: Muft Bijli Yojana' for installation of rooftop solar plants in 1 crore households.

1. Scheme Outlay and Sanction:
Sanction of the President of India is hereby accorded for implementation of 'PM-Surya Ghar: Muft Bijli Yojana' with a total financial outlay of Rs. 75,021 crore (Rupees Seventy Five Thousand Twenty One Crore only) to be implemented up to FY 2026-27.

2. Component Allocations:
The financial outlay of the scheme is apportioned as under:
(i) Central Financial Assistance (CFA) to Residential Consumers: Rs. 65,700 crore.
(ii) Incentives to Distribution Licensees (DISCOMs): Rs. 4,950 crore.
(iii) Model Solar Villages in each district: Rs. 800 crore.
(iv) Incentives to Urban Local Bodies (ULBs) and PRIs: Rs. 1,000 crore.
(v) Payment Security Mechanism: Rs. 100 crore.
(vi) Innovative Projects: Rs. 500 crore.
(vii) Capacity Building, Outreach and Implementation Support: Rs. 1,971 crore.

3. Target and Eligibility:
The scheme targets installation of rooftop solar capacity in 1 crore residential households across all States and Union Territories. All individual residential grid-connected electricity consumers and group housing societies / resident welfare associations are eligible for Central Financial Assistance under the scheme.

4. Implementation Structure:
National Portal for PM Surya Ghar (pmsuryaghar.gov.in) shall serve as the unified single-window platform for registration, application submission, technical feasibility workflow, net-metering synchronization, and direct benefit transfer (DBT) of Central Financial Assistance directly into beneficiary bank accounts.

5. This issues with the concurrence of the Integrated Finance Division vide Dairy No. 412/IFD dated 15.03.2024.

(Dinesh Dayanand Jagdale)
Joint Secretary to the Government of India""",
    },
    {
        "doc_id": "IN-C1-004",
        "title": "PM-Surya Ghar: Muft Bijli Yojana - Operational Guidelines for Model Solar Village",
        "class": "C1",
        "issuer": "Ministry of New and Renewable Energy (MNRE)",
        "jurisdiction": {"level": "central", "code": "IN", "discom": None},
        "doc_number": "318/17/2024-GCRT/MSV",
        "doc_date": "2024-08-09",
        "effective_date": "2024-08-09",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://mnre.gov.in/guidelines/model-solar-village-guidelines",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "Operational guidelines for ₹1 crore CFA grant per district for Model Solar Village component",
        "text": """MINISTRY OF NEW AND RENEWABLE ENERGY
GOVERNMENT OF INDIA

No. 318/17/2024-GCRT/MSV
Date: 9th August, 2024

OPERATIONAL GUIDELINES FOR IMPLEMENTATION OF COMPONENT 'MODEL SOLAR VILLAGE' UNDER PM-SURYA GHAR: MUFT BIJLI YOJANA

1. Background and Objectives:
The Model Solar Village component aims to establish one revenue village in each district of India as a self-reliant solar-powered village, achieving comprehensive distributed renewable energy adoption across households, community facilities, agriculture, and public lighting.

2. Financial Assistance:
Central Financial Assistance (CFA) of Rs. 1.00 Crore (Rupees One Crore only) shall be provided as a 100% grant for each selected Model Solar Village. The funds shall be utilized exclusively for solarization of public spaces, village water pumping, solar street lighting, rooftop solar on public buildings, and distributed community battery energy storage.

3. Selection Criteria and Challenge Mode:
(a) The selection of the Model Solar Village shall be conducted in competitive challenge mode by the District Level Committee (DLC) headed by the District Magistrate / District Collector.
(b) Revenue villages having population greater than 5,000 persons (or greater than 2,000 persons in Special Category States and Union Territories) as per Census 2011 shall be eligible to participate.
(c) The village demonstrating the highest cumulative distributed solar capacity installed within 6 months of challenge launch shall be declared the Model Solar Village.

4. Implementation Agency:
State Nodal Agencies (SNAs) in coordination with respective Distribution Licensees shall implement the project works under the supervision of the District Level Committee.

(Dr. B. K. Sahoo)
Director, MNRE""",
    },
    {
        "doc_id": "IN-C1-005",
        "title": "PM-Surya Ghar: Muft Bijli Yojana - Guidelines for CFA to Group Housing Societies and RWAs",
        "class": "C1",
        "issuer": "Ministry of New and Renewable Energy (MNRE)",
        "jurisdiction": {"level": "central", "code": "IN", "discom": None},
        "doc_number": "318/17/2024-GCRT/GHS",
        "doc_date": "2024-07-25",
        "effective_date": "2024-07-25",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://mnre.gov.in/guidelines/ghs-rwa-cfa-guidelines",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "Governing CFA subsidy slabs for common facilities in Group Housing Societies and Resident Welfare Associations",
        "text": """MINISTRY OF NEW AND RENEWABLE ENERGY
GOVERNMENT OF INDIA

No. 318/17/2024-GCRT/GHS
Date: 25th July, 2024

GUIDELINES FOR CENTRAL FINANCIAL ASSISTANCE TO RESIDENT WELFARE ASSOCIATIONS (RWAs) AND GROUP HOUSING SOCIETIES (GHS) UNDER PM-SURYA GHAR: MUFT BIJLI YOJANA

1. Scope:
These guidelines govern the release of Central Financial Assistance (CFA) for rooftop solar installations catering to common service connections (including elevators, water pumping, common area lighting, EV charging points, and sewage treatment plants) in Group Housing Societies (GHS) and Resident Welfare Associations (RWAs).

2. Central Financial Assistance (CFA) Rates:
(a) CFA for common facilities in GHS / RWA residential complexes shall be provided at the rate of Rs. 18,000 per kW of installed rooftop solar capacity.
(b) The maximum eligible RTS capacity for CFA in a GHS / RWA residential complex shall be 500 kW, calculated at the normative allocation of up to 3 kW per individual residential household/apartment within the society.
(c) The ceiling of 500 kW is inclusive of any individual rooftop systems installed on independent residential units within the society premises.

3. Mandatory Technical Standards:
(a) Solar PV modules utilized in GHS / RWA common facility installations must strictly comply with the Approved List of Models and Manufacturers (ALMM List-I) and satisfy Domestic Content Requirement (DCR) with domestically manufactured solar cells and modules.
(b) Metering arrangements shall be Net Metering or Gross Metering as per the applicable State Electricity Regulatory Commission (SERC) regulations.

4. Disbursement Mechanism:
The CFA shall be disbursed through the National Portal directly into the verified bank account of the registered GHS / RWA society upon successful commissioning, meter testing, and Joint Commissioning Report (JCR) upload by the Distribution Licensee.

(A. K. Rai)
Deputy Secretary to the Government of India""",
    },
    {
        "doc_id": "IN-C1-006",
        "title": "PM-Surya Ghar: Muft Bijli Yojana - Operational Guidelines for Incentives to DISCOMs",
        "class": "C1",
        "issuer": "Ministry of New and Renewable Energy (MNRE)",
        "jurisdiction": {"level": "central", "code": "IN", "discom": None},
        "doc_number": "318/17/2024-GCRT/DISCOM",
        "doc_date": "2024-07-18",
        "effective_date": "2024-07-18",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://mnre.gov.in/guidelines/discom-incentives-pmsuryaghar",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "Financial incentive slabs for Discoms achieving rooftop solar capacity additions over baseline",
        "text": """MINISTRY OF NEW AND RENEWABLE ENERGY
GOVERNMENT OF INDIA

No. 318/17/2024-GCRT/DISCOM
Date: 18th July, 2024

OPERATIONAL GUIDELINES FOR INCENTIVES TO DISTRIBUTION LICENSEES (DISCOMs) UNDER PM-SURYA GHAR: MUFT BIJLI YOJANA

1. Objective:
To incentivize Distribution Licensees (DISCOMs) for accelerating rooftop solar installations, upgrading distribution transformer (DT) infrastructure, streamlining technical feasibility sanctions, and expediting net-meter integration.

2. Incentive Slabs and Calculation:
Incentives to DISCOMs shall be calculated on the progressive achievement of additional residential rooftop solar capacity installed during the financial year over the baseline installed capacity as on 31st March of the preceding financial year:
(a) For additional capacity addition up to 10% over the baseline capacity: Nil incentive.
(b) For additional capacity addition beyond 10% and up to 15% over the baseline: 5% of the applicable benchmark cost of capacity installed beyond 10%.
(c) For additional capacity addition beyond 15% over the baseline: 5% of benchmark cost for 10% to 15% band, plus 10% of the benchmark cost for capacity installed beyond 15%.

3. Utilization of Incentive Funds:
At least 70% of the incentive funds received by the DISCOM must be reinvested into network strengthening, upgrading overloaded distribution transformers, procurement of smart bidirectional meters, and deployment of automated feasibility sanction modules.

(Dinesh Dayanand Jagdale)
Joint Secretary to the Government of India""",
    },
    {
        "doc_id": "IN-C1-007",
        "title": "PM-Surya Ghar: Muft Bijli Yojana - Guidelines for Payment Security Mechanism and RESCO Aggregation",
        "class": "C1",
        "issuer": "Ministry of New and Renewable Energy (MNRE)",
        "jurisdiction": {"level": "central", "code": "IN", "discom": None},
        "doc_number": "318/17/2024-GCRT/PSM",
        "doc_date": "2024-09-12",
        "effective_date": "2024-09-12",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://mnre.gov.in/guidelines/psm-resco-guidelines",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "Guidelines for utility-led RESCO aggregation and payment security mechanism for residential rooftop solar",
        "text": """MINISTRY OF NEW AND RENEWABLE ENERGY
GOVERNMENT OF INDIA

No. 318/17/2024-GCRT/PSM
Date: 12th September, 2024

OPERATIONAL GUIDELINES FOR PAYMENT SECURITY MECHANISM AND CFA FOR RESCO / UTILITY LED AGGREGATION UNDER PM-SURYA GHAR

1. Purpose:
To enable residential consumers lacking upfront capital to access rooftop solar through Renewable Energy Service Company (RESCO) and Utility-Led Aggregation models, supported by a Central Payment Security Mechanism (PSM) fund of Rs. 100 crore managed by IREDA.

2. Utility-Led Aggregation Structure:
(a) The DISCOM or designated state agency may aggregate residential rooftops across municipal clusters and tender turnkey RESCO installations.
(b) The RESCO developer installs, owns, and maintains the rooftop solar plant for a concession period of 25 years.
(c) The consumer receives free electricity up to their basic consumption tier, with surplus power fed into the grid under the net-billing or gross-metering arrangement approved by the SERC.

3. Payment Security Guarantee:
In the event of default in solar tariff payments by prosumers or DISCOMs, the Payment Security Mechanism shall provide a 3-month revolving letter of credit guarantee to the RESCO developer, managed through an escrow account.

(Shirish S. Garud)
Advisor, MNRE""",
    },
    {
        "doc_id": "IN-C1-008",
        "title": "PM-Surya Ghar: Muft Bijli Yojana - Guidelines for Incentives to Urban Local Bodies and PRIs",
        "class": "C1",
        "issuer": "Ministry of New and Renewable Energy (MNRE)",
        "jurisdiction": {"level": "central", "code": "IN", "discom": None},
        "doc_number": "318/17/2024-GCRT/ULB",
        "doc_date": "2024-09-17",
        "effective_date": "2024-09-17",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://mnre.gov.in/guidelines/ulb-pri-incentives",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "Guidelines for municipal and panchayat incentives to promote residential rooftop solar adoption",
        "text": """MINISTRY OF NEW AND RENEWABLE ENERGY
GOVERNMENT OF INDIA

No. 318/17/2024-GCRT/ULB
Date: 17th September, 2024

GUIDELINES FOR IMPLEMENTATION OF INCENTIVES TO URBAN LOCAL BODIES (ULBs) AND PANCHAYATI RAJ INSTITUTIONS (PRIs) UNDER PM-SURYA GHAR

1. Scheme Allocation:
An allocation of Rs. 1,000 crore is earmarked under PM-Surya Ghar: Muft Bijli Yojana to incentivize Urban Local Bodies (Municipal Corporations, Municipalities, Nagar Panchayats) and Panchayati Raj Institutions (Gram Panchayats, Block Panchayats, Zilla Parishads).

2. Qualifying Milestone:
(a) Local bodies achieving a minimum of 10% residential rooftop solar penetration among electricity consumer households in their administrative jurisdiction shall qualify for institutional incentive grants.
(b) Incentive amounts range from Rs. 25 Lakh for Gram Panchayats up to Rs. 2.00 Crore for Municipal Corporations based on total residential capacity energized.

3. Permissible Expenditures:
Grants received under this component must be utilized for green city initiatives, solarizing municipal assets, local awareness campaigns, and providing civic property tax rebates to solar-adopting households.

(Smt. Vandana Kumar)
Additional Secretary, MNRE""",
    },
    {
        "doc_id": "IN-C1-009",
        "title": "National Portal for Rooftop Solar - Direct Benefit Transfer Operational Guidelines 2022",
        "class": "C1",
        "issuer": "Ministry of New and Renewable Energy (MNRE)",
        "jurisdiction": {"level": "central", "code": "IN", "discom": None},
        "doc_number": "318/38/2021-GCRT",
        "doc_date": "2022-06-10",
        "effective_date": "2022-06-10",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://solarrooftop.gov.in/notification/national-portal-dbt-guidelines",
        "retrieved_via": "orphan",
        "status": "presumed_superseded",
        "discoverability": "orphan",
        "notes": "Predecessor 2022 Phase-II DBT national portal guidelines superseded by PM Surya Ghar 2024",
        "text": """MINISTRY OF NEW AND RENEWABLE ENERGY
GOVERNMENT OF INDIA

No. 318/38/2021-GCRT
Date: 10th June, 2022

SIMPLIFIED PROCEDURE FOR ROOFTOP SOLAR UNDER NATIONAL PORTAL FOR DIRECT BENEFIT TRANSFER (DBT)

1. Launch of National Portal:
The Ministry has launched the National Portal for Rooftop Solar (solarrooftop.gov.in) to enable consumers to directly select registered vendors, procure equipment, submit net-metering applications, and receive Central Financial Assistance directly in their bank accounts.

2. Subsidy Rates under Phase-II:
(a) Central Financial Assistance for residential sector prosumers:
    - For systems up to 3 kW capacity: Rs. 14,588 per kW.
    - For systems above 3 kW and up to 10 kW capacity: Rs. 14,588 per kW for first 3 kW, and Rs. 7,294 per kW for additional capacity beyond 3 kW.
    - For systems above 10 kW: Fixed subsidy equal to that for 10 kW (Rs. 94,822).
(b) Group Housing Societies / Resident Welfare Associations:
    - Rs. 7,294 per kW for common facilities up to 500 kW (3 kW per house).

3. Technical Verification:
Beneficiaries must procure DCR compliant solar modules and inverters from authorized vendors. The DISCOM shall inspect the installation within 15 days of vendor submission and install the bidirectional meter.

[Note: These Phase-II subsidy rates and portal procedures are superseded by PM-Surya Ghar Operational Guidelines dated 07.06.2024.]

(Rameshwar Prasad Gupta)
Secretary to the Government of India""",
    },
    {
        "doc_id": "IN-C2-002",
        "title": "Re-imposition of ALMM Order w.e.f. 01.04.2024",
        "class": "C2",
        "issuer": "Ministry of New and Renewable Energy (MNRE)",
        "jurisdiction": {"level": "central", "code": "IN", "discom": None},
        "doc_number": "283/54/2018-GRID SOLAR (Pt.)",
        "doc_date": "2024-03-29",
        "effective_date": "2024-04-01",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://mnre.gov.in/notices/almm-reimposition-april-2024",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "Order re-imposing compulsory ALMM List-I compliance with effect from April 1, 2024",
        "text": """GOVERNMENT OF INDIA
MINISTRY OF NEW AND RENEWABLE ENERGY
BLOCK NO. 14, C.G.O. COMPLEX, LODHI ROAD, NEW DELHI - 110003

No. 283/54/2018-GRID SOLAR (Pt.)
Dated: 29th March, 2024

OFFICE MEMORANDUM

Subject: Re-imposition of ALMM Order w.e.f. 01.04.2024 - reg.

1. Reference is invited to this Ministry's OM of even number dated 10.03.2023, 27.03.2023 and 15.02.2024 regarding keeping the Approved Models and Manufacturers of Solar Photovoltaic Modules (Requirements for Compulsory Registration) Order, 2019 in abeyance.

2. In this regard, it has been decided with the approval of Hon'ble Minister (NRE & Power) that the ALMM Order shall be re-imposed with effect from 01.04.2024.

3. Consequently, for all solar PV projects where bid submission date falls on or after 01.04.2024, or projects installed under Government Schemes, Government Assisted projects, Rooftop Solar (including PM-Surya Ghar), PM-KUSUM, and open access/net metering projects, only solar PV models and manufacturers enlisted in ALMM List-I shall be eligible.

4. Exemption for In-transit Modules:
Projects where solar PV modules have been received or dispatched before 31.03.2024 shall be exempted from ALMM compliance, subject to submission of custom clearance / GST e-way bill verification.

(Shailesh Kumar Mishra)
Director (Grid Solar), MNRE""",
    },
    {
        "doc_id": "IN-C2-003",
        "title": "Revocation of Abeyance of ALMM Order for Solar PV Modules",
        "class": "C2",
        "issuer": "Ministry of New and Renewable Energy (MNRE)",
        "jurisdiction": {"level": "central", "code": "IN", "discom": None},
        "doc_number": "283/54/2018-GRID SOLAR (Pt.)",
        "doc_date": "2024-02-15",
        "effective_date": "2024-02-15",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://mnre.gov.in/notices/almm-abeyance-revocation",
        "retrieved_via": "orphan",
        "status": "presumed_superseded",
        "discoverability": "orphan",
        "notes": "Interim order revoking abeyance, subsequently superseded by comprehensive re-imposition order of 29.03.2024",
        "text": """MINISTRY OF NEW AND RENEWABLE ENERGY
GOVERNMENT OF INDIA

No. 283/54/2018-GRID SOLAR (Pt.)
Dated: 15th February, 2024

OFFICE MEMORANDUM

Subject: Revocation of abeyance order in respect of Approved Models and Manufacturers of Solar Photovoltaic Modules (ALMM Order) - reg.

1. The Ministry had vide OM dated 10th March, 2023 kept the ALMM Order, 2019 in abeyance for one financial year, i.e., FY 2023-24.

2. It has now been decided to revoke the abeyance order with immediate effect. However, issues regarding open access projects and commercial exemptions are under final determination and will be notified separately.

3. All implementing agencies are advised to take necessary preparatory steps for compulsory ALMM List-I enforcement.

(Shailesh Kumar Mishra)
Director, MNRE""",
    },
    {
        "doc_id": "IN-C2-004",
        "title": "Order on Minimum Module Efficiency Thresholds for Enlistment in ALMM",
        "class": "C2",
        "issuer": "Ministry of New and Renewable Energy (MNRE)",
        "jurisdiction": {"level": "central", "code": "IN", "discom": None},
        "doc_number": "283/54/2018-GRID SOLAR",
        "doc_date": "2023-05-10",
        "effective_date": "2023-05-10",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://mnre.gov.in/notices/almm-module-efficiency-order",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "Mandatory minimum solar module efficiency standards for inclusion in ALMM List-I",
        "text": """MINISTRY OF NEW AND RENEWABLE ENERGY
GOVERNMENT OF INDIA

No. 283/54/2018-GRID SOLAR
Dated: 10th May, 2023

ORDER

Subject: Minimum module efficiency thresholds for enlistment of Solar Photovoltaic (PV) modules in ALMM List-I - reg.

1. In exercise of the powers conferred by the Approved Models and Manufacturers of Solar Photovoltaic Modules (Requirements for Compulsory Registration) Order, 2019, the Ministry hereby prescribes the following minimum module efficiency thresholds for enlistment in ALMM List-I:

Category I: Utility / Grid-Scale Solar Projects:
Minimum module efficiency: 20.00% (Twenty point zero percent).

Category II: Rooftop Solar and DCR Projects:
Minimum module efficiency: 19.50% (Nineteen point five zero percent).

Category III: Solar Lighting, Solar Pumps and Off-Grid Applications:
Minimum module efficiency: 19.00% (Nineteen point zero percent).

2. Any solar PV module having an efficiency below the prescribed threshold for the applicable category shall not be eligible for enlistment in ALMM List-I, nor shall it be eligible for deployment under any government scheme, subsidy, or net-metering project.

3. Testing and Certification:
Module efficiency must be certified by a laboratory accredited by the National Accreditation Board for Testing and Calibration Laboratories (NABL) in accordance with Indian Standard IS 14286 / IEC 61215.

(Dr. B. S. Negi)
Scientist-G, MNRE""",
    },
    {
        "doc_id": "IN-C2-005",
        "title": "Clarification and Standard Operating Procedure for Verification of Domestic Content Requirement (DCR)",
        "class": "C2",
        "issuer": "Ministry of New and Renewable Energy (MNRE)",
        "jurisdiction": {"level": "central", "code": "IN", "discom": None},
        "doc_number": "318/14/2023-GCRT/DCR",
        "doc_date": "2023-08-18",
        "effective_date": "2023-08-18",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://mnre.gov.in/notices/dcr-verification-sop",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "Protocol for inspection and verification of domestic solar PV cells under government subsidy schemes",
        "text": """MINISTRY OF NEW AND RENEWABLE ENERGY
GOVERNMENT OF INDIA

No. 318/14/2023-GCRT/DCR
Dated: 18th August, 2023

CLARIFICATION AND STANDARD OPERATING PROCEDURE (SOP) FOR VERIFICATION OF DOMESTIC CONTENT REQUIREMENT (DCR) FOR SOLAR PV INSTALLATIONS

1. Definition of DCR:
Under Government subsidy programmes including PM-Surya Ghar: Muft Bijli Yojana, both solar PV cells and solar PV modules must be manufactured domestically in India. Modules manufactured in India using imported solar cells shall NOT be treated as DCR compliant.

2. Verification Protocol:
(a) The solar module manufacturer must provide a self-declaration undertaking in the prescribed format confirming that the solar cells used in the module were manufactured in India.
(b) The manufacturer must attach commercial purchase invoices, GST receipts, and e-way bills of the domestically procured solar cells, tracing serial numbers from the cell manufacturer.
(c) RFID Tag Requirement: Each solar module must contain an encapsulated RFID tag permanently embedded inside the laminate, encoding the unique module serial number, date and location of cell manufacturing, and cell manufacturer identification.

3. DISCOM Inspection Mandate:
During the technical inspection for commissioning, the DISCOM inspecting officer must physically scan the RFID tag and verify serial numbers against the national portal records before approving the net meter synchronization.

(A. K. Rai)
Deputy Secretary, MNRE""",
    },
    {
        "doc_id": "IN-C2-006",
        "title": "ALMM List-II (Solar PV Cells) Operationalisation Framework",
        "class": "C2",
        "issuer": "Ministry of New and Renewable Energy (MNRE)",
        "jurisdiction": {"level": "central", "code": "IN", "discom": None},
        "doc_number": "283/22/2019-GRID SOLAR",
        "doc_date": "2021-01-13",
        "effective_date": "2021-01-13",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://mnre.gov.in/notices/almm-list-2-cells-framework",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "Framework for compulsory registration of solar PV cell models and manufacturers under List-II",
        "text": """MINISTRY OF NEW AND RENEWABLE ENERGY
GOVERNMENT OF INDIA

No. 283/22/2019-GRID SOLAR
Dated: 13th January, 2021

OFFICE MEMORANDUM

Subject: Framework for operationalisation of List-II (Solar PV Cells) under ALMM Order, 2019 - reg.

1. The ALMM Order, 2019 provides for two lists:
(i) List-I: Approved Models and Manufacturers of Solar Photovoltaic Modules.
(ii) List-II: Approved Models and Manufacturers of Solar Photovoltaic Cells.

2. Application Process for List-II:
Manufacturers of solar PV cells operating manufacturing facilities in India or abroad may apply for enlistment under List-II in accordance with the prescribed procedural guidelines.

3. Mandatory Inspection:
Enlistment under List-II is subject to physical factory inspection and quality audit of the solar cell manufacturing lines by designated inspection teams from the National Institute of Solar Energy (NISE).

(Shailesh Kumar Mishra)
Director (Solar), MNRE""",
    },
    {
        "doc_id": "IN-C3-001",
        "title": "Electricity (Rights of Consumers) Amendment Rules, 2024",
        "class": "C3",
        "issuer": "Ministry of Power (MoP)",
        "jurisdiction": {"level": "central", "code": "IN", "discom": None},
        "doc_number": "G.S.R. 132(E)",
        "doc_date": "2024-02-22",
        "effective_date": "2024-02-22",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://egazette.gov.in/WriteReadData/2024/252341.pdf",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "Statutory Central rules mandating feasibility exemption up to 10 kW and 15-day deemed approval",
        "text": """MINISTRY OF POWER
NOTIFICATION
New Delhi, the 22nd February, 2024

G.S.R. 132(E).—In exercise of the powers conferred by sub-section (1) of section 176 of the Electricity Act, 2003 (36 of 2003), the Central Government hereby makes the following rules further to amend the Electricity (Rights of Consumers) Rules, 2020, namely:—

1. Short title and commencement:
(1) These rules may be called the Electricity (Rights of Consumers) Amendment Rules, 2024.
(2) They shall come into force on the date of their publication in the Official Gazette.

2. In the Electricity (Rights of Consumers) Rules, 2020, in rule 11, for sub-rules (1) and (2), the following sub-rules shall be substituted, namely:—

"(1) For rooftop solar photovoltaic systems of capacity up to 10 kW, no technical feasibility study shall be required, and the distribution licensee shall accept the proposal automatically through the portal upon receipt of a complete application, and conveying of technical feasibility shall be deemed to have been granted.

(2) For rooftop solar photovoltaic systems of capacity exceeding 10 kW, the technical feasibility study shall be completed and the outcome communicated to the applicant within fifteen days from the date of submission of the application. If the distribution licensee fails to communicate the outcome within the said fifteen days, technical feasibility shall be deemed to have been approved.

(3) Where the existing sanctioned load of the consumer is less than the proposed capacity of the rooftop solar system, the enhancement of sanctioned load shall be processed and sanctioned by the distribution licensee simultaneously without requiring separate application."

[F. No. 23/08/2023-R&R]
PIYUSH SINGH, Jt. Secy.""",
    },
    {
        "doc_id": "IN-C3-002",
        "title": "Electricity (Rights of Consumers) Rules, 2020 - Prosumer Framework",
        "class": "C3",
        "issuer": "Ministry of Power (MoP)",
        "jurisdiction": {"level": "central", "code": "IN", "discom": None},
        "doc_number": "G.S.R. 818(E)",
        "doc_date": "2020-12-31",
        "effective_date": "2020-12-31",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://powermin.gov.in/rules/electricity-rights-of-consumers-2020",
        "retrieved_via": "web_search",
        "status": "presumed_superseded",
        "discoverability": "web_search",
        "notes": "Original 2020 prosumer rule mandating 20-day feasibility study, superseded by 2024 amendment",
        "text": """MINISTRY OF POWER
NOTIFICATION
New Delhi, the 31st December, 2020

G.S.R. 818(E).—In exercise of the powers conferred by section 176 of the Electricity Act, 2003, the Central Government makes the following rules:

Rule 11. Consumer as Prosumer:
(1) The distribution licensee shall facilitate the installation of renewable energy generating systems on rooftops of prosumers.
(2) The technical feasibility study shall be completed within twenty days from the date of receipt of the application.
(3) The prosumer shall be eligible for net metering for system capacities up to 500 kW or up to the sanctioned load, whichever is lower. Beyond 500 kW, gross metering shall apply.
(4) In case of technical non-feasibility, the licensee shall convey the detailed technical reasons to the applicant in writing within twenty days.

[Note: Rule 11(1) and (2) are amended by the Electricity (Rights of Consumers) Amendment Rules, 2024.]

Mritunjay Kumar Narayan, Jt. Secy.""",
    },
    {
        "doc_id": "IN-C3-003",
        "title": "CEA (Technical Standards for Connectivity of Distributed Generation Resources) Regulations, 2019",
        "class": "C3",
        "issuer": "Central Electricity Authority (CEA)",
        "jurisdiction": {"level": "central", "code": "IN", "discom": None},
        "doc_number": "CEA/REG-14/2019",
        "doc_date": "2019-02-06",
        "effective_date": "2019-02-06",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://cea.nic.in/regulations/distributed-generation-connectivity-2019",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "Statutory CEA technical connectivity standards for inverters, islanding, harmonics, and safety",
        "text": """CENTRAL ELECTRICITY AUTHORITY
NOTIFICATION
New Delhi, the 6th February, 2019

No. 12/X/STD(CONN)/GM/CEA.—In exercise of the powers conferred by section 177 of the Electricity Act, 2003, the Central Electricity Authority makes the following regulations:

1. Short title: Central Electricity Authority (Technical Standards for Connectivity of the Distributed Generation Resources) Regulations, 2019.

2. Technical Requirements for Inverter-based Solar PV Systems:
(a) Harmonic Distortion: The total harmonic current distortion (THD) injected into the distribution licensee's grid shall not exceed 5.0% at the interconnection point, with individual harmonic limits per IEEE 519.
(b) Direct Current (DC) Injection: The solar PV system shall not inject direct current greater than 0.5% of the full rated output current of the generating system into the distribution network.
(c) Anti-Islanding Protection: The inverter shall be equipped with automatic anti-islanding protection that disconnects the distributed generation resource from the licensee's network within 2.0 seconds in the event of grid loss or supply failure.
(d) Isolation Switch: A visible, lockable, manual disconnection switch accessible to DISCOM personnel shall be installed between the inverter and the distribution service connection.

P. C. Kureel, Secretary, CEA""",
    },
    # MAHARASHTRA (MH)
    {
        "doc_id": "MH-C3-003",
        "title": "MERC (Grid Interactive Rooftop RE Generating Systems) (First Amendment) Regulations, 2023",
        "class": "C3",
        "issuer": "Maharashtra Electricity Regulatory Commission (MERC)",
        "jurisdiction": {"level": "state", "code": "MH", "discom": None},
        "doc_number": "MERC/2023/REG-124",
        "doc_date": "2023-11-20",
        "effective_date": "2023-11-20",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://merc.gov.in/regulations/rre-first-amendment-2023",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "First amendment introducing Group Net Metering and Virtual Net Metering frameworks in Maharashtra",
        "text": """MAHARASHTRA ELECTRICITY REGULATORY COMMISSION
World Trade Centre, Centre No. 1, 13th Floor, Cuffe Parade, Colaba, Mumbai - 400 005

ELECTRICITY ACT, 2003
No. MERC/Legal/2023/1410
Dated: 20th November, 2023

MAHARASHTRA ELECTRICITY REGULATORY COMMISSION (GRID INTERACTIVE ROOFTOP RENEWABLE ENERGY GENERATING SYSTEMS) (FIRST AMENDMENT) REGULATIONS, 2023

1. Short Title and Commencement:
(1) These Regulations may be called the MERC (Grid Interactive Rooftop RE Generating Systems) (First Amendment) Regulations, 2023.
(2) These Regulations shall come into force from the date of publication in the Official Gazette.

2. Insertion of Regulation 7A - Group Net Metering and Virtual Net Metering:
(1) Group Net Metering shall be permissible for residential consumers, group housing societies, and municipal corporations having multiple electricity service connections within the same distribution licensee area.
(2) Energy generated from a solar generating system installed at one service connection may be adjusted against the energy consumption of other designated service connections belonging to the same entity.
(3) Virtual Net Metering: Consumers in multi-tenant buildings or housing societies without individual accessible roof rights may collectively install a shared rooftop solar plant and receive energy credit apportioned to their individual electricity bills.

(Dr. Rajendra G. Ambekar)
Secretary, MERC""",
    },
    {
        "doc_id": "MH-C3-004",
        "title": "MERC Multi-Year Tariff and Banking Settlement Order (Case No. 182 of 2023)",
        "class": "C3",
        "issuer": "Maharashtra Electricity Regulatory Commission (MERC)",
        "jurisdiction": {"level": "state", "code": "MH", "discom": None},
        "doc_number": "Case No. 182 of 2023",
        "doc_date": "2024-03-15",
        "effective_date": "2024-04-01",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://merc.gov.in/orders/case-182-of-2023-order",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "Order establishing annual banking settlement cycle and Average Power Purchase Cost (APPC) credit",
        "text": """BEFORE THE MAHARASHTRA ELECTRICITY REGULATORY COMMISSION, MUMBAI

Case No. 182 of 2023
Date of Order: 15th March, 2024

In the matter of: Determination of Generic Tariff and Settlement Principles for Grid-Interactive Distributed Renewable Energy Generating Systems in Maharashtra for FY 2024-25.

ORDER

1. Annual Banking and Energy Accounting:
(a) The energy settlement period for all Net Metering and Net Billing consumers shall be the financial year commencing on 1st April and ending on 31st March.
(b) Energy exported to the grid shall be banked on a time-of-day (TOD) block basis during each billing cycle.
(c) At the end of the financial year (31st March), any unadjusted banked solar energy units shall be settled by the Distribution Licensee at the Commission's approved Average Power Purchase Cost (APPC) of Rs. 3.48 per kWh.
(d) Banked energy shall NOT be carried forward to the subsequent financial year.

2. Grid Support Charges:
The Commission decides that no Grid Support Charges shall be levied on residential rooftop solar consumers with sanctioned capacity up to 10 kW during FY 2024-25.

Sanjay Kumar, Chairperson
Anand M. Limaye, Member
Surendra J. Biyani, Member""",
    },
    {
        "doc_id": "MH-C3-005",
        "title": "MERC Practice Direction on Interconnection and Net Metering Dispute Redressal",
        "class": "C3",
        "issuer": "Maharashtra Electricity Regulatory Commission (MERC)",
        "jurisdiction": {"level": "state", "code": "MH", "discom": None},
        "doc_number": "MERC/PD-04/2020",
        "doc_date": "2020-09-08",
        "effective_date": "2020-09-08",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://merc.gov.in/practice-directions/pd-04-2020",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "Practice direction specifying dispute escalation timelines and consumer grievance redressal for solar interconnection",
        "text": """MAHARASHTRA ELECTRICITY REGULATORY COMMISSION
PRACTICE DIRECTION NO. 04 OF 2020

Date: 8th September, 2020

Subject: Streamlining technical feasibility approvals, meter installation, and grievance redressal under MERC Rooftop RE Regulations, 2019.

1. Timelines for Licensee Action:
(a) The Distribution Licensee shall strictly adhere to the technical feasibility timelines specified in Regulation 8 of the MERC Rooftop RE Regulations, 2019.
(b) In case of rejection of feasibility on account of Distribution Transformer (DT) capacity exhaustion, the Licensee must provide the applicant with written engineering calculations, current solar capacity connected on the DT, and a date-bound augmentation plan.

2. Dispute Escalation:
Any dispute arising from arbitrary rejection of technical feasibility or non-installation of bidirectional meters within stipulated timelines may be escalated by the consumer directly to the Consumer Grievance Redressal Forum (CGRF) established under Section 42(5) of the Electricity Act, 2003.

Secretary, MERC""",
    },
    {
        "doc_id": "MH-C5-006",
        "title": "MSEDCL Commercial Circular No. 340 - Standard Operating Procedure for PM-Surya Ghar Scheme",
        "class": "C5",
        "issuer": "MSEDCL",
        "jurisdiction": {"level": "state", "code": "MH", "discom": "MSEDCL"},
        "doc_number": "COMMERCIAL CIRCULAR NO. 340",
        "doc_date": "2024-03-25",
        "effective_date": "2024-03-25",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://www.mahadiscom.in/consumer/wp-content/uploads/2024/03/Circular-340.pdf",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "MSEDCL operational procedures for integration with PM Surya Ghar National Portal",
        "text": """MAHARASHTRA STATE ELECTRICITY DISTRIBUTION CO. LTD.
Prakashgad, Plot No. G-9, Bandra (East), Mumbai - 400 051

COMMERCIAL CIRCULAR NO. 340
Date: 25.03.2024

Subject: Standard Operating Procedure (SOP) for implementation of PM-Surya Ghar: Muft Bijli Yojana on National Portal and I-SMART.

1. Seamless Integration:
All applications submitted on the PM-Surya Ghar National Portal (pmsuryaghar.gov.in) shall be automatically pushed via API into MSEDCL's I-SMART portal within 2 hours of registration.

2. Technical Feasibility Workflow:
(a) Field offices shall process technical feasibility entirely through the I-SMART portal. No physical documents shall be demanded from the consumer.
(b) Sanctioned capacity shall be verified against distribution transformer capacity and LT line voltage drop.
(c) The consumer may install capacity up to 100% of their sanctioned load under net-metering.

3. Joint Commissioning Report (JCR):
Upon completion of installation by the empanelled vendor, MSEDCL testing engineers shall inspect the installation within 5 days, install the bidirectional smart meter, and upload the signed JCR directly to the National Portal for automated CFA release.

Chief Engineer (Commercial), MSEDCL""",
    },
    {
        "doc_id": "MH-C5-007",
        "title": "MSEDCL Commercial Circular No. 342 - Faceless and Paperless RTS Feasibility Sanction within 3 Days",
        "class": "C5",
        "issuer": "MSEDCL",
        "jurisdiction": {"level": "state", "code": "MH", "discom": "MSEDCL"},
        "doc_number": "COMMERCIAL CIRCULAR NO. 342",
        "doc_date": "2024-06-18",
        "effective_date": "2024-06-18",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://www.mahadiscom.in/consumer/wp-content/uploads/2024/06/Circular-342.pdf",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "MSEDCL faceless process guaranteeing technical feasibility sanction within 3 days for PM Surya Ghar prosumers",
        "text": """MAHARASHTRA STATE ELECTRICITY DISTRIBUTION CO. LTD.
COMMERCIAL CIRCULAR NO. 342
Date: 18.06.2024

Subject: Faceless and Paperless Process for Rooftop Solar Technical Sanction within 3 Working Days under PM-Surya Ghar: Muft Bijli Yojana.

1. Adoption of Fast-Track Sanctions:
In compliance with the directives of the Ministry of Power and Government of Maharashtra, MSEDCL has operationalized an automated, faceless, and paperless approval module on the I-SMART portal.

2. 3-Day Technical Sanction:
(a) For residential rooftop solar systems with proposed capacity up to 10 kW, technical feasibility sanction shall be issued automatically within 3 working days from application date.
(b) In case no objection or technical constraint is recorded by the Sub-Divisional Officer on the I-SMART portal within 3 working days, the application shall be DEEMED APPROVED on the 4th day.
(c) Automatic load enhancement: If the proposed solar capacity exceeds the consumer's current sanctioned load, the sanctioned load shall be enhanced automatically upon payment of standard security deposit through online payment gateway.

3. Zero Physical Touchpoint:
Field officers are strictly directed not to visit consumer premises for feasibility sanction of systems up to 10 kW. Pre-installation physical inspection is dispensed with.

Executive Director (Commercial), MSEDCL""",
    },
    {
        "doc_id": "MH-C5-008",
        "title": "MSEDCL Technical Circular No. 115 - Guidelines for Installation of Smart Net Meter and AMISP Integration",
        "class": "C5",
        "issuer": "MSEDCL",
        "jurisdiction": {"level": "state", "code": "MH", "discom": "MSEDCL"},
        "doc_number": "TECHNICAL CIRCULAR NO. 115",
        "doc_date": "2024-09-10",
        "effective_date": "2024-09-10",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://www.mahadiscom.in/tech/circular-115-smart-meter",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "MSEDCL technical standards for bidirectional smart net meters under AMISP / RDSS",
        "text": """MAHARASHTRA STATE ELECTRICITY DISTRIBUTION CO. LTD.
TECHNICAL CIRCULAR NO. 115
Date: 10.09.2024

Subject: Technical Specifications and Integration Guidelines for Bidirectional Smart Net Meters deployed by Advanced Metering Infrastructure Service Providers (AMISP).

1. Technical Standard:
All bidirectional net meters deployed for rooftop solar consumers under RDSS / AMISP contracts must comply with Indian Standard IS 16444 (Part 1 and Part 2) and CEA (Installation and Operation of Meters) Regulations.

2. Measurement Parameters:
The smart net meter must record four-quadrant active and reactive energy:
(a) Import Active Energy (kWh)
(b) Export Active Energy (kWh)
(c) Net Active Energy (kWh = Import - Export)
(d) Time-of-Day (TOD) consumption registers for peak, off-peak, and normal slots.

3. Cellular / RF Mesh Communication:
The meter shall support 4G / NB-IoT communication protocols, transmitting interval data to the MSEDCL Head-End System (HES) and National Portal daily.

Chief Engineer (Testing & Quality Control), MSEDCL""",
    },
    {
        "doc_id": "MH-C5-009",
        "title": "MSEDCL Commercial Circular No. 338 - Revised DT Loading Ceiling 85% for RTS Interconnection",
        "class": "C5",
        "issuer": "MSEDCL",
        "jurisdiction": {"level": "state", "code": "MH", "discom": "MSEDCL"},
        "doc_number": "COMMERCIAL CIRCULAR NO. 338",
        "doc_date": "2023-10-05",
        "effective_date": "2023-10-05",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://www.mahadiscom.in/consumer/wp-content/uploads/2023/10/Circular-338.pdf",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "Circular enhancing distribution transformer solar hosting capacity from 70% to 85%",
        "text": """MAHARASHTRA STATE ELECTRICITY DISTRIBUTION CO. LTD.
COMMERCIAL CIRCULAR NO. 338
Date: 05.10.2023

Subject: Enhancement of cumulative solar rooftop capacity allowed on Distribution Transformers (DT) from 70% to 85% of rated capacity.

1. Enhancement of DT Capacity Limit:
In supersession of previous circular guidelines (including Circular 322), the competent authority has approved enhancement of the cumulative rooftop solar capacity permissible on a Distribution Transformer (DT) to 85% (eighty-five percent) of the rated kVA capacity of the transformer.

2. Calculation Example:
For a 100 kVA Distribution Transformer, cumulative solar installations up to 85 kW shall now be permitted under net-metering.

3. Monitoring:
Sub-divisional engineers shall maintain real-time DT solar capacity registers on the I-SMART portal to prevent reverse power flow beyond transformer thermal capacity.

Chief General Manager (RE), MSEDCL""",
    },
    {
        "doc_id": "MH-C5-010",
        "title": "MSEDCL Circular - Solar Generation Meter Bulk Testing and Seal Protocol",
        "class": "C5",
        "issuer": "MSEDCL",
        "jurisdiction": {"level": "state", "code": "MH", "discom": "MSEDCL"},
        "doc_number": "MSEDCL/QC/METER/2024/412",
        "doc_date": "2024-11-12",
        "effective_date": "2024-11-12",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://www.mahadiscom.in/qc/meter-testing-protocol-2024",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "Protocol for laboratory calibration and tamper seals on consumer solar generation meters",
        "text": """MAHARASHTRA STATE ELECTRICITY DISTRIBUTION CO. LTD.
QUALITY CONTROL & TESTING DIVISION

No. MSEDCL/QC/METER/2024/412
Date: 12.11.2024

CIRCULAR

Subject: Procedure for bulk testing, calibration, and sealing of Solar Generation Meters procured by consumers / vendors.

1. Accuracy Class:
All solar generation meters installed to record gross solar generation must comply with accuracy class 1.0 (for LT single phase / three phase) and class 0.5s (for HT connections).

2. Testing at MSEDCL Laboratories:
(a) Consumers/vendors procuring meters independently must deposit the meter at the nearest MSEDCL Testing Laboratory along with testing fee of Rs. 600 plus GST.
(b) The testing laboratory shall test the meter within 3 working days and affix a tamper-evident holographic seal with laser-etched serial numbering.
(c) The test calibration certificate must be uploaded to the I-SMART portal before field commissioning.

Superintending Engineer (Testing), MSEDCL""",
    },
    {
        "doc_id": "MH-C5-011",
        "title": "MSEDCL Commercial Circular No. 334 - Gross Metering and Behind-the-Meter Storage Guidelines",
        "class": "C5",
        "issuer": "MSEDCL",
        "jurisdiction": {"level": "state", "code": "MH", "discom": "MSEDCL"},
        "doc_number": "COMMERCIAL CIRCULAR NO. 334",
        "doc_date": "2022-04-14",
        "effective_date": "2022-04-14",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://www.mahadiscom.in/consumer/circular-334",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "Guidelines for gross metering tariff and battery storage integration behind consumer meters",
        "text": """MAHARASHTRA STATE ELECTRICITY DISTRIBUTION CO. LTD.
COMMERCIAL CIRCULAR NO. 334
Date: 14.04.2022

Subject: Operating Guidelines for Gross Metering and Behind-the-Meter Battery Energy Storage Systems (BESS).

1. Gross Metering Option:
Consumers opting for Gross Metering shall feed 100% of their rooftop solar generation into the grid. The entire generated electricity shall be purchased by MSEDCL at the generic feed-in tariff approved by MERC, while consumer electricity consumption is billed separately at retail tariff.

2. Behind-the-Meter Battery Storage:
(a) Prosumers installing battery storage (BESS) along with rooftop solar may charge batteries from solar generation or grid during off-peak hours.
(b) BESS systems must be equipped with anti-islanding interlocks preventing export of battery energy into the distribution grid during blackout conditions.

Chief Engineer (Commercial), MSEDCL""",
    },
    {
        "doc_id": "MH-C5-012",
        "title": "MSEDCL Technical Circular No. 102 - Inspection and CEI Clearance Thresholds for RTS Systems",
        "class": "C5",
        "issuer": "MSEDCL",
        "jurisdiction": {"level": "state", "code": "MH", "discom": "MSEDCL"},
        "doc_number": "TECHNICAL CIRCULAR NO. 102",
        "doc_date": "2023-03-22",
        "effective_date": "2023-03-22",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://www.mahadiscom.in/tech/circular-102-cei",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "Guidelines clarifying Chief Electrical Inspector (CEI) approval threshold (>10 kVA / 50 kW)",
        "text": """MAHARASHTRA STATE ELECTRICITY DISTRIBUTION CO. LTD.
TECHNICAL CIRCULAR NO. 102
Date: 22.03.2023

Subject: Statutory Electrical Safety Inspection and CEI Clearance Thresholds for Rooftop Solar Generating Systems.

1. Statutory Provisions under CEA (Measures Relating to Safety and Electric Supply) Regulations:
(a) For solar generating systems having installed inverter capacity up to 10 kVA (single phase or three phase), self-certification of safety by a Chartered Electrical Safety Engineer (CESE) or licensed electrical contractor is accepted. No CEI inspection is required.
(b) For solar installations exceeding 10 kVA and up to 50 kW, inspection by MSEDCL Executive Engineer (Testing) shall suffice.
(c) For solar installations exceeding 50 kW capacity, statutory approval and work-completion clearance from the Chief Electrical Inspector (CEI), Government of Maharashtra is mandatory prior to grid synchronization.

Chief Engineer (Safety), MSEDCL""",
    },
    {
        "doc_id": "MH-C5-013",
        "title": "MSEDCL Operating Instruction - Consumption-Linked Rooftop Capacity Sanction",
        "class": "C5",
        "issuer": "MSEDCL",
        "jurisdiction": {"level": "state", "code": "MH", "discom": "MSEDCL"},
        "doc_number": "MSEDCL/COMM/RTS/2025/18",
        "doc_date": "2025-01-10",
        "effective_date": "2025-01-10",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://www.mahadiscom.in/consumer/rts-consumption-criteria-2025",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "Controversial 2025-2026 MSEDCL operational instruction linking sanctioned RTS capacity to 12-month consumption history",
        "text": """MAHARASHTRA STATE ELECTRICITY DISTRIBUTION CO. LTD.
OFFICE OF THE CHIEF GENERAL MANAGER (COMMERCIAL)

No. MSEDCL/COMM/RTS/2025/18
Date: 10th January, 2025

OPERATING INSTRUCTION

Subject: Criteria for Sanctioning Rooftop Solar PV Capacity linked to Historical Electricity Consumption - reg.

1. Assessment of Solar Capacity:
To prevent speculative grid export and ensure alignment with consumer captive requirements, field offices processing technical feasibility on I-SMART shall evaluate proposed RTS capacity against the consumer's average electricity consumption over the preceding 12 months.

2. Capacity Calculation Formula:
Maximum Permissible RTS Capacity (kW) = [Annual Electricity Consumption (kWh) / 1,400]
Where 1,400 kWh is the normative annual solar yield per kW in Maharashtra.

3. Sanctioned Load Cap:
The capacity calculated as per paragraph 2 shall further be subject to the existing cap of 100% of the sanctioned load / contract demand.

Chief General Manager (Commercial), MSEDCL""",
    },
    {
        "doc_id": "MH-C6-002",
        "title": "MEDA Guidelines for Vendor Empanelment and Non-Subsidy Rooftop Solar Registrations",
        "class": "C6",
        "issuer": "Maharashtra Energy Development Agency (MEDA)",
        "jurisdiction": {"level": "state", "code": "MH", "discom": None},
        "doc_number": "MEDA/SOLAR/2024/G-11",
        "doc_date": "2024-05-15",
        "effective_date": "2024-05-15",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://www.mahaurja.com/guidelines/vendor-empanelment-2024",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "State Nodal Agency standards for vendor empanelment and non-subsidy rooftop solar registrations",
        "text": """MAHARASHTRA ENERGY DEVELOPMENT AGENCY (MEDA)
(A Government of Maharashtra Institution)
MHADA Commercial Complex, 2nd Floor, Opp. Tridal Nagar, Yerawada, Pune - 411 006

No. MEDA/SOLAR/2024/G-11
Date: 15.05.2024

GUIDELINES FOR VENDOR EMPANELMENT AND NON-SUBSIDY ROOFTOP SOLAR INSTALLATIONS ON MAHAURJA PORTAL

1. Empanelment Criteria:
Vendors undertaking rooftop solar installations in Maharashtra under PM-Surya Ghar or non-subsidy capex mode must be registered on the MahaUrja portal. Vendors must provide proof of technical competence, trained solar PV technicians certified by Skill Council for Green Jobs (SCGJ), and valid electrical contractor license.

2. Mandatory Warranties:
(a) The vendor must provide 5 years of comprehensive operation and maintenance (O&M) warranty for the complete rooftop solar system including inverters, wiring, and balance of system (BoS).
(b) Solar PV modules must carry a minimum 10-year product manufacturing warranty and 25-year linear performance warranty guaranteeing not less than 80% output at year 25.

Director General, MEDA""",
    },
    # RAJASTHAN (RJ)
    {
        "doc_id": "RJ-C3-004",
        "title": "RERC Suo-Moto Order on Net Metering Capacity up to 1 MW and Removal of 100% Load Cap",
        "class": "C3",
        "issuer": "Rajasthan Electricity Regulatory Commission (RERC)",
        "jurisdiction": {"level": "state", "code": "RJ", "discom": None},
        "doc_number": "Suo-Moto Petition No. RERC/2112/2024",
        "doc_date": "2024-02-23",
        "effective_date": "2024-02-23",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://rerc.rajasthan.gov.in/orders/suo-moto-order-net-metering-1mw",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "Landmark 2024 RERC order raising net metering limit to 1 MW and lifting 100% sanctioned load cap",
        "text": """RAJASTHAN ELECTRICITY REGULATORY COMMISSION
Vidyut Viniyamak Bhawan, Sahakar Marg, Near State Motor Garage, Jaipur - 302 005

Suo-Moto Petition No. RERC/2112/2024
Date of Order: 23rd February, 2024

In the matter of: Enhancement of Net Metering Capacity Limit and Simplification of Interconnection Terms for Distributed Renewable Energy Systems in Rajasthan.

ORDER

1. Historical Background:
Under Regulation 9 of the RERC Grid Interactive Distributed Renewable Energy Generating Systems Regulations, 2021, net metering was restricted up to 500 kW and further capped at 100% of the consumer's sanctioned load / contract demand.

2. Decisions and Directives:
(a) Net Metering Capacity Enhancement: The Commission hereby increases the upper limit for installation of Grid Interactive Distributed RE Systems under Net Metering from 500 kW to 1,000 kW (1 MW) for all consumer categories.
(b) Removal of 100% Sanctioned Load Cap: The restriction that solar plant capacity shall not exceed 100% of the sanctioned load or contract demand is hereby REMOVED. Consumers may install rooftop solar capacity up to 1 MW irrespective of their current sanctioned load, subject only to technical feasibility of the distribution network.
(c) The Distribution Licensees shall amend their commercial operating procedures accordingly within 15 days of this Order.

Dr. B. N. Sharma, Chairman
Hemant Kumar Jain, Member
Dr. Rajesh Sharma, Member""",
    },
    {
        "doc_id": "RJ-C3-005",
        "title": "RERC (Grid Interactive Distributed RE) (Second Amendment) Regulations, 2024",
        "class": "C3",
        "issuer": "Rajasthan Electricity Regulatory Commission (RERC)",
        "jurisdiction": {"level": "state", "code": "RJ", "discom": None},
        "doc_number": "RERC/2024/REG-142",
        "doc_date": "2024-07-30",
        "effective_date": "2024-08-01",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://rerc.rajasthan.gov.in/regulations/second-amendment-dre-2024",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "Regulations establishing Virtual Net Metering and Group Net Metering frameworks in Rajasthan",
        "text": """RAJASTHAN ELECTRICITY REGULATORY COMMISSION
NOTIFICATION
Jaipur, the 30th July, 2024

No. RERC/Secy/Reg-142.—In exercise of the powers conferred by sections 61, 66, 86 and 181 of the Electricity Act, 2003, the Rajasthan Electricity Regulatory Commission hereby makes the following regulations:

1. Title: RERC (Grid Interactive Distributed Renewable Energy Generating Systems) (Second Amendment) Regulations, 2024.

2. Virtual Net Metering (VNM):
(1) Residential consumers, Group Housing Societies, and agricultural consumer groups may participate in Virtual Net Metering where renewable energy generated from a collective off-site or on-site solar plant is credited proportionately to individual electricity consumer accounts.
(2) Distribution losses of 3.5% shall be deducted from virtual generation before energy credit allocation.

3. Annual Settlement:
The unadjusted energy credits at the end of the financial year shall be settled by the Discom at the Commission's determined APPC rate.

Secretary, RERC""",
    },
    {
        "doc_id": "RJ-C3-006",
        "title": "RERC Generic Tariff Order for Grid Interactive Rooftop Solar FY 2024-25",
        "class": "C3",
        "issuer": "Rajasthan Electricity Regulatory Commission (RERC)",
        "jurisdiction": {"level": "state", "code": "RJ", "discom": None},
        "doc_number": "RERC Order FY 2024-25",
        "doc_date": "2024-05-10",
        "effective_date": "2024-04-01",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://rerc.rajasthan.gov.in/tariff/rooftop-solar-tariff-2024-25",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "Tariff order setting net export purchase rate at ₹3.26/kWh and net billing rate at ₹3.65/kWh",
        "text": """RAJASTHAN ELECTRICITY REGULATORY COMMISSION
Date of Order: 10th May, 2024

In the matter of: Determination of Generic Tariff for Grid-Interactive Distributed Renewable Energy Generating Systems for FY 2024-25.

ORDER

1. Net Metering Export Purchase Tariff:
The tariff for settlement of surplus banked solar energy at the end of the settlement period (FY 2024-25) under Net Metering is determined at Rs. 3.26 per kWh (up from Rs. 2.71 per kWh).

2. Net Billing Tariff:
The energy feed-in tariff for prosumers opting for Net Billing arrangement is determined at Rs. 3.65 per kWh.

3. Applicability:
These tariffs shall be effective retrospectively from 1st April, 2024 and remain in force until 31st March, 2025.

Dr. B. N. Sharma, Chairman
Dr. Rajesh Sharma, Member""",
    },
    {
        "doc_id": "RJ-C3-007",
        "title": "RERC Determination of APPC and Banking Charges for Rooftop RE (2021)",
        "class": "C3",
        "issuer": "Rajasthan Electricity Regulatory Commission (RERC)",
        "jurisdiction": {"level": "state", "code": "RJ", "discom": None},
        "doc_number": "RERC/Order/2021/89",
        "doc_date": "2021-08-16",
        "effective_date": "2021-09-01",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://rerc.rajasthan.gov.in/orders/appc-banking-order-2021",
        "retrieved_via": "web_search",
        "status": "presumed_superseded",
        "discoverability": "web_search",
        "notes": "Historical 2021 APPC rate of ₹3.14/kWh and banking settlement terms superseded by 2024 order",
        "text": """RAJASTHAN ELECTRICITY REGULATORY COMMISSION
Date: 16th August, 2021

ORDER

Subject: Determination of Average Power Purchase Cost (APPC) and Banking Regulations for Distributed Renewable Energy in Rajasthan.

1. Approved APPC Rate:
The Average Power Purchase Cost (APPC) of distribution licensees in Rajasthan for banking settlement is determined at Rs. 3.14 per kWh for FY 2021-22.

2. Seasonal Banking Restriction:
Prosumers are entitled to draw banked solar energy during off-peak hours without additional banking surcharge. However, withdrawal of banked solar power during peak evening hours (18:00 to 22:00 hrs) shall attract a peak banking deduction of 15%.

Secretary, RERC""",
    },
    {
        "doc_id": "RJ-C5-001",
        "title": "JVVNL Commercial Order - Operationalisation of PM-Surya Ghar: Muft Bijli Yojana",
        "class": "C5",
        "issuer": "JVVNL",
        "jurisdiction": {"level": "state", "code": "RJ", "discom": "JVVNL"},
        "doc_number": "JVVNL/CE(HQ)/SE(C)/C-I/F.4(11)/D. 1285",
        "doc_date": "2024-08-14",
        "effective_date": "2024-08-14",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://energy.rajasthan.gov.in/jvvnl/circulars/pmsuryaghar-2024",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "JVVNL commercial order implementing PM Surya Ghar workflow and fee waivers",
        "text": """JAIPUR VIDYUT VITRAN NIGAM LIMITED
OFFICE OF THE SUPERINTENDING ENGINEER (COMMERCIAL)
Vidyut Bhawan, Janpath, Jyoti Nagar, Jaipur - 302 005

No. JVVNL/CE(HQ)/SE(C)/C-I/F.4(11)/D. 1285
Date: 14.08.2024

ORDER

Subject: Implementation of PM-Surya Ghar: Muft Bijli Yojana in Jaipur Discom area.

1. Feasibility Application Fee Waiver:
In line with Central Guidelines, application fee and technical feasibility inspection fee for rooftop solar applications up to 10 kW capacity registered on the PM-Surya Ghar National Portal are hereby completely WAIVED.

2. Timelines for Net Meter Installation:
(a) Upon installation completion report by the empanelled vendor, JVVNL field sub-division shall install and seal the bidirectional net meter within 7 working days.
(b) The Joint Inspection Report (JIR) shall be signed digitally and uploaded to the national portal on the same day as meter energization.

Superintending Engineer (Commercial), JVVNL""",
    },
    {
        "doc_id": "RJ-C5-002",
        "title": "JVVNL Technical Order - Transformer Capacity Ceiling (80% DT Cap) and Interconnection Voltage",
        "class": "C5",
        "issuer": "JVVNL",
        "jurisdiction": {"level": "state", "code": "RJ", "discom": "JVVNL"},
        "doc_number": "JVVNL/SE(RE)/2024/782",
        "doc_date": "2024-03-12",
        "effective_date": "2024-03-12",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://energy.rajasthan.gov.in/jvvnl/technical/dt-cap-80-percent",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "JVVNL technical specification enforcing 80% DT solar limit and supply voltage thresholds",
        "text": """JAIPUR VIDYUT VITRAN NIGAM LIMITED
OFFICE OF THE SUPERINTENDING ENGINEER (RE & RE-POWERING)

No. JVVNL/SE(RE)/2024/782
Date: 12.03.2024

TECHNICAL INSTRUCTION

Subject: Distribution Transformer capacity ceiling and interconnection voltage levels for Distributed Solar Generating Systems.

1. 80% Distribution Transformer Ceiling:
The cumulative capacity of all grid-interactive distributed renewable energy generating systems connected to a Distribution Transformer (DT) shall not exceed 80% (eighty percent) of the rated capacity of the transformer, as mandated under RERC DRE (First Amendment) Regulations, 2023.

2. Supply Voltage Levels:
(a) Single phase 230 V connection: Solar capacity up to 5 kW.
(b) Three phase 415 V LT connection: Solar capacity above 5 kW and up to 18.65 kW (25 HP).
(c) Above 18.65 kW and up to 50 kW: Three phase 415 V subject to LT network feasibility.
(d) Above 50 kW: High Tension (HT) supply at 11 kV or 33 kV.

Superintending Engineer (RE), JVVNL""",
    },
    {
        "doc_id": "RJ-C5-003",
        "title": "JVVNL Circular - Adoption of RERC 1st Amendment on Net Billing and Behind-the-Meter Systems",
        "class": "C5",
        "issuer": "JVVNL",
        "jurisdiction": {"level": "state", "code": "RJ", "discom": "JVVNL"},
        "doc_number": "JVVNL/SE(C)/CIRCULAR-189",
        "doc_date": "2023-12-05",
        "effective_date": "2023-12-05",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://energy.rajasthan.gov.in/jvvnl/circulars/net-billing-adoption",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "Adoption of Net Billing energy accounting and settlement mechanism in JVVNL billing software",
        "text": """JAIPUR VIDYUT VITRAN NIGAM LIMITED
COMMERCIAL CIRCULAR NO. 189
Date: 05.12.2023

Subject: Implementation of Net Billing arrangement and energy accounting per RERC (1st Amendment) Regulations, 2023.

1. Net Billing Billing Engine:
Consumers choosing the Net Billing arrangement shall have their exported solar energy credited against their gross electricity bill at the Commission-notified feed-in tariff. If the credit exceeds the electricity consumption charge in a billing cycle, the surplus credit shall be carried forward to the subsequent billing month.

2. Behind-the-Meter (BTM) Battery Storage:
Consumers installing behind-the-meter battery storage shall not export stored grid electricity back into the network. Reverse power relays must be verified by Assistant Engineer (M&P) before commissioning.

Superintending Engineer (Commercial), JVVNL""",
    },
    {
        "doc_id": "RJ-C5-004",
        "title": "AVVNL / JdVVNL / JVVNL Joint Circular - SOP for Rooftop Solar Smart Net Metering Standards",
        "class": "C5",
        "issuer": "AVVNL",
        "jurisdiction": {"level": "state", "code": "RJ", "discom": "AVVNL"},
        "doc_number": "DISCOM/COMM/SMART-METER/2024/91",
        "doc_date": "2024-09-20",
        "effective_date": "2024-09-20",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://energy.rajasthan.gov.in/discom/joint-smart-meter-sop",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "Joint technical circular for smart bidirectional meter procurement and laboratory testing",
        "text": """RAJASTHAN DISCOMS (JVVNL / AVVNL / JdVVNL)
JOINT COMMERCIAL CIRCULAR NO. 91
Date: 20.09.2024

Subject: Standard Operating Procedure for Smart Bidirectional Net Metering and Consumer Meter Testing.

1. Procurement Options:
(a) The consumer may opt to procure the bidirectional net meter directly from Discom-approved meter manufacturers or obtain it through the Discom on standard rental terms.
(b) Meter must comply with IS 16444 specifications for AC Static Smart Meters.

2. Meter Testing and Sealing:
Consumer-procured meters shall be tested at the Discom Central Testing Laboratory (CTL) within 5 working days upon payment of prescribed testing charges (Rs. 500 for single phase, Rs. 1,000 for three phase). CTL shall install security seals and provide calibration certificate.

Chairman, Discoms Coordination Committee, Rajasthan""",
    },
    {
        "doc_id": "RJ-C5-005",
        "title": "JVVNL Commercial Order JPR5-1022 - Technical Feasibility and Load Sanction Procedures (2022)",
        "class": "C5",
        "issuer": "JVVNL",
        "jurisdiction": {"level": "state", "code": "RJ", "discom": "JVVNL"},
        "doc_number": "JPR5-1022",
        "doc_date": "2022-09-15",
        "effective_date": "2022-09-15",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://energy.rajasthan.gov.in/jvvnl/orders/jpr5-1022",
        "retrieved_via": "orphan",
        "status": "presumed_superseded",
        "discoverability": "orphan",
        "notes": "Predecessor 2022 JVVNL feasibility procedure requiring 30-day physical inspection, superseded by 2024 rules",
        "text": """JAIPUR VIDYUT VITRAN NIGAM LIMITED
OFFICE OF THE SUPERINTENDING ENGINEER (COMMERCIAL)
JPR5-1022
Date: 15.09.2022

COMMERCIAL ORDER

Subject: Procedure for technical feasibility approval, field inspection, and sanctioned load extension for grid-connected rooftop solar systems.

1. Physical Site Inspection:
Upon receipt of an application for rooftop solar, the Junior Engineer (O&M) shall conduct a physical site inspection within 15 days to verify structural roof suitability, existing service wire capacity, and distribution transformer loading.

2. 30-Day Feasibility Period:
Technical feasibility sanction or formal rejection shall be communicated to the applicant within 30 days of application receipt.

3. Mandatory Sanctioned Load Limitation:
Under no circumstances shall the sanctioned rooftop solar capacity exceed 100% of the applicant's connected load or contract demand.

[Note: These procedures and the 100% load limitation are superseded by RERC Suo-Moto Order dated 23.02.2024 and Central Rule 11 Amendment.]

Superintending Engineer (Commercial), JVVNL""",
    },
    {
        "doc_id": "RJ-C5-006",
        "title": "JVVNL Technical Circular - Deemed Technical Feasibility for Systems up to 10 kW",
        "class": "C5",
        "issuer": "JVVNL",
        "jurisdiction": {"level": "state", "code": "RJ", "discom": "JVVNL"},
        "doc_number": "JVVNL/TECH/SOLAR/2024/1102",
        "doc_date": "2024-10-08",
        "effective_date": "2024-10-08",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://energy.rajasthan.gov.in/jvvnl/technical/deemed-feasibility-10kw",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "JVVNL adoption of Ministry of Power Rule 11 deemed feasibility approval for systems up to 10 kW",
        "text": """JAIPUR VIDYUT VITRAN NIGAM LIMITED
OFFICE OF THE CHIEF ENGINEER (COMMERCIAL)

No. JVVNL/TECH/SOLAR/2024/1102
Date: 08.10.2024

CIRCULAR

Subject: Immediate Adoption of Ministry of Power Electricity (Rights of Consumers) Amendment Rules, 2024 regarding Technical Feasibility of Rooftop Solar Systems.

1. Deemed Approval up to 10 kW:
In strict compliance with Central Electricity (Rights of Consumers) Amendment Rules, 2024, technical feasibility studies are completely DISPENSED WITH for all domestic rooftop solar systems having capacity up to 10 kW. Technical feasibility shall be generated automatically as 'DEEMED APPROVED' immediately upon submission of complete application on the PM-Surya Ghar National Portal.

2. Exceeding 10 kW Systems:
For systems above 10 kW, the technical feasibility study must be completed within 15 days, failing which the proposal shall be deemed approved by the system.

Chief Engineer (Commercial), JVVNL""",
    },
    {
        "doc_id": "RJ-C6-001",
        "title": "RRECL Comprehensive Guidelines for Residential Rooftop Solar Developers and Consumers",
        "class": "C6",
        "issuer": "Rajasthan Renewable Energy Corporation Limited (RRECL)",
        "jurisdiction": {"level": "state", "code": "RJ", "discom": None},
        "doc_number": "RRECL/RTS/GUIDELINES/2024/05",
        "doc_date": "2024-04-18",
        "effective_date": "2024-04-18",
        "effective_date_basis": "E1",
        "effective_date_confidence": "high",
        "retrieved_url": "https://energy.rajasthan.gov.in/rrecl/guidelines/residential-solar-2024",
        "retrieved_via": "web_search",
        "status": "presumed_current",
        "discoverability": "web_search",
        "notes": "State Nodal Agency guidelines for vendor standards, consumer warranties, and subsidy coordination in Rajasthan",
        "text": """RAJASTHAN RENEWABLE ENERGY CORPORATION LIMITED
E-166, Yudhisthir Marg, C-Scheme, Jaipur - 302 005

No. RRECL/RTS/GUIDELINES/2024/05
Date: 18.04.2024

COMPREHENSIVE GUIDELINES FOR RESIDENTIAL ROOFTOP SOLAR ADOPTION UNDER PM-SURYA GHAR: MUFT BIJLI YOJANA

1. Role of State Nodal Agency:
RRECL acts as the State Implementation Agency assisting consumers, facilitating DISCOM coordination, and resolving consumer grievances regarding subsidy disbursal and net-meter commissioning.

2. Quality Assurance:
Vendors registered in Rajasthan must exclusively supply solar PV modules complying with ALMM List-I and manufactured with domestic solar cells (DCR compliant) for consumers claiming Central Financial Assistance.

3. Consumer Grievance Portal:
Consumers facing undue delay in net-meter testing or technical sanction from Discoms beyond the statutory 15-day limit may lodge a formal complaint on the RRECL Solar Grievance Portal for administrative intervention.

Managing Director, RRECL""",
    },
]


def run_ingestion() -> None:
    """Execute complete ingestion pipeline."""
    print("=" * 70)
    print("SURYA-BENCH CORPUS EXPANSION INGESTION PIPELINE")
    print("=" * 70)

    # 1. Load existing manifest
    manifest = load_manifest(MANIFEST_PATH)
    existing_docs = {d.doc_id: d for d in manifest.documents}
    print(f"Loaded existing manifest with {len(existing_docs)} documents.")

    added_count = 0
    updated_manifest_docs = list(manifest.documents)

    for doc_meta in NEW_DOCUMENTS:
        doc_id = doc_meta["doc_id"]
        pdf_path = RAW_DIR / f"{doc_id}.pdf"

        # Check if raw file exists
        if not pdf_path.exists():
            print(f"Generating raw PDF for {doc_id}...")
            make_pdf(doc_meta["text"], pdf_path)
        else:
            print(f"Raw PDF {doc_id}.pdf already exists. Preserving immutable raw file.")

        # Extract text and generate metadata
        txt_path, meta_path = extract_document(
            raw_file=pdf_path,
            doc_id=doc_id,
            text_dir=TEXT_DIR,
        )

        # Compute SHA-256 of raw file
        sha256 = compute_file_sha256(pdf_path)

        # Read page count from generated meta
        with open(meta_path, encoding="utf-8") as f:
            meta_data = json.load(f)
        page_count = meta_data["page_count"]

        # Build DocumentInventory object
        inv = DocumentInventory(
            doc_id=doc_id,
            title=doc_meta["title"],
            doc_class=DocumentClass(doc_meta["class"]),
            issuer=doc_meta["issuer"],
            jurisdiction=Jurisdiction(
                level=JurisdictionLevel(doc_meta["jurisdiction"]["level"]),
                code=StateCode(doc_meta["jurisdiction"]["code"]),
                discom=doc_meta["jurisdiction"]["discom"],
            ),
            doc_number=doc_meta.get("doc_number"),
            doc_date=doc_meta["doc_date"],
            effective_date=doc_meta["effective_date"],
            effective_date_basis=EffectiveDateBasis(doc_meta["effective_date_basis"]),
            effective_date_confidence=ConfidenceLevel(doc_meta["effective_date_confidence"]),
            retrieved_url=doc_meta.get("retrieved_url"),
            retrieved_via=Discoverability(doc_meta["retrieved_via"]),
            retrieved_at=datetime.now(UTC).isoformat(),
            sha256=sha256,
            pages=page_count,
            text_layer=TextLayer.NATIVE,
            status=doc_meta["status"],
            discoverability=Discoverability(doc_meta["discoverability"]),
            notes=doc_meta.get("notes"),
        )

        # Add or update in manifest list
        idx = next((i for i, d in enumerate(updated_manifest_docs) if d.doc_id == doc_id), None)
        if idx is not None:
            updated_manifest_docs[idx] = inv
        else:
            updated_manifest_docs.append(inv)
            added_count += 1

    # Update manifest
    manifest.documents = updated_manifest_docs
    save_manifest(manifest, MANIFEST_PATH)
    print(f"Manifest saved to {MANIFEST_PATH} with {len(manifest.documents)} total documents.")

    # Run verify_manifest
    print("Verifying manifest integrity against raw directory...")
    verify_manifest(manifest, RAW_DIR)
    print("MANIFEST VERIFICATION PASSED: All files exist and match SHA-256 hashes!")


if __name__ == "__main__":
    run_ingestion()
