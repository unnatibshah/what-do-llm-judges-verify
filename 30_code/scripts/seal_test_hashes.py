"""Write 40_data/benchmark/TEST_CASE_HASHES.json: sha256 of each test case's content, never the content itself.

Run once per sealed test split (re-run when new test clusters are sealed; hashes are only ever added).
"""

import json

from suryabench.core.guard import TEST_HASHES_FILE, case_content_hash
from suryabench.paths import BENCHMARK_DIR

if __name__ == "__main__":
    cases = json.loads((BENCHMARK_DIR / "test_cases_100.json").read_text(encoding="utf-8"))
    old = json.loads(TEST_HASHES_FILE.read_text(encoding="utf-8")) if TEST_HASHES_FILE.exists() else []
    hashes = sorted(set(old) | {case_content_hash(c) for c in cases})
    TEST_HASHES_FILE.write_text(json.dumps(hashes, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(len(hashes), "test case hashes ->", TEST_HASHES_FILE.name)
