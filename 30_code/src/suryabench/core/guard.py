"""Test-split access guard hook.

Enforces that held-out test split benchmark cases are never inspected during prompt engineering,
tool design, or agent tuning.
"""

import hashlib
import json
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
from typing import Any

from suryabench.core.exceptions import TestSplitAccessViolation
from suryabench.paths import BENCHMARK_DIR

# Sealed sha256 digests of every test case's content (see scripts/seal_test_hashes.py). They hold no case content.
TEST_HASHES_FILE = BENCHMARK_DIR / "TEST_CASE_HASHES.json"
# Content hashes of the candidate v2 test split (provisional labels, not sealed): guarded the same way,
# so no model run reads the candidates before human verification and sealing.
TEST_CANDIDATE_HASHES_FILE = BENCHMARK_DIR / "TEST_CANDIDATE_HASHES.json"

# Context variable to indicate whether test split reading is explicitly authorized (e.g., eval entrypoint)
_TEST_SPLIT_AUTHORIZED: ContextVar[bool] = ContextVar("test_split_authorized", default=False)


def case_content_hash(case: dict[str, Any]) -> str:
    """sha256 of the case content (facts + inputs), independent of case id, order and file name."""
    body = json.dumps({"facts": case.get("facts"), "inputs": case.get("inputs")}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


@lru_cache(maxsize=1)
def _test_hashes() -> frozenset[str]:
    hashes: set[str] = set()
    for f in (TEST_HASHES_FILE, TEST_CANDIDATE_HASHES_FILE):
        if f.exists():
            hashes |= set(json.loads(f.read_text(encoding="utf-8")))
    return frozenset(hashes)


def file_contains_test_cases(path: Path, hashes: frozenset[str] | None = None) -> bool:
    """True when the JSON file at `path` holds at least one case whose content hash is a sealed test hash."""
    hashes = _test_hashes() if hashes is None else hashes
    if not hashes or path.suffix != ".json" or not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    cases = data if isinstance(data, list) else [data]
    return any(isinstance(c, dict) and case_content_hash(c) in hashes for c in cases)


def verify_fingerprint(path: Path) -> str:
    """The sha256 of a sealed split, checked against the ``<name>.sha256`` written beside it at sealing (T8).

    Raises TestSplitAccessViolation when the seal file is missing or the content no longer matches it.
    """
    seal = path.with_suffix(".sha256")
    if not seal.is_file():
        raise TestSplitAccessViolation(f"{path.name} has no seal file {seal.name}; seal it first (seal_test_v3.py)")
    expected = seal.read_text(encoding="utf-8").split()[0]
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise TestSplitAccessViolation(f"{path.name} sha256 {actual[:12]} does not match its seal {expected[:12]}")
    return actual


class TestSplitGuard:
    """Context manager or controller for held-out test split access control."""

    __test__ = False

    @classmethod
    def authorize(cls) -> "TestSplitAuthorizationContext":
        """Authorize access to the sealed test split within a scoped context block."""
        return TestSplitAuthorizationContext()

    @classmethod
    def is_authorized(cls) -> bool:
        """Check if test split access is currently authorized."""
        return _TEST_SPLIT_AUTHORIZED.get()

    @classmethod
    def verify_access(cls, file_or_case_id: str | Path, is_test_split: bool | None = None) -> None:
        """Verify whether access to the requested case is permitted.

        Args:
            file_or_case_id: Identifier or file path of the case.
            is_test_split: Explicit flag. If None, checks the name for test markers and any JSON file's
                cases against the sealed test content hashes.

        Raises:
            TestSplitAccessViolation: If access to test split is attempted without authorization.
        """
        path_str = str(file_or_case_id)
        is_test = (
            is_test_split
            if is_test_split is not None
            else (
                "test_split" in path_str
                or "test_cases" in path_str
                or file_contains_test_cases(Path(path_str))  # by content hash, whatever the file is called
            )
        )

        if is_test and not cls.is_authorized():
            raise TestSplitAccessViolation(
                f"Prohibited access to held-out test split resource: '{file_or_case_id}'. "
                "Test cases must never be accessed during prompt engineering, tool development, or dev tuning. "
                "Access is permitted strictly via the final evaluation runner entrypoint."
            )


class TestSplitAuthorizationContext:
    """Scoped context manager that enables test split authorization."""

    def __enter__(self) -> None:
        self._token = _TEST_SPLIT_AUTHORIZED.set(True)

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        _TEST_SPLIT_AUTHORIZED.reset(self._token)
