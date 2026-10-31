"""D13: v2 case generation (opaque ids, shuffled slots, wide magnitudes), v1 reproducibility, and the content-hash guard."""

import hashlib
import json
import re
from pathlib import Path

import pytest

from suryabench.cases import generator as g
from suryabench.core.exceptions import TestSplitAccessViolation
from suryabench.core.guard import TestSplitGuard, case_content_hash, file_contains_test_cases
from suryabench.paths import BENCHMARK_DIR

ALL = BENCHMARK_DIR / "benchmark_cases_160.json"


def test_v1_dev_regenerates_byte_identically() -> None:
    graph = g._load_graph()
    dev = [c for n in g.DEV_RULE_NODES for c in g.generate_node_cases(n, graph)]
    text = json.dumps([c.model_dump(mode="json", exclude=None if c.cluster_id else {"cluster_id"}) for c in dev], indent=2)
    assert hashlib.sha256(text.encode()).hexdigest() == hashlib.sha256((BENCHMARK_DIR / "dev_cases_60.json").read_bytes()).hexdigest()


def test_v2_dev_is_deterministic_opaque_and_shuffled() -> None:
    a, b = g.build_v2_dev(), g.build_v2_dev()
    assert [c.model_dump() for c in a] == [c.model_dump() for c in b]
    assert len(a) == 60
    assert all(re.fullmatch(r"SB-[0-9a-f]{8}", c.case_id) for c in a)
    assert len({c.case_id for c in a}) == 60
    # no cluster, slot or trap information in the ids
    assert not any(c.case_id.startswith(("MH", "RJ", "IN")) for c in a)
    # order is shuffled: the same trap type does not sit at the same position in every block of 20
    blocks = [[c.failure_class_probed for c in a[i:i + 20]] for i in (0, 20, 40)]
    assert blocks[0] != blocks[1] != blocks[2]


def test_v2_keeps_partitions_and_trap_validity() -> None:
    cases = g.build_v2_dev()  # builds assert every trap flips the verdict; the suite validator also ran
    probed = {c.failure_class_probed for c in cases}
    assert {"CLEAN", "F2", "F3", "F4", "F5", "F6", "F9", "MULTI"} <= probed
    for cls in ("F5", "F6"):
        assert sum(fe.fault_class == cls for c in cases for fe in c.fault_events) >= 5


def test_v2_magnitudes_overlap_between_clean_and_f5() -> None:
    cases = g.build_v2_dev()
    clean = [c.facts.proposed_capacity_kw for c in cases if c.failure_class_probed == "CLEAN"]
    f5 = [c.facts.proposed_capacity_kw for c in cases if c.failure_class_probed == "F5"]
    assert max(clean) > min(f5)
    assert max(clean) < 1000  # no clean net-metering case exceeds the 1 MW ceiling


def test_saved_v2_file_matches_generator() -> None:
    path = BENCHMARK_DIR / "dev_cases_v2.json"
    text = json.dumps([c.model_dump(mode="json") for c in g.build_v2_dev()], indent=2)
    assert path.read_text(encoding="utf-8") == text
    digest = (BENCHMARK_DIR / "dev_cases_v2.sha256").read_text(encoding="utf-8").split()[0]
    assert digest == hashlib.sha256(path.read_bytes()).hexdigest()


def test_guard_blocks_any_file_holding_test_cases() -> None:
    with pytest.raises(TestSplitAccessViolation):
        TestSplitGuard.verify_access(ALL)  # name has no test marker; content does
    with TestSplitGuard.authorize():
        TestSplitGuard.verify_access(ALL)


def test_guard_blocks_renamed_copy_and_allows_dev(tmp_path: Path) -> None:
    copy = tmp_path / "innocent.json"
    copy.write_bytes(ALL.read_bytes())
    with pytest.raises(TestSplitAccessViolation):
        TestSplitGuard.verify_access(copy)
    for name in ("dev_cases_60.json", "dev_cases_v2.json"):
        TestSplitGuard.verify_access(BENCHMARK_DIR / name)


def test_content_hash_ignores_case_id_and_file_name() -> None:
    case = json.loads((BENCHMARK_DIR / "dev_cases_60.json").read_text(encoding="utf-8"))[0]
    renamed = {**case, "case_id": "SB-00000000"}
    assert case_content_hash(case) == case_content_hash(renamed)
    assert file_contains_test_cases(BENCHMARK_DIR / "dev_cases_60.json", frozenset({case_content_hash(case)}))
    assert not file_contains_test_cases(BENCHMARK_DIR / "dev_cases_60.json", frozenset({"0" * 64}))
