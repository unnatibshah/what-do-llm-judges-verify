"""Unit tests for corpus manifest parsing, hashing, and verification."""

import tempfile
from pathlib import Path

import pytest

from suryabench.core.exceptions import ManifestMismatchError
from suryabench.corpus.manifest import (
    compute_file_sha256,
    load_manifest,
    save_manifest,
    verify_manifest,
)
from suryabench.paths import CORPUS_DIR

FIXTURE_CORPUS_DIR = Path(__file__).parents[1] / "fixtures" / "corpus"


def test_load_fixture_manifest() -> None:
    """Test that the fixture manifest loads and parses according to schema."""
    manifest_path = FIXTURE_CORPUS_DIR / "MANIFEST.json"
    manifest = load_manifest(manifest_path)

    assert manifest.corpus_version == "SuryaBench-Corpus-2026.11-fixture"
    assert len(manifest.documents) == 3
    doc_ids = {d.doc_id for d in manifest.documents}
    assert doc_ids == {"IN-C1-001", "MH-C3-001", "MH-C3-002"}


def test_verify_manifest_success() -> None:
    """Test that verify_manifest succeeds on intact fixture files."""
    manifest_path = FIXTURE_CORPUS_DIR / "MANIFEST.json"
    raw_dir = FIXTURE_CORPUS_DIR / "raw"
    manifest = load_manifest(manifest_path)

    # Should succeed without raising
    verify_manifest(manifest, raw_dir)


def test_verify_manifest_hash_mismatch() -> None:
    """Test that verify_manifest raises ManifestMismatchError if file content is tampered."""
    manifest_path = FIXTURE_CORPUS_DIR / "MANIFEST.json"
    manifest = load_manifest(manifest_path)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_raw = Path(tmpdir)
        # Create a file with incorrect content
        bad_file = tmp_raw / "IN-C1-001.txt"
        bad_file.write_text("TAMPERED CONTENT", encoding="utf-8")

        with pytest.raises(ManifestMismatchError, match="SHA-256 mismatch"):
            verify_manifest(manifest, tmp_raw)


def test_save_and_hash_manifest() -> None:
    """Test saving a manifest and generating the corresponding MANIFEST.sha256 file."""
    manifest_path = FIXTURE_CORPUS_DIR / "MANIFEST.json"
    manifest = load_manifest(manifest_path)

    with tempfile.TemporaryDirectory() as tmpdir:
        dest_manifest = Path(tmpdir) / "MANIFEST.json"
        dest_sha256 = Path(tmpdir) / "MANIFEST.sha256"

        manifest_hash = save_manifest(manifest, dest_manifest)
        assert dest_manifest.exists()
        assert dest_sha256.exists()

        computed = compute_file_sha256(dest_manifest)
        assert computed == manifest_hash
        assert manifest_hash in dest_sha256.read_text(encoding="utf-8")


def test_live_corpus_expanded_inventory_and_floors() -> None:
    """The live corpus meets the authentic-document floors (>=30 total, >=10 per jurisdiction)."""
    live_corpus_dir = CORPUS_DIR
    manifest_path = live_corpus_dir / "MANIFEST.json"
    if not manifest_path.exists():
        pytest.skip("Live corpus manifest not found")

    manifest = load_manifest(manifest_path)

    # 1. Document floors (researcher decision 2026-09-23: >=30 authentic, across IN, MH, RJ)
    assert len(manifest.documents) >= 30, f"Expected >=30 documents, got {len(manifest.documents)}"
    for prefix in ("IN", "MH", "RJ"):
        assert sum(d.doc_id.startswith(prefix) for d in manifest.documents) >= 10, prefix

    # 2. Verify immutable raw files match cryptographic SHA-256 hashes
    verify_manifest(manifest, live_corpus_dir / "raw")

    # 3. Verify text layer extractions and provenance metadata
    for doc in manifest.documents:
        txt_path = live_corpus_dir / "text" / f"{doc.doc_id}.txt"
        meta_path = live_corpus_dir / "text" / f"{doc.doc_id}.meta.json"
        assert txt_path.exists(), f"Missing text extraction for {doc.doc_id}"
        assert txt_path.stat().st_size > 0, f"Empty text extraction for {doc.doc_id}"
        assert meta_path.exists(), f"Missing metadata sidecar for {doc.doc_id}"

    # 4. Recency floor: >70% post-2021
    recent_docs = [d for d in manifest.documents if d.doc_date >= "2021-01-01"]
    recent_ratio = len(recent_docs) / len(manifest.documents)
    assert recent_ratio >= 0.70, f"Expected >=70% post-2021 documents, got {recent_ratio:.1%}"

    # 5. Composition floors MC-1 through MC-5
    from suryabench.core.enums import StateCode
    from suryabench.corpus.inventory import check_composition_floors

    report = check_composition_floors(
        manifest=manifest,
        supersession_pair_count=11,
        live_superseded_pair_count=5,
        states_in_supersession={StateCode.MH, StateCode.RJ},
    )
    assert report.passed, f"Composition floors check failed:\n{report.summary}"
