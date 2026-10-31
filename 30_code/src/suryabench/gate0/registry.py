"""Frozen Gate 0 query registry implementation and verification (protocol §8)."""

import hashlib
from pathlib import Path

from suryabench.core.enums import SubjectTag
from suryabench.core.exceptions import SuryaBenchError
from suryabench.gate0.schema import ExpectedNodeBasis, Gate0Query, Gate0QueryRegistry, QueryBand

FROZEN_GATE0_QUERIES: list[Gate0Query] = [
    # Band Q-A: Currency-sensitive (n=6)
    Gate0Query(
        query_id="Q-A-01",
        band=QueryBand.Q_A,
        text="What is the central government subsidy amount for a 3 kW residential rooftop solar installation?",
        subject=SubjectTag.SUBSIDY_CFA_CENTRAL_RESIDENTIAL,
        intended_jurisdiction="IN",
        jurisdiction_stated=True,
        expected_governing_nodes=["IN-C1-001#cl-4.1"],
        expected_node_basis=ExpectedNodeBasis.EXPLICIT_APPLICABILITY,
        known_superseded_nodes=["IN-C1-002#cl-2"],
    ),
    Gate0Query(
        query_id="Q-A-02",
        band=QueryBand.Q_A,
        text="Can a consumer in Rajasthan install a 5 kW net-metered rooftop solar system on a 5 kW sanctioned load connection?",
        subject=SubjectTag.NET_METERING_CAPACITY_CAP,
        intended_jurisdiction="RJ",
        jurisdiction_stated=True,
        expected_governing_nodes=["RJ-C3-002#cl-7.2"],
        expected_node_basis=ExpectedNodeBasis.EXPLICIT_APPLICABILITY,
        known_superseded_nodes=["RJ-C3-001#cl-3.1"],
    ),
    Gate0Query(
        query_id="Q-A-03",
        band=QueryBand.Q_A,
        text="What is the maximum cumulative solar capacity permitted on a 100 kVA distribution transformer in Jaipur?",
        subject=SubjectTag.DT_TRANSFORMER_CAPACITY_LIMIT,
        intended_jurisdiction="RJ",
        jurisdiction_stated=True,
        expected_governing_nodes=["RJ-C3-003#cl-2"],
        expected_node_basis=ExpectedNodeBasis.EXPLICIT_SUPERSESSION,
        known_superseded_nodes=["RJ-C3-002#cl-6.1"],
    ),
    Gate0Query(
        query_id="Q-A-04",
        band=QueryBand.Q_A,
        text="Can a residential rooftop solar consumer in Maharashtra also take open access power for their home?",
        subject=SubjectTag.INTERCONNECTION_FEASIBILITY_STAGE,
        intended_jurisdiction="MH",
        jurisdiction_stated=True,
        expected_governing_nodes=["MH-C5-001#cl-feasibility"],
        expected_node_basis=ExpectedNodeBasis.EXPLICIT_SUPERSESSION,
        known_superseded_nodes=["MH-C5-004#cl-open-access"],
    ),
    Gate0Query(
        query_id="Q-A-05",
        band=QueryBand.Q_A,
        text="How much CFA subsidy per kW does MNRE give for the first 2 kW of residential solar?",
        subject=SubjectTag.SUBSIDY_CFA_CENTRAL_RESIDENTIAL,
        intended_jurisdiction="IN",
        jurisdiction_stated=True,
        expected_governing_nodes=["IN-C1-001#cl-4.1"],
        expected_node_basis=ExpectedNodeBasis.EXPLICIT_APPLICABILITY,
        known_superseded_nodes=["IN-C1-002#cl-2"],
    ),
    Gate0Query(
        query_id="Q-A-06",
        band=QueryBand.Q_A,
        text="What is the maximum rooftop solar capacity allowed for net metering against an 8 kW sanctioned load in Jodhpur?",
        subject=SubjectTag.NET_METERING_CAPACITY_CAP,
        intended_jurisdiction="RJ",
        jurisdiction_stated=True,
        expected_governing_nodes=["RJ-C3-002#cl-7.2"],
        expected_node_basis=ExpectedNodeBasis.EXPLICIT_APPLICABILITY,
        known_superseded_nodes=["RJ-C3-001#cl-3.1"],
    ),
    # Band Q-B: Jurisdiction-sensitive (n=5, >=3 omit state)
    Gate0Query(
        query_id="Q-B-01",
        band=QueryBand.Q_B,
        text="What is the transformer capacity limit for connecting grid interactive rooftop solar?",
        subject=SubjectTag.DT_TRANSFORMER_CAPACITY_LIMIT,
        intended_jurisdiction="MH",
        jurisdiction_stated=False,
        expected_governing_nodes=["MH-C3-001#cl-5.2"],
        expected_node_basis=ExpectedNodeBasis.EXPLICIT_APPLICABILITY,
        known_superseded_nodes=[],
    ),
    Gate0Query(
        query_id="Q-B-02",
        band=QueryBand.Q_B,
        text="What percentage of sanctioned load is allowed for residential net metering?",
        subject=SubjectTag.NET_METERING_CAPACITY_CAP,
        intended_jurisdiction="RJ",
        jurisdiction_stated=False,
        expected_governing_nodes=["RJ-C3-002#cl-7.2"],
        expected_node_basis=ExpectedNodeBasis.EXPLICIT_APPLICABILITY,
        known_superseded_nodes=["RJ-C3-001#cl-3.1"],
    ),
    Gate0Query(
        query_id="Q-B-03",
        band=QueryBand.Q_B,
        text="Are residents in an apartment building eligible for virtual net metering?",
        subject=SubjectTag.NET_METERING_CAPACITY_CAP,
        intended_jurisdiction="MH",
        jurisdiction_stated=False,
        expected_governing_nodes=["MH-C3-002#cl-2"],
        expected_node_basis=ExpectedNodeBasis.EXPLICIT_APPLICABILITY,
        known_superseded_nodes=[],
    ),
    Gate0Query(
        query_id="Q-B-04",
        band=QueryBand.Q_B,
        text="What is the minimum plant capacity for rooftop solar grid connectivity in Maharashtra?",
        subject=SubjectTag.NET_METERING_CAPACITY_CAP,
        intended_jurisdiction="MH",
        jurisdiction_stated=True,
        expected_governing_nodes=["MH-C3-001#cl-6.2"],
        expected_node_basis=ExpectedNodeBasis.EXPLICIT_APPLICABILITY,
        known_superseded_nodes=[],
    ),
    Gate0Query(
        query_id="Q-B-05",
        band=QueryBand.Q_B,
        text="Can an agricultural consumer connect rooftop solar under net metering in Rajasthan?",
        subject=SubjectTag.NET_METERING_CAPACITY_CAP,
        intended_jurisdiction="RJ",
        jurisdiction_stated=True,
        expected_governing_nodes=["RJ-C3-002#cl-7.2"],
        expected_node_basis=ExpectedNodeBasis.EXPLICIT_APPLICABILITY,
        known_superseded_nodes=[],
    ),
    # Band Q-C: Structure-sensitive (n=4)
    Gate0Query(
        query_id="Q-C-01",
        band=QueryBand.Q_C,
        text="What is the subsidy amount in rupees for 1 kW, 2 kW, and 3 kW residential rooftop solar?",
        subject=SubjectTag.SUBSIDY_CFA_CENTRAL_RESIDENTIAL,
        intended_jurisdiction="IN",
        jurisdiction_stated=True,
        expected_governing_nodes=["IN-C1-001#cl-4.1"],
        expected_node_basis=ExpectedNodeBasis.EXPLICIT_APPLICABILITY,
        known_superseded_nodes=["IN-C1-002#cl-2"],
    ),
    Gate0Query(
        query_id="Q-C-02",
        band=QueryBand.Q_C,
        text="What are the specific technical definitions and responsibilities of the Lead Person for shared rooftop solar?",
        subject=SubjectTag.NET_METERING_CAPACITY_CAP,
        intended_jurisdiction="MH",
        jurisdiction_stated=True,
        expected_governing_nodes=["MH-C3-002#cl-2"],
        expected_node_basis=ExpectedNodeBasis.EXPLICIT_APPLICABILITY,
        known_superseded_nodes=[],
    ),
    Gate0Query(
        query_id="Q-C-03",
        band=QueryBand.Q_C,
        text="What is the allowable solar capacity rule for high tension HT consumers with private distribution transformers?",
        subject=SubjectTag.DT_TRANSFORMER_CAPACITY_LIMIT,
        intended_jurisdiction="RJ",
        jurisdiction_stated=True,
        expected_governing_nodes=["RJ-C3-003#cl-2"],
        expected_node_basis=ExpectedNodeBasis.EXPLICIT_SUPERSESSION,
        known_superseded_nodes=[],
    ),
    Gate0Query(
        query_id="Q-C-04",
        band=QueryBand.Q_C,
        text="What are the safety and separate earthing requirements mandated for solar rooftop grid connectivity?",
        subject=SubjectTag.GRID_INVERTER_SAFETY_STANDARD,
        intended_jurisdiction="MH",
        jurisdiction_stated=True,
        expected_governing_nodes=["MH-C5-003#cl-safety"],
        expected_node_basis=ExpectedNodeBasis.AUTHORITY_RESOLUTION,
        known_superseded_nodes=[],
    ),
    # Band Q-D: Multi-document (n=3)
    Gate0Query(
        query_id="Q-D-01",
        band=QueryBand.Q_D,
        text="Can I claim PM Surya Ghar central subsidy if I install a 4 kW net-metered system in Pune with imported solar panels?",
        subject=SubjectTag.DCR_CELL_MODULE_REQUIREMENT,
        intended_jurisdiction="IN",
        jurisdiction_stated=True,
        expected_governing_nodes=["IN-C1-001#cl-5.1m", "MH-C3-001#cl-6.2"],
        expected_node_basis=ExpectedNodeBasis.EXPLICIT_APPLICABILITY,
        known_superseded_nodes=[],
    ),
    Gate0Query(
        query_id="Q-D-02",
        band=QueryBand.Q_D,
        text="To get central CFA for an individual home in Jaipur, which national portal and state Discom portal must be used?",
        subject=SubjectTag.SUBSIDY_DISBURSEMENT_PROCESS,
        intended_jurisdiction="IN",
        jurisdiction_stated=True,
        expected_governing_nodes=["IN-C1-001#cl-4.1", "RJ-C3-002#cl-7.2"],
        expected_node_basis=ExpectedNodeBasis.EXPLICIT_APPLICABILITY,
        known_superseded_nodes=[],
    ),
    Gate0Query(
        query_id="Q-D-03",
        band=QueryBand.Q_D,
        text="If an apartment society in Mumbai sets up 20 kW solar on shared roof under virtual net metering, are they eligible for central CFA subsidy?",
        subject=SubjectTag.SUBSIDY_CFA_GROUP_HOUSING,
        intended_jurisdiction="IN",
        jurisdiction_stated=True,
        expected_governing_nodes=["IN-C1-001#cl-4.1", "MH-C3-002#cl-2"],
        expected_node_basis=ExpectedNodeBasis.EXPLICIT_APPLICABILITY,
        known_superseded_nodes=[],
    ),
    # Band Q-E: Control (n=2)
    Gate0Query(
        query_id="Q-E-01",
        band=QueryBand.Q_E,
        text="Under PM Surya Ghar Muft Bijli Yojana, what is the maximum total Central Financial Assistance cap for any individual residential household?",
        subject=SubjectTag.SUBSIDY_CFA_CENTRAL_RESIDENTIAL,
        intended_jurisdiction="IN",
        jurisdiction_stated=True,
        expected_governing_nodes=["IN-C1-001#cl-4.1"],
        expected_node_basis=ExpectedNodeBasis.EXPLICIT_APPLICABILITY,
        known_superseded_nodes=[],
    ),
    Gate0Query(
        query_id="Q-E-02",
        band=QueryBand.Q_E,
        text="What is the title and notification number of the MERC Second Amendment Regulations issued in August 2024?",
        subject=SubjectTag.NET_METERING_CAPACITY_CAP,
        intended_jurisdiction="MH",
        jurisdiction_stated=True,
        expected_governing_nodes=["MH-C3-002#cl-2"],
        expected_node_basis=ExpectedNodeBasis.EXPLICIT_APPLICABILITY,
        known_superseded_nodes=[],
    ),
]


def validate_query_registry(registry: Gate0QueryRegistry) -> None:
    """Validate frozen query registry against protocol §8 invariants."""
    queries = registry.queries
    if len(queries) != 20:
        raise SuryaBenchError(
            f"Gate 0 registry must contain exactly 20 queries, found {len(queries)}"
        )

    band_counts: dict[QueryBand, int] = {}
    for q in queries:
        band_counts[q.band] = band_counts.get(q.band, 0) + 1

    expected_bands = {
        QueryBand.Q_A: 6,
        QueryBand.Q_B: 5,
        QueryBand.Q_C: 4,
        QueryBand.Q_D: 3,
        QueryBand.Q_E: 2,
    }

    for band, expected in expected_bands.items():
        actual = band_counts.get(band, 0)
        if actual != expected:
            raise SuryaBenchError(f"Band {band.value} expected {expected} queries, got {actual}")

    # Check Q-B state omission constraint: >=3 must omit state
    qb_omitted = [q for q in queries if q.band == QueryBand.Q_B and not q.jurisdiction_stated]
    if len(qb_omitted) < 3:
        raise SuryaBenchError(
            f"Band Q-B requires >=3 queries omitting jurisdiction, found {len(qb_omitted)}"
        )


def compute_registry_sha256(registry: Gate0QueryRegistry) -> str:
    """Compute deterministic SHA-256 hash of the query registry."""
    dumped = registry.model_dump_json(indent=2)
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


def get_default_frozen_registry() -> Gate0QueryRegistry:
    """Build and validate the default frozen Gate 0 query registry."""
    reg = Gate0QueryRegistry(
        frozen_at="2026-09-21T16:05:00Z",
        queries=FROZEN_GATE0_QUERIES,
    )
    validate_query_registry(reg)
    return reg


def save_query_registry(registry: Gate0QueryRegistry, output_path: Path) -> str:
    """Save registry to JSON and return its SHA-256 digest."""
    validate_query_registry(registry)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = registry.model_dump_json(indent=2) + "\n"
    output_path.write_text(content, encoding="utf-8", newline="\n")
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    output_path.with_name("GATE0_QUERIES.sha256").write_text(
        f"{digest}  {output_path.name}\n", encoding="utf-8", newline="\n"
    )
    return digest
