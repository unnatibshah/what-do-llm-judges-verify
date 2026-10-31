"""Corpus r3 (staging), the v3 rule functions and clusters, the candidate test split and its guard,
and the annotation-agreement script."""

import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

from suryabench.cases import generator_v3 as g3
from suryabench.cases import rules_v3 as r3
from suryabench.core.enums import CurrencyVerdict, FaultClass
from suryabench.core.exceptions import TestSplitAccessViolation
from suryabench.core.guard import TEST_CANDIDATE_HASHES_FILE, TestSplitGuard, case_content_hash
from suryabench.corpus.manifest import compute_file_sha256, load_manifest
from suryabench.graph.oracle import in_force, validate_graph
from suryabench.paths import BENCHMARK_DIR, CODE_DIR, CORPUS_DIR, CORPUS_R3_DIR

sys.path.insert(0, str(CODE_DIR / "scripts"))
import annotation_agreement as aa  # noqa: E402
import trivial_baselines as tb  # noqa: E402

CANDIDATE = BENCHMARK_DIR / g3.CANDIDATE_FILE


@pytest.fixture(scope="module")
def graph():  # type: ignore[no-untyped-def]
    gr = g3.load_r3_graph()
    validate_graph(gr)
    return gr


@pytest.fixture(scope="module")
def cases(graph):  # type: ignore[no-untyped-def]
    return g3.generate_v3_cases(graph)


def test_r3_manifest_extends_r2_unchanged() -> None:
    r2 = load_manifest(CORPUS_DIR / "MANIFEST.json")
    r3m = load_manifest(CORPUS_R3_DIR / "MANIFEST.json")
    assert r3m.corpus_version == "SuryaBench-Corpus-2026.10-r3"
    old = {d.doc_id: d for d in r3m.documents if d.verification_status is None}
    assert {d.doc_id: d.model_dump() for d in r2.documents} == {k: v.model_dump() for k, v in old.items()}
    new = [d for d in r3m.documents if d.verification_status is not None]
    assert len(new) == 65 and all(d.verification_status == "UNVERIFIED" for d in new)
    assert all(d.provenance_file and (CORPUS_R3_DIR / d.provenance_file).is_file() for d in new)
    # D23: copies on the BESCOM / TANGEDCO portals are flagged
    assert all(d.source_class == "discom_copy" for d in new if "srtpv.bescom.org" in (d.retrieved_url or "")
               and not d.issuer.startswith("BESCOM"))
    assert all(d.source_class == "discom_copy" for d in new if d.jurisdiction.code == "TN")
    assert {d.doc_id for d in new if d.status == "draft_not_in_force"} == {"GJ-C3-006", "GJ-C3-008"}
    # MANIFEST.sha256 is the hash of MANIFEST.json, and every raw file matches its manifest hash
    digest = (CORPUS_R3_DIR / "MANIFEST.sha256").read_text(encoding="utf-8").split()[0]
    assert digest == hashlib.sha256((CORPUS_R3_DIR / "MANIFEST.json").read_bytes()).hexdigest()
    for d in new:
        assert compute_file_sha256(CORPUS_R3_DIR / "raw" / f"{d.doc_id}.pdf") == d.sha256
        assert (CORPUS_R3_DIR / "text" / f"{d.doc_id}.txt").is_file()


def test_r3_graph_new_items_are_unverified_and_quoted(graph) -> None:  # type: ignore[no-untyped-def]
    new = [n for n in graph.nodes.values() if n.verification_status is not None]
    assert len(new) > 100 and all(n.verification_status == "UNVERIFIED" for n in new)
    assert all(n.quote_check in {"exact", "loose", "pypdf_text_only"} for n in new)
    new_edges = [e for e in graph.edges if e.verification_status is not None]
    assert new_edges and all(e.verification_status == "UNVERIFIED" and e.evidence.quote_text for e in new_edges)
    # no supersession edge is drawn from a draft instrument
    drafts = {"GJ-C3-006", "GJ-C3-008"}
    assert not any(graph.nodes[e.to_node].doc_id in drafts for e in graph.edges)


def test_rule_functions_quote_their_numbers() -> None:
    assert r3.dt_limit("GJ-C3-003#cl-5-proviso", 100, 60, 10).ok and not r3.dt_limit("GJ-C3-001#cl-5-proviso", 100, 60, 10).ok
    assert r3.capacity("GJ-C3-004#cl-6.2c-i", 2, 4.5).ok and not r3.capacity("GJ-C3-001#cl-6.2", 2, 4.5).ok
    assert not r3.capacity("TN-C5-002#cl-I.2", 1200, 1100).ok and r3.capacity("TN-C5-001#cl-2", 1200, 1100).ok
    assert r3.capacity("DL-C3-009#cl-3.8", 100, 500).ok and not r3.capacity("DL-C3-009#cl-3.8", 100, 501).ok
    assert r3.capacity("DL-C3-009#cl-3.8", 100, 900, ground_mounted=False).ok
    assert r3.feasibility("DL-C3-016#cl-g3-stage1-lapse", 30, 16, None).ok
    assert not r3.feasibility("DL-C3-016#cl-g3-stage1-lapse", 30, 15, None).ok
    assert not r3.feasibility("DL-C3-016#cl-g3-stage1-deemed", 8, 1, None, same_supply=False).ok
    assert r3.voltage_level("KA-C3-001#cl-6a", 80, "LT-3ph").ok and not r3.voltage_level(
        "KA-C3-001#cl-6a-2016-quoted", 80, "LT-3ph").ok
    assert r3.almm_list2("IN-C2-013#cl-1b", "2026-12-31", False).ok
    assert not r3.almm_list2("IN-C2-013#cl-1b", "2027-01-01", False).ok
    assert r3.almm_list2("IN-C2-013#cl-1b", "2027-03-31", False, giu_residential=True).ok
    assert r3.up_augmentation("UP-C3-002#cl-6.2-proviso2", 15, True, 5000).ok  # the regulation's own example
    assert not r3.up_augmentation("UP-C3-002#cl-6.2-proviso2", 15, True, 4999).ok
    assert r3.phase2_claim("IN-C1-001#cl-annex1-ii-amended", "2023-10-01", "2025-12-31", True).ok
    assert not r3.phase2_claim("IN-C1-011#cl-annex-phase2-claims", "2023-10-01", "2024-11-01", True).ok


def test_v3_clusters_sizes_and_determinism(cases) -> None:  # type: ignore[no-untyped-def]
    per = Counter(c.cluster_id for c in cases)
    assert len(per) >= 20 and all(10 <= n <= 14 for n in per.values())
    assert {c.facts.state.value for c in cases} >= {"GJ", "KA", "TN", "DL", "UP"}
    again = g3.generate_v3_cases(g3.load_r3_graph())
    assert [c.model_dump() for c in again] == [c.model_dump() for c in cases]
    assert len({case_content_hash(c.model_dump(mode="json")) for c in cases}) == len(cases)
    assert all(c.corpus_version == g3.CORPUS_VERSION_R3 and c.case_id.startswith("SB-") for c in cases)


def test_v3_labels_are_consistent_with_the_r3_graph(cases, graph) -> None:  # type: ignore[no-untyped-def]
    """Decisive clauses are not superseded or not yet in force at the case date; F3 traps are not in force."""
    for c in cases:
        d = c.facts.case_date
        for r in c.applicable_rules:
            v = in_force(r.rule_id, d, graph)
            assert v not in {CurrencyVerdict.SUPERSEDED, CurrencyVerdict.NOT_YET_IN_FORCE}, (c.case_id, r.rule_id, d, v)
        for f in c.fault_events:
            if f.fault_class == FaultClass.F3:
                for e in f.gold_evidence:
                    assert in_force(e, d, graph) != CurrencyVerdict.IN_FORCE, (c.case_id, e, d)
            for e in f.gold_evidence:
                assert "#" not in e or e in graph.nodes, e


def test_capacity_heuristic_is_not_a_shortcut(cases) -> None:  # type: ignore[no-untyped-def]
    dumped = [c.model_dump(mode="json") for c in cases]
    res = tb.analyse(dumped)
    majority = max(res["gold_counts"].values()) / res["n"]
    assert res["accuracy"]["capacity_heuristic"] <= majority + 0.10


def test_candidate_file_matches_generator_and_is_guarded(cases) -> None:  # type: ignore[no-untyped-def]
    text = CANDIDATE.read_text(encoding="utf-8")
    assert text == json.dumps([c.model_dump(mode="json") for c in cases], indent=2)
    digest = (BENCHMARK_DIR / "test_cases_v2_CANDIDATE.sha256").read_text(encoding="utf-8").split()[0]
    assert digest == hashlib.sha256(text.encode("utf-8")).hexdigest()
    hashes = set(json.loads(TEST_CANDIDATE_HASHES_FILE.read_text(encoding="utf-8")))
    assert {case_content_hash(c) for c in json.loads(text)} <= hashes


def test_guard_blocks_candidate_cases_under_any_name(tmp_path: Path) -> None:
    one = json.loads(CANDIDATE.read_text(encoding="utf-8"))[:1]
    renamed = tmp_path / "harmless_dev_file.json"
    renamed.write_text(json.dumps(one), encoding="utf-8")
    with pytest.raises(TestSplitAccessViolation):
        TestSplitGuard.verify_access(renamed)
    with TestSplitGuard.authorize():
        TestSplitGuard.verify_access(renamed)


def test_annotation_agreement_kappa(tmp_path: Path) -> None:
    assert aa.kappa(["A", "A", "R", "R"], ["A", "A", "R", "R"]) == 1.0
    assert aa.kappa(["A", "R", "A", "R"], ["A", "A", "R", "R"]) == 0.0
    assert aa.kappa(["A", "A"], ["A", "A"]) is None
    assert aa.norm("deciding_clauses", "b; a,a") == "a;b"
    assert aa.pabak(["A", "A", "A", "R"], ["A", "A", "A", "A"]) == 0.5 and aa.pabak(["A"], ["A"]) is None
    hdr = ["case_id", "decision", "blocking_stage", "deciding_clauses"]

    def sheet(name: str, rows: list[list[str]]) -> Path:
        p = tmp_path / name
        with open(p, "w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows([hdr, *rows])
        return p

    a = sheet("a.csv", [["c1", "approved", "", "X"], ["c2", "REJECTED", "technical_feasibility", "Y"]])
    b = sheet("b.csv", [["c1", "APPROVED", "", "X"], ["c2", "APPROVED", "", "Y"]])
    res, dis = aa.agreement(aa.read(a)[1], aa.read(b)[1], aa.read(a)[1], aa.FIELDS["cases"])
    assert res["items"] == 2 and res["fields"]["decision"]["agreement_a_b"] == 0.5  # type: ignore[index]
    assert ["c2", "decision", "REJECTED", "APPROVED", "REJECTED"] in dis


def test_annotation_agreement_new_sheets() -> None:
    """D41: the link sheet is compared with the link key in its own vocabulary; quotes and controls are recognised."""
    from suryabench.paths import ANNOTATION_DIR

    def first(sheet: str) -> dict[str, str]:
        with open(ANNOTATION_DIR / sheet, encoding="utf-8", newline="") as f:
            return next(csv.DictReader(f))

    assert [aa.kind_of(first(s)) for s in ("links_to_verify.csv", "r3_quotes_check.csv", "controls_check.csv",
                                           "cases_to_label.csv", "clauses_to_check.csv")] == \
        ["links", "quotes", "controls", "cases", "clauses"]
    key = aa.link_key({"L1": {"new_clause_id": "B#cl-1", "link_type": "partially_supersedes",
                              "effective_date": "2024-01-01", "explicit_implicit_agent": "IMPLICIT"}})
    a = {"L1": {"new_clause_id": "B#cl-1", "relation": "partially_superseded", "effective_date": "2024-01-01",
                "wording": "implicit"}}
    b = {"L1": {"new_clause_id": "B#cl-2", "relation": "SUPERSEDED", "effective_date": "2024-01-01", "wording": "EXPLICIT"}}
    res, dis = aa.agreement(a, b, key, aa.FIELDS["links"])
    assert res["fields"]["relation"]["agreement_a_b"] == 0.0  # type: ignore[index]
    assert ["L1", "relation", "PARTIALLY_SUPERSEDED", "SUPERSEDED", "PARTIALLY_SUPERSEDED"] in dis
    assert not any(d[1] == "effective_date" for d in dis)


def test_annotation_sheets_hide_the_answers() -> None:
    from suryabench.paths import ANNOTATION_DIR

    with open(ANNOTATION_DIR / "cases_to_label.csv", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    from suryabench.paths import BENCHMARK_DIR

    cand = json.loads((BENCHMARK_DIR / "test_cases_v3_CANDIDATE.json").read_text(encoding="utf-8"))
    assert {r["case_id"] for r in rows} == {c["case_id"] for c in cand}  # T1: every v3 candidate case is labelled
    assert all(not r["decision"] and not r["deciding_clauses"] for r in rows)
    assert not {"cluster_id", "failure_class_probed", "expected_decision"} & set(rows[0])
    with open(ANNOTATION_DIR / "ANSWER_KEY_DO_NOT_SHARE.csv", encoding="utf-8", newline="") as f:
        key = list(csv.DictReader(f))
    assert {r["case_id"] for r in key} == {r["case_id"] for r in rows}
    assert len({r["cluster_id"] for r in key}) >= 15
    # H-03 (D41): the annotators' link sheet hides the registry's answer; the agent's tags are in the key only
    with open(ANNOTATION_DIR / "links_to_verify.csv", encoding="utf-8", newline="") as f:
        links = list(csv.DictReader(f))
    with open(ANNOTATION_DIR / "LINKS_KEY_DO_NOT_SHARE.csv", encoding="utf-8", newline="") as f:
        lkey = {r["link_id"]: r for r in csv.DictReader(f)}
    assert links and {r["link_id"] for r in links} == set(lkey)
    assert not {"new_clause_id", "relation", "wording", "substitution_quote", "confidence"} & {k for r in links for k, v in r.items() if v}
    assert not {"link_type", "quote", "explicit_implicit_agent"} & set(links[0])  # "confidence" is the annotator's
    assert all(r["explicit_implicit_agent"] in {"EXPLICIT", "IMPLICIT"} for r in lkey.values())
    with open(ANNOTATION_DIR / "scorer_check.csv", encoding="utf-8", newline="") as f:  # Task 0 submitted 2026-10-28: fully labelled
        assert all(r["label"] for r in csv.DictReader(f))
    for sheet, n in (("controls_check.csv", 40), ("r3_quotes_check.csv", 1)):
        with open(ANNOTATION_DIR / sheet, encoding="utf-8", newline="") as f:
            rs = list(csv.DictReader(f))
        assert len(rs) >= n and all(not r["decision"] and not r["annotator_id"] for r in rs)
    with open(ANNOTATION_DIR / "sources_to_check.csv", encoding="utf-8", newline="") as f:
        src = list(csv.DictReader(f))
    assert src and all(r["url"] and r["url_is_official"] for r in src)  # Task 6 submitted 2026-10-23
