"""T8: the v3 seal applies adjudication by its rules, and a test run refuses a file that does not match its seal."""

import csv
import json
import sys
from pathlib import Path

import pytest

from suryabench.core.exceptions import TestSplitAccessViolation
from suryabench.core.guard import verify_fingerprint
from suryabench.paths import CODE_DIR

sys.path.insert(0, str(CODE_DIR / "scripts"))
import seal_test_v3 as seal  # noqa: E402


def _edit(path: Path, key: str, value: str, **changes: str) -> None:
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        if r[key] == value:
            r.update(changes)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def test_fingerprint(tmp_path: Path) -> None:
    f = tmp_path / "test_cases_v3.json"
    f.write_text("[]\n", encoding="utf-8")
    with pytest.raises(TestSplitAccessViolation, match="no seal file"):
        verify_fingerprint(f)
    (tmp_path / "test_cases_v3.sha256").write_text(f"{seal.sha256(f)}  test_cases_v3.json\n", encoding="utf-8")
    assert verify_fingerprint(f) == seal.sha256(f)
    f.write_text("[{}]\n", encoding="utf-8")
    with pytest.raises(TestSplitAccessViolation, match="does not match"):
        verify_fingerprint(f)


def test_unchanged_adjudication_seals_the_candidate_bytes(tmp_path: Path) -> None:
    adj = tmp_path / "adj"
    adj.mkdir()
    seal.stand_in(adj)
    m = seal.seal(adj, tmp_path / "out", dry_run=True)
    assert m["sha256"] == m["candidate_sha256"] and m["n_cases"] == 60 and m["distinct_replaced_clauses"] == 15
    assert m["registry"] == "registry_real_v2_r3.json" and not m["problems"]


def test_drops_and_registry_changes(tmp_path: Path) -> None:
    adj = tmp_path / "adj"
    adj.mkdir()
    seal.stand_in(adj)
    manifest = json.loads(seal.CAND_MANIFEST.read_text(encoding="utf-8"))
    by_clause = {r["clause"]: r["cases"] for r in manifest["replaced_clauses"]}
    rejected = "DL-C3-004#cl-3.8"
    ties = [k["link_id"] for k in seal.read(seal.ANNOTATION_DIR / "LINKS_KEY_DO_NOT_SHARE.csv")
            if f"planted:{rejected}" in k["cited_by_test_pairs"].split(";")]
    assert len(ties) == 2  # L004 (a neighbouring chunk's link) and L010
    _edit(adj / "links_ADJUDICATED.csv", "link_id", ties[0], relation="NO_CHANGE")
    assert seal.seal(adj, tmp_path / "one", dry_run=True)["distinct_replaced_clauses"] == 15  # one link left: kept
    for lid in ties[1:]:
        _edit(adj / "links_ADJUDICATED.csv", "link_id", lid, relation="NO_CHANGE")
    other_case = by_clause["UP-C3-001#cl-6.2"][0]
    _edit(adj / "cases_ADJUDICATED.csv", "case_id", other_case, decision="ABSTAIN")
    m = seal.seal(adj, tmp_path / "out", dry_run=True)
    assert set(m["dropped_cases"]) == {*by_clause[rejected], other_case}
    assert m["n_cases"] == 55 and m["distinct_replaced_clauses"] == 14
    assert m["registry"] == "registry_real_v3.json" and (tmp_path / "out" / "registry_real_v3.json").exists()
    assert m["sha256"] != m["candidate_sha256"]


def test_clause_disputes_are_kept_and_flagged_controls_listed(tmp_path: Path) -> None:  # D49
    adj = tmp_path / "adj"
    adj.mkdir()
    seal.stand_in(adj)
    cases = seal.read(adj / "cases_ADJUDICATED.csv")
    disputed, wrong = cases[0]["case_id"], cases[1]["case_id"]
    _edit(adj / "cases_ADJUDICATED.csv", "case_id", disputed, deciding_clauses="XX-C1-001#cl-1")
    _edit(adj / "cases_ADJUDICATED.csv", "case_id", wrong, decision="ABSTAIN")
    ctrl = [r["item_id"] for r in seal.read(adj / "controls_check.csv")]
    flagged = [i for i in ctrl if i.split("#")[0] != wrong][:3]
    for i in flagged:
        _edit(adj / "controls_check.csv", "item_id", i, decision="INCOMPLETE")
    m = seal.seal(adj, tmp_path / "out", dry_run=True)
    assert not m["problems"] and m["n_cases"] == 59 and set(m["dropped_cases"]) == {wrong}
    assert set(m["clause_disputed"]) == {disputed} and set(m["strict_dropped"]) == {disputed, wrong}
    assert set(m["controls_flagged"]) == {i.split("#")[0] for i in flagged}
    assert m["controls_correct"] == round(1 - 3 / len(ctrl), 4)


def test_unresolved_merge_rows_block_the_seal(tmp_path: Path) -> None:
    adj = tmp_path / "adj"
    adj.mkdir()
    seal.stand_in(adj)
    case = seal.read(adj / "cases_ADJUDICATED.csv")[0]["case_id"]
    _edit(adj / "cases_ADJUDICATED.csv", "case_id", case, decision="", decided_by="ADJUDICATE")
    _edit(adj / "links_ADJUDICATED.csv", "link_id", "L002", relation="", decided_by="ADJUDICATE")
    m = seal.seal(adj, tmp_path / "out", dry_run=True)
    assert len(m["problems"]) == 4 and not (tmp_path / "out" / "test_cases_v3.json").exists()
