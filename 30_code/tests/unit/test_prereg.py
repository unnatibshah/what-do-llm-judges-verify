"""Preregistered family (analysis/prereg.py) on synthetic run records, Holm, co-primary rule, macros."""

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from suryabench.analysis import prereg
from suryabench.analysis.numbers import render_macros
from suryabench.analysis.prereg import (
    FILES_SPEC,
    MODEL_TAGS,
    Data,
    analyse_all,
    build_spec,
    family,
    load_runs,
    safe,
)

Runs = dict[tuple[str, str, bool], list[dict[str, Any]]]
Caught = Callable[[str, int], bool]  # (cluster, case index) -> bool


def rec(cluster: str, i: int, cond: str, caught: bool, flagged: bool = False, committed: bool = True,
        recovery: bool = False) -> dict[str, Any]:
    cid = f"{cluster}-{i}"
    eid = f"{cid}#exp-{cond}"
    r: dict[str, Any] = {
        "case_id": cid, "cluster_clause_id": cluster, "is_correct": caught, "verifier_flags": [],
        "fault_event_committed": {}, "fault_event_committed_citation": {}, "fault_event_matches": {},
        "fault_event_matches_class": {}, "avoided_trap_matches": {},
        "raw": {"verifier": {"is_flagged": flagged}}}
    if cond in prereg.EXPOSURE_CLASS:
        r["fault_event_committed"][eid] = committed
        r["fault_event_committed_citation"][eid] = committed
        if committed:
            r["fault_event_matches"][eid] = caught
            r["fault_event_matches_class"][eid] = caught
    if recovery:
        r["raw"]["recovery"] = {"flagged": flagged, "initial_correct": False, "final_correct": caught,
                                "initial_outcome_correct": False, "final_outcome_correct": caught}
    return r


def runs_for(label: str, conds: list[str], caught: Caught, flag: Caught = lambda c, i: False,
             n_clusters: int = 10, per: int = 2, meta: bool = True) -> Runs:  # D29: family at metadata on
    out: Runs = {}
    for cond in conds:
        out[(label, cond, meta)] = [
            rec(f"c{k}", i, cond, caught(f"c{k}", i), flag(f"c{k}", i), recovery=label in ("arm3", "reg_oracle"))
            for k in range(n_clusters) for i in range(per)]
    return out


PRIMARY = ["S-both", "J", "A"]  # D28
NEVER: Caught = lambda c, i: False  # noqa: E731
ALWAYS: Caught = lambda c, i: True  # noqa: E731


def base_runs(**kw: Any) -> Runs:
    r = runs_for("arm3", PRIMARY + ["C"], NEVER, **kw)
    return r


def test_p1_exact_one_sided_and_holm_over_five_with_missing_tests() -> None:
    runs = {"m": base_runs()}
    fam = family(Data.build(runs), ["m"])
    p1 = fam["P1"]
    assert p1["p"] == pytest.approx(2**-10) and p1["exact"] and p1["observed"] == 0.0
    assert p1["p_holm"] == pytest.approx(5 * 2**-10, abs=1e-5) and p1["decision"] == "supported"
    assert p1["n_clusters"] == 10 and p1["ci_lower"] is None  # all-zero: degenerate interval refused
    for k in ("P2", "P3", "P4", "P5"):  # nothing to compare to: enter the family with p = 1
        assert fam[k]["status"] == "not_available" and fam[k]["p_for_family"] == 1.0
        assert fam[k]["decision"] is None and fam[k]["decision_note"] == "not available"


def test_p1_not_supported_when_sensitivity_high() -> None:
    runs = {"m": runs_for("arm3", PRIMARY + ["C"], ALWAYS)}
    p1 = family(Data.build(runs), ["m"])["P1"]
    assert p1["p"] == 1.0 and p1["decision"] == "not supported"


def test_p1_few_clusters_reports_test_and_suppresses_ci() -> None:
    p1 = family(Data.build({"m": base_runs(n_clusters=4)}), ["m"])["P1"]
    assert p1["p"] == pytest.approx(1 / 16) and p1["ci_lower"] is None
    assert "only 4 clusters" in p1["ci_note"]


def test_p2_improves_when_sensitivity_rises_and_fpr_flat() -> None:
    runs = {"m": {**base_runs(), **runs_for("arm3@validity", PRIMARY + ["C"], ALWAYS)}}
    p2 = family(Data.build(runs), ["m"])["P2"]
    assert p2["sens_diff"] == 1.0 and p2["sens_p"] == pytest.approx(2 / 1024)
    assert p2["fpr_diff"] == 0.0 and p2["fpr_noninferior"] is True
    assert p2["sens_significant"] and p2["improves"] and p2["decision"] == "supported"
    assert p2["n_clusters"] == 10 and p2["n_events"] == 60


def test_coprimary_rule_blocks_improvement_when_fpr_rises() -> None:
    runs = {"m": {**base_runs(),
                  **runs_for("reg_real", ["J", "S-both", "C"], ALWAYS, flag=lambda c, i: True)}}
    p5 = family(Data.build(runs), ["m"])["P5"]
    assert p5["conds"] == ["J", "S-both"] and p5["n_events"] == 40  # F2+F3 only, A excluded
    assert p5["sens_significant"] is True
    assert p5["fpr_diff"] == 1.0 and p5["fpr_noninferior"] is False
    assert p5["improves"] is False and p5["decision"] == "not supported"


def test_p3_metadata_lower_sensitivity_is_not_an_improvement() -> None:
    off = runs_for("arm3", PRIMARY + ["C"], ALWAYS, meta=False)
    on = runs_for("arm3", PRIMARY + ["C"], lambda c, i: i == 0)
    p3 = family(Data.build({"m": {**off, **on}}), ["m"])["P3"]
    assert p3["sens_diff"] == pytest.approx(-0.5) and p3["config"] == "arm3+meta"
    assert p3["sens_significant"] is False and p3["decision"] == "not supported"


def test_p4_tost_equivalent_and_upper_bound_family_p() -> None:
    runs = {"m": {**base_runs(), **runs_for("arm4_100n", PRIMARY + ["C"], NEVER)}}
    p4 = family(Data.build(runs), ["m"])["P4"]
    assert p4["tost"]["equivalent"] is True and p4["tost"]["margin"] == 0.10
    assert p4["tost"]["p"] == pytest.approx(2**-10) and p4["p_upper"] == pytest.approx(2**-10)
    assert p4["decision"] == "supported"


def test_p4_not_supported_when_100_neutral_clearly_higher() -> None:
    runs = {"m": {**base_runs(), **runs_for("arm4_100n", PRIMARY + ["C"], ALWAYS)}}
    p4 = family(Data.build(runs), ["m"])["P4"]
    assert p4["tost"]["equivalent"] is False and p4["p_upper"] == 1.0
    assert p4["decision"] == "not supported"


def test_holm_adjusts_across_family_and_pooled_pairs_by_model_and_case() -> None:
    def mk(shift: int) -> Runs:  # model-specific catch pattern so pooled differs from each model
        return {**base_runs(), **runs_for("arm3@validity", PRIMARY + ["C"], lambda c, i: i >= shift)}

    d = Data.build({"a": mk(0), "b": mk(1)})
    pooled = family(d, ["a", "b"])
    assert pooled["P2"]["models_used"] == ["a", "b"] and pooled["P2"]["n_events"] == 120
    assert pooled["P2"]["sens_diff"] == pytest.approx(0.75)  # (1.0 + 0.5) / 2 per event
    # Holm over five: P1 (smaller p) is ranked first, so P2 is multiplied by 4; unavailable tests count as p = 1
    assert pooled["P2"]["p_holm"] == pytest.approx(4 * pooled["P2"]["sens_p"], abs=1e-5)
    assert pooled["P1"]["p_holm"] == pytest.approx(5 * pooled["P1"]["p"], abs=1e-5)
    sec = family(d, ["a"], correct=False)
    assert sec["P2"]["p_holm"] == sec["P2"]["sens_p"] and "secondary" in sec["correction"]


def test_partial_data_marks_missing_and_does_not_crash() -> None:
    runs = {"m": {("arm3", "S-both", True): [rec("c0", 0, "S-both", False), rec("c1", 0, "S-both", False),
                                               rec("c2", 0, "S-both", True)]}}
    res = analyse_all(runs, [{"cluster_id": "c0"}], "dev_cases_v2.json")
    assert "reg_real|J+meta" in res["exposure"]["m"]["missing_configurations"]
    assert "arm3|C" in res["exposure"]["m"]["missing_configurations"]  # P3's metadata-off comparator
    assert res["family"]["P2"]["status"] == "not_available"
    assert res["family"]["P1"]["status"] == "partial" and "m:J" in res["family"]["P1"]["missing"]
    assert res["macro_coverage"]["not_available_count"] >= len(prereg.NOT_RUN_DATA)
    assert any(x["macro"] == "SensQwenSevenZZZ" for x in res["not_available"])


def test_load_runs_reads_index_and_canonicalises_cross_model_label(tmp_path: Path) -> None:
    rows = []
    for rid, vm in (("r1", "m1"), ("r2", "other")):
        (tmp_path / rid).mkdir()
        (tmp_path / rid / "evaluations.json").write_text(json.dumps([rec("c0", 0, "S-both", True)]))
        rows.append({"arm": "arm3", "condition": "S-both", "model": "m1", "verifier_model": vm,
                     "variant": "support", "taxonomy": False, "metadata": True, "run_id": rid})
    rows.append({**rows[0], "taxonomy": True, "run_id": "r1"})
    idx = tmp_path / "exposure_index.json"
    idx.write_text(json.dumps(rows))
    runs = load_runs([idx])
    assert set(runs["m1"]) == {("arm3", "S-both", True), ("arm3@x", "S-both", True), ("arm3@tax", "S-both", True)}


def _full_synthetic() -> dict[str, Runs]:
    labels = prereg.EXPECTED_LABELS + prereg.PARAPHRASES[1:]
    conds = ["C", "S-swap", "S-both", "J", "A", "O"]
    out: dict[str, Runs] = {}
    for mi, m in enumerate(MODEL_TAGS.values()):
        runs: Runs = {}
        for li, lab in enumerate(labels):
            runs.update(runs_for(lab, conds, lambda c, i, li=li, mi=mi: (int(c[1:]) + i + li + mi) % 3 == 0,
                                 flag=lambda c, i: int(c[1:]) % 4 == 0, n_clusters=6))
        for lab, cond in prereg.EXPECTED_META_OFF:
            runs.update(runs_for(lab, [cond], ALWAYS, n_clusters=6, meta=False))
        runs.update(runs_for("arm3", ["N"], ALWAYS, n_clusters=6))
        out[m] = runs
    return out


def test_macro_export_covers_every_macro_in_macros_md() -> None:
    runs = _full_synthetic()
    cases = [{"cluster_id": f"c{k}"} for k in range(6) for _ in range(2)]
    spec = build_spec()
    macros_md = Path(__file__).resolve().parents[3] / "60_paper_drafts" / "paper_v2" / "MACROS.md"
    res = analyse_all(runs, cases, "test_cases_v2.json", spec, macros_md)
    cov = res["macro_coverage"]
    assert cov["unmapped_in_macros_md"] == []
    assert cov["emitted"] == len(spec) and cov["not_available_count"] == len(prereg.NOT_RUN_DATA)
    assert {x["macro"] for x in res["not_available"]} == set(prereg.NOT_RUN_DATA)
    tex = render_macros(res, spec)  # numbers.py consumes the spec: every path is a scalar
    assert tex.count("\\newcommand") == len(spec)
    pooled_sens = res["exposure"]["pooled"]["pooled"]["arm3+meta"]["sensitivity"]["display"]
    assert f"\\newcommand{{\\SensPooledZZZ}}{{{pooled_sens.replace('%', chr(92) + '%')}}}" in tex
    assert res["exposure"][safe("qwen2.5:7b")]["commit"]["J+meta"]["primary"]["total_opportunities"] == 12
    assert re.search(r"\\newcommand\{\\PTwoDecision\}\{(supported|not supported)\}", tex)
    assert res["counts"]["test_cases"] == 12 and res["counts"]["test_clusters"] == 6
    assert res["arm5"]["n"] > 0 and "outcome_net" in res["arm5"]
    assert res["exposure"]["pooled"]["paraphrase_spread"]["max_range"] is not None


def test_sparse_cell_prints_k_over_n_with_dagger() -> None:
    r = prereg.rate([("c0", 1.0), ("c0", 0.0), ("c1", 1.0)])
    assert r["display"] == "2/3\u2020" and r["is_sparse"] and r["point_estimate"] == pytest.approx(2 / 3)
    ok = prereg.rate([(f"c{k}", float(k % 2)) for k in range(12)] * 2)
    assert ok["display"] == "50%" and ok["ci_lower"] is not None and not ok["is_sparse"]


def test_saved_file_specs_resolve() -> None:
    from suryabench.paths import resolve

    for name, item in FILES_SPEC.items():
        f = resolve(item["file"])
        if not f.exists():
            pytest.skip(f"{f} not present")
        render_macros({}, {name: item})
