"""Document fetching and immutable ingestion pipeline.

Protocol §4 requirement:
1. Download directly without opening in modifying editors.
2. Compute SHA-256 immediately upon download.
3. Store immutably under corpus/raw/<doc_id>.<ext>.
"""

import shutil
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from suryabench.core.exceptions import SuryaBenchError
from suryabench.corpus.manifest import compute_file_sha256


@dataclass(frozen=True)
class FetchResult:
    """Outcome of document fetch operation."""

    doc_id: str
    file_path: Path
    sha256: str
    size_bytes: int
    source_url: str | None


def fetch_document(
    source: str | Path,
    doc_id: str,
    raw_dir: Path,
    extension: str | None = None,
    timeout: int = 30,
    force: bool = False,
) -> FetchResult:
    """Fetch a document from a remote URL or local path and store it immutably.

    Args:
        source: URL or local path to source document.
        doc_id: Unique document ID (e.g. 'MH-C3-004').
        raw_dir: Destination directory for raw corpus files.
        extension: Explicit file extension (e.g. 'pdf', 'txt'). If None, derived from source.
        timeout: Network timeout in seconds.
        force: Overwrite if file already exists (strictly discouraged in production).

    Returns:
        FetchResult containing the local path, SHA-256, and metadata.

    Raises:
        SuryaBenchError: If file already exists and force is False, or download fails.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    source_str = str(source)

    # Derive extension
    if extension is None:
        source_path = Path(source_str.split("?")[0])
        ext = source_path.suffix.lstrip(".")
        extension = ext if ext else "pdf"

    dest_filename = f"{doc_id}.{extension}"
    dest_path = raw_dir / dest_filename

    if dest_path.exists() and not force:
        raise SuryaBenchError(
            f"Immutable store violation: file '{dest_path}' already exists for doc_id '{doc_id}'. "
            "Corpus documents must not be rewritten once ingested."
        )

    source_url: str | None = None

    if source_str.startswith(("http://", "https://")):
        source_url = source_str
        req = urllib.request.Request(
            source_str,
            headers={
                "User-Agent": "SuryaBench-Corpus-Collector/1.0 (Regulatory Research Benchmark; non-commercial)"
            },
        )
        try:
            with (
                urllib.request.urlopen(req, timeout=timeout) as response,
                open(dest_path, "wb") as out,
            ):
                shutil.copyfileobj(response, out)
        except Exception as e:
            if dest_path.exists():
                dest_path.unlink()
            raise SuryaBenchError(
                f"Failed to fetch document '{doc_id}' from URL '{source_str}': {e}"
            ) from e
    else:
        local_src = Path(source_str)
        if not local_src.exists():
            raise SuryaBenchError(f"Source file does not exist: '{local_src}'")
        shutil.copy2(local_src, dest_path)

    # Compute hash immediately
    file_sha256 = compute_file_sha256(dest_path)
    file_size = dest_path.stat().st_size

    return FetchResult(
        doc_id=doc_id,
        file_path=dest_path,
        sha256=file_sha256,
        size_bytes=file_size,
        source_url=source_url,
    )
