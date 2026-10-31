"""Unit tests for corpus ingestion: fetch, extract, inventory, and composition floors."""

import tempfile
from pathlib import Path

import pytest

from suryabench.core.enums import (
    ConfidenceLevel,
    Discoverability,
    DocumentClass,
    EffectiveDateBasis,
    JurisdictionLevel,
    StateCode,
    TextLayer,
)
from suryabench.core.exceptions import SuryaBenchError
from suryabench.corpus.extract import extract_document
from suryabench.corpus.fetch import fetch_document
from suryabench.corpus.inventory import add_document_to_manifest, check_composition_floors
from suryabench.corpus.manifest import compute_file_sha256, load_manifest
from suryabench.corpus.schema import CorpusManifest, DocumentInventory, Jurisdiction

FIXTURE_CORPUS_DIR = Path(__file__).parents[1] / "fixtures" / "corpus"


def test_fetch_document_local_and_immutability() -> None:
    """Test fetching from local source and verifying immutability protection."""
    src_file = FIXTURE_CORPUS_DIR / "raw" / "MH-C3-001.txt"

    with tempfile.TemporaryDirectory() as tmpdir:
        raw_dir = Path(tmpdir) / "raw"
        res = fetch_document(source=src_file, doc_id="TEST-001", raw_dir=raw_dir, extension="txt")

        assert res.doc_id == "TEST-001"
        assert res.file_path.exists()
        assert res.sha256 == compute_file_sha256(src_file)

        # Attempting to fetch again without force=True must raise SuryaBenchError
        with pytest.raises(SuryaBenchError, match="Immutable store violation"):
            fetch_document(source=src_file, doc_id="TEST-001", raw_dir=raw_dir, extension="txt")


def test_extract_document_and_metadata_logging() -> None:
    """Test extracting text from raw document and verifying provenance metadata."""
    raw_file = FIXTURE_CORPUS_DIR / "raw" / "MH-C3-001.txt"

    with tempfile.TemporaryDirectory() as tmpdir:
        text_dir = Path(tmpdir) / "text"
        txt_path, meta_path = extract_document(raw_file, "TEST-001", text_dir)

        assert txt_path.exists()
        assert meta_path.exists()

        text_content = txt_path.read_text(encoding="utf-8")
        assert "MAHARASHTRA ELECTRICITY REGULATORY COMMISSION" in text_content

        meta_json = meta_path.read_text(encoding="utf-8")
        assert '"tool": "native_text_reader"' in meta_json
        assert '"text_layer": "native"' in meta_json
        assert f'"{compute_file_sha256(raw_file)}"' in meta_json


def test_add_document_to_manifest() -> None:
    """Test adding inventory records and verifying SHA-256 updating."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manifest_path = Path(tmpdir) / "MANIFEST.json"
        doc = DocumentInventory(
            doc_id="MH-C3-999",
            title="Test Solar Circular",
            doc_class=DocumentClass.C5,
            issuer="MSEDCL",
            jurisdiction=Jurisdiction(level=JurisdictionLevel.STATE, code=StateCode.MH),
            doc_date="2024-01-01",
            effective_date="2024-01-01",
            effective_date_basis=EffectiveDateBasis.E1,
            effective_date_confidence=ConfidenceLevel.HIGH,
            retrieved_via=Discoverability.NAV,
            retrieved_at="2026-09-21T12:00:00Z",
            sha256="abc123def456",
            pages=2,
            text_layer=TextLayer.NATIVE,
            status="presumed_current",
            discoverability=Discoverability.NAV,
        )

        manifest = add_document_to_manifest(manifest_path, doc)
        assert len(manifest.documents) == 1
        assert manifest.documents[0].doc_id == "MH-C3-999"

        # Check that file exists and re-loads
        loaded = load_manifest(manifest_path)
        assert len(loaded.documents) == 1
        assert (Path(tmpdir) / "MANIFEST.sha256").exists()


def test_composition_floors_checker() -> None:
    """Test composition floors MC-1 through MC-5 evaluator."""
    manifest = CorpusManifest(
        corpus_version="Test-2026.11",
        created_at="2026-09-21T00:00:00Z",
        documents=[
            DocumentInventory(
                doc_id="D1",
                title="Doc 1",
                doc_class=DocumentClass.C1,
                issuer="MNRE",
                jurisdiction=Jurisdiction(level=JurisdictionLevel.CENTRAL, code=StateCode.IN),
                doc_date="2024-01-01",
                effective_date="UNKNOWN",
                effective_date_basis=EffectiveDateBasis.E9,
                effective_date_confidence=ConfidenceLevel.LOW,
                retrieved_via=Discoverability.ORPHAN,
                retrieved_at="2026-09-21T00:00:00Z",
                sha256="1111",
                pages=1,
                text_layer=TextLayer.NATIVE,
                status="unknown",
                discoverability=Discoverability.ORPHAN,
            ),
            DocumentInventory(
                doc_id="D2",
                title="Doc 2",
                doc_class=DocumentClass.C3,
                issuer="MERC",
                jurisdiction=Jurisdiction(level=JurisdictionLevel.STATE, code=StateCode.MH),
                doc_date="2024-01-01",
                effective_date="UNKNOWN",
                effective_date_basis=EffectiveDateBasis.E9,
                effective_date_confidence=ConfidenceLevel.LOW,
                retrieved_via=Discoverability.WEB_SEARCH,
                retrieved_at="2026-09-21T00:00:00Z",
                sha256="2222",
                pages=1,
                text_layer=TextLayer.NATIVE,
                status="unknown",
                discoverability=Discoverability.WEB_SEARCH,
            ),
        ],
    )

    # With only 2 docs, floors MC-1 (needs 6 pairs) and MC-3 (needs 4 docs) will fail
    report = check_composition_floors(manifest, supersession_pair_count=2)
    assert report.passed is False
    assert report.floors["MC-1"].passed is False
    assert report.floors["MC-4"].passed is True  # 2 unknown dates met

    # Test full pass when parameters meet thresholds
    full_report = check_composition_floors(
        manifest,
        supersession_pair_count=6,
        live_superseded_pair_count=3,
        states_in_supersession={StateCode.MH, StateCode.RJ},
    )
    # MC-3 still has only 2 web_search/orphan docs
    assert full_report.floors["MC-3"].passed is False
