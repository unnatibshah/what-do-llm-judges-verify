"""The locked oracle rule and paired contrasts used by the paper analysis."""

from suryabench.analysis.paper import classify_oracle_gap, paired_diff


def test_oracle_rule_ci_condition_overrides_point_estimate() -> None:
    assert classify_oracle_gap(0.10, -0.01, 0.20).startswith("Reasoning")  # 0 in CI despite +10 pp
    assert classify_oracle_gap(0.10, 0.03, 0.20) == "Retrieval Bottleneck Dominates"
    assert classify_oracle_gap(-0.10, -0.20, -0.04).startswith("Statutory Context Pathology")
    assert classify_oracle_gap(0.02, 0.01, 0.03).startswith("Reasoning")  # |delta| <= 2.5%


def test_paired_diff_uses_only_shared_pairs() -> None:
    a = [{"cluster": f"c{i % 3}", "v": 0.0, "pair": (i,)} for i in range(9)]
    b = [{"cluster": f"c{i % 3}", "v": 1.0, "pair": (i,)} for i in range(9)] + [{"cluster": "c9", "v": 0.0, "pair": (99,)}]
    d = paired_diff(a, b)
    assert d["n"] == 9 and d["delta"] == 1.0 and not d["sparse"]


def test_exposure_analysis_counts_commit_catch_survival_fpr_and_recovery() -> None:
    from suryabench.analysis.paper import analyse_exposure

    def rec(i: int, committed: bool, caught: bool, final_correct: bool, cond: str = "S-both") -> dict:
        eid = f"K-{i:03d}#exp-{cond}"
        return {"case_id": f"K-{i:03d}", "cluster_clause_id": f"c{i % 3}", "verifier_flags": ["F3:X#cl-1"] if caught else [],
                "fault_event_committed": {eid: committed}, "fault_event_committed_citation": {eid: committed},
                "fault_event_matches": {eid: caught} if committed else {},
                "fault_event_matches_class": {eid: caught} if committed else {},
                "avoided_trap_matches": {} if committed else {eid: caught},
                "nfo_matches": {}, "detected_faults": [],
                "raw": {"verifier": {"is_flagged": caught},
                        "recovery": {"flagged": caught, "initial_correct": not committed, "final_correct": final_correct,
                                     "initial_outcome_correct": not committed, "final_outcome_correct": final_correct}}}

    base = [rec(i, i < 6, False, i >= 6) for i in range(9)]  # 000: never catches
    real = [rec(i, i < 6, i < 4, i < 3 or i >= 6) for i in range(9)]  # reg-real: catches 4 of 6
    clean = [rec(i, False, i < 2, True, "C") for i in range(9)]  # 2 of 9 clean cases flagged
    runs = {("arm3", "S-both", True): base, ("reg_real", "S-both", True): real, ("reg_real", "C", True): clean}
    res = analyse_exposure(runs, cases={})
    assert res["commit"]["S-both+meta"]["primary"]["event_count"] == 6
    cell = res["cells"]["reg_real|S-both+meta"]
    assert (cell["sensitivity"]["event_count"], cell["sensitivity"]["total_opportunities"]) == (4, 6)
    assert cell["survival"]["event_count"] == 2  # committed and not caught
    fpr = res["fpr_clean"]["reg_real|C+meta"]
    assert (fpr["event_count"], fpr["total_opportunities"]) == (2, 9)
    t = res["contrasts"]["exploratory"]["reg-real vs 000, pooled S-both+J+A"]
    assert (t["n"], t["a_caught"], t["b_caught"], t["b_only"]) == (6, 0, 4, 4) and t["p"] == 0.125
    r = res["recovery"]["reg_real|S-both+meta"]
    assert (r["n"], r["flagged"], r["initial_wrong"], r["recovered"], r["initial_correct"], r["degraded"]) == (9, 4, 6, 3, 3, 0)
    assert r["outcome_net"] == 3 / 9
    assert "reg_real" in res["registry_curve"]["S-both+meta"]


def test_degenerate_interval_is_not_printed() -> None:
    from suryabench.analysis.paper import cell
    from suryabench.eval.evaluators import MetricWithCI

    m = MetricWithCI(point_estimate=1.0, ci_lower=1.0, ci_upper=1.0, event_count=8, total_opportunities=8,
                     n_clusters=3, is_sparse=False, formatted="")
    assert cell(m) == "8/8†"
