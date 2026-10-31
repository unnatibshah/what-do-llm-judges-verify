"""Manifest verification, hashing, and management utilities."""

import hashlib
import json
from pathlib import Path

from suryabench.core.exceptions import ManifestMismatchError
from suryabench.corpus.schema import CorpusManifest


def compute_file_sha256(file_path: Path) -> str:
    """Compute SHA-256 hex digest for a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_string_sha256(content: str) -> str:
    """Compute SHA-256 hex digest for a string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def load_manifest(manifest_path: Path) -> CorpusManifest:
    """Load and validate a CorpusManifest from a JSON file."""
    with open(manifest_path, encoding="utf-8") as f:
        data = json.load(f)
    return CorpusManifest.model_validate(data)


def save_manifest(manifest: CorpusManifest, manifest_path: Path) -> str:
    """Save CorpusManifest to JSON and write accompanying MANIFEST.sha256 root of trust.

    Returns:
        The SHA-256 hash of the generated MANIFEST.json.
    """
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_json = manifest.model_dump_json(by_alias=True, indent=2) + "\n"

    with open(manifest_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(manifest_json)

    manifest_hash = compute_string_sha256(manifest_json)
    sha256_file = manifest_path.with_name("MANIFEST.sha256")
    with open(sha256_file, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"{manifest_hash}  {manifest_path.name}\n")

    return manifest_hash


def verify_manifest(manifest: CorpusManifest, raw_dir: Path) -> None:
    """Verify that all files declared in the manifest exist in raw_dir and match their SHA-256.

    Raises:
        ManifestMismatchError: If any document is missing or hash does not match.
    """
    errors: list[str] = []
    for doc in manifest.documents:
        # Check files with common extensions or doc_id prefix
        matched_files = list(raw_dir.glob(f"{doc.doc_id}.*"))
        if not matched_files:
            errors.append(f"Missing file for doc_id '{doc.doc_id}' in {raw_dir}")
            continue

        raw_file = matched_files[0]
        actual_hash = compute_file_sha256(raw_file)
        if actual_hash.lower() != doc.sha256.lower():
            errors.append(
                f"SHA-256 mismatch for {doc.doc_id} ({raw_file.name}): "
                f"expected {doc.sha256}, got {actual_hash}"
            )

    if errors:
        raise ManifestMismatchError("\n".join(errors))
