"""Document inventory management and composition floor validation."""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from suryabench.core.enums import Discoverability, StateCode
from suryabench.corpus.manifest import load_manifest, save_manifest
from suryabench.corpus.schema import CorpusManifest, DocumentInventory


@dataclass
class FloorStatus:
    """Status of an individual composition floor (MC-1 through MC-5)."""

    floor_id: str
    description: str
    target: int
    actual: int
    passed: bool
    details: str


@dataclass
class CompositionReport:
    """Consolidated report across all composition floors."""

    passed: bool
    floors: dict[str, FloorStatus]
    summary: str


def add_document_to_manifest(manifest_path: Path, doc: DocumentInventory) -> CorpusManifest:
    """Add or update a document inventory row in MANIFEST.json and update MANIFEST.sha256."""
    if manifest_path.exists():
        manifest = load_manifest(manifest_path)
    else:
        manifest = CorpusManifest(
            corpus_version="SuryaBench-Corpus-2026.11",
            created_at=datetime.now(UTC).isoformat(),
            documents=[],
        )

    # Check for duplicate doc_id
    existing_idx = next(
        (i for i, d in enumerate(manifest.documents) if d.doc_id == doc.doc_id),
        None,
    )
    if existing_idx is not None:
        manifest.documents[existing_idx] = doc
    else:
        manifest.documents.append(doc)

    save_manifest(manifest, manifest_path)
    return manifest


def check_composition_floors(
    manifest: CorpusManifest,
    supersession_pair_count: int = 0,
    live_superseded_pair_count: int = 0,
    states_in_supersession: set[StateCode] | None = None,
) -> CompositionReport:
    """Evaluate corpus composition against mandatory floors MC-1 through MC-5 (protocol §2).

    MC-1: >=6 supersession or amendment pairs.
    MC-2: >=3 pairs where superseded member remains live and reachable.
    MC-3: >=4 documents with discoverability of web_search or orphan.
    MC-4: >=2 documents with effective_date: UNKNOWN.
    MC-5: Both states (MH and RJ) represented in MC-1.
    """
    states_represented = states_in_supersession or set()

    # MC-3: Count web_search or orphan discoverability
    mc3_docs = [
        d
        for d in manifest.documents
        if d.discoverability in {Discoverability.WEB_SEARCH, Discoverability.ORPHAN}
    ]
    mc3_count = len(mc3_docs)

    # MC-4: Count unknown effective dates
    mc4_docs = [d for d in manifest.documents if d.effective_date == "UNKNOWN"]
    mc4_count = len(mc4_docs)

    floors = {
        "MC-1": FloorStatus(
            floor_id="MC-1",
            description=">=6 supersession or amendment pairs",
            target=6,
            actual=supersession_pair_count,
            passed=supersession_pair_count >= 6,
            details=f"{supersession_pair_count} / 6 pairs documented",
        ),
        "MC-2": FloorStatus(
            floor_id="MC-2",
            description=">=3 pairs where superseded doc is live/reachable",
            target=3,
            actual=live_superseded_pair_count,
            passed=live_superseded_pair_count >= 3,
            details=f"{live_superseded_pair_count} / 3 live superseded pairs",
        ),
        "MC-3": FloorStatus(
            floor_id="MC-3",
            description=">=4 documents with discoverability of web_search or orphan",
            target=4,
            actual=mc3_count,
            passed=mc3_count >= 4,
            details=f"{mc3_count} / 4 web_search/orphan docs ({[d.doc_id for d in mc3_docs]})",
        ),
        "MC-4": FloorStatus(
            floor_id="MC-4",
            description=">=2 documents with effective_date: UNKNOWN",
            target=2,
            actual=mc4_count,
            passed=mc4_count >= 2,
            details=f"{mc4_count} / 2 UNKNOWN dated docs ({[d.doc_id for d in mc4_docs]})",
        ),
        "MC-5": FloorStatus(
            floor_id="MC-5",
            description="Both states (MH and RJ) represented in supersession pairs",
            target=2,
            actual=len({StateCode.MH, StateCode.RJ}.intersection(states_represented)),
            passed={StateCode.MH, StateCode.RJ}.issubset(states_represented),
            details=f"States with supersession pairs: {[s.value for s in states_represented]}",
        ),
    }

    all_passed = all(f.passed for f in floors.values())
    summary_lines = [
        f"[{'PASS' if f.passed else 'FAIL'}] {f.floor_id}: {f.description} ({f.details})"
        for f in floors.values()
    ]
    summary = "\n".join(summary_lines)

    return CompositionReport(passed=all_passed, floors=floors, summary=summary)
