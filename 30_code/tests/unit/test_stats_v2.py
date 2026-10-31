"""Tests for the D15 cluster-level statistics and the numbers.tex generator."""

import json
from pathlib import Path
from typing import Any

import pytest

from suryabench.analysis.numbers import main as numbers_main
from suryabench.analysis.numbers import render_macros
from suryabench.analysis.stats import (
    MAX_FAMILY,
    cluster_bootstrap_ci_checked,
    cluster_permutation_test,
    coprimary_improvement,
    holm_family,
    tost_equivalence,
)


def test_perm_exact_all_positive() -> None:
    r = cluster_permutation_test([[0.2], [0.3], [0.1], [0.4]])
    assert r.exact and r.n_clusters == 4
    assert r.p == pytest.approx(2 / 16)  # identity and its mirror
    assert r.observed == pytest.approx(0.25)


def test_perm_null_and_monte_carlo() -> None:
    r = cluster_permutation_test([[1.0, -1.0]] * 20, n_perm=2000, seed=1)
    assert not r.exact and r.p == 1.0  # all cluster means 0
    big = cluster_permutation_test({str(i): [0.3] for i in range(20)}, n_perm=2000, seed=1)
    assert big.p < 0.01


def test_perm_rejects_empty_cluster() -> None:
    with pytest.raises(ValueError):
        cluster_permutation_test([[0.1], []])


def _mean(rs: list[dict[str, Any]]) -> float:
    return sum(r["v"] for r in rs) / len(rs)


def test_bootstrap_checked_refuses() -> None:
    few = [{"c": i % 5, "v": float(i)} for i in range(50)]
    res, why = cluster_bootstrap_ci_checked(few, "c", _mean)
    assert res is None and why is not None and "5 clusters" in why
    const = [{"c": i % 12, "v": 1.0} for i in range(48)]
    res, why = cluster_bootstrap_ci_checked(const, "c", _mean)
    assert res is None and why is not None and "degenerate" in why
    ok = [{"c": i % 12, "v": float(i % 12)} for i in range(48)]
    res, why = cluster_bootstrap_ci_checked(ok, "c", _mean)
    assert res is not None and why is None


def test_tost() -> None:
    near0 = [[0.01], [-0.01], [0.0], [0.02], [-0.02], [0.01], [0.0], [-0.01], [0.01], [0.0]]
    assert tost_equivalence(near0, margin=0.1).equivalent
    shifted = [[0.3 + 0.01 * i] for i in range(10)]
    assert not tost_equivalence(shifted, margin=0.1).equivalent
    with pytest.raises(ValueError):
        tost_equivalence(near0, margin=0)


def test_holm_family() -> None:
    out = holm_family({"P1": 0.001, "P2": 0.02, "P3": 0.06})
    assert out["P1"]["reject"] and out["P1"]["p_holm"] == pytest.approx(0.003)
    assert not out["P3"]["reject"]
    with pytest.raises(ValueError):
        holm_family({f"P{i}": 0.1 for i in range(MAX_FAMILY + 1)})


def test_coprimary() -> None:
    sens = [[0.3]] * 12
    assert coprimary_improvement(sens, [[0.02]] * 12, n_perm=2000).improves
    bad = coprimary_improvement(sens, [[0.25]] * 12, n_perm=2000)
    assert bad.sens_significant and not bad.fpr_noninferior and not bad.improves
    assert not coprimary_improvement([[0.0]] * 12, [[0.0]] * 12, n_perm=2000).improves


def test_numbers(tmp_path: Path) -> None:
    res = {"a": {"sens": 0.1234, "arms": [{"n": 7}]}}
    spec = {
        "SensA": {"path": "a.sens", "fmt": ".1f", "scale": 100},
        "ArmN": "a.arms.0.n",
        "Pct": {"path": "a.sens", "fmt": ".0%"},
    }
    tex = render_macros(res, spec)
    assert r"\newcommand{\SensA}{12.3}" in tex and r"\newcommand{\ArmN}{7}" in tex
    assert r"\newcommand{\Pct}{12\%}" in tex
    with pytest.raises(KeyError):
        render_macros(res, {"Bad": "a.missing"})
    with pytest.raises(ValueError):
        render_macros(res, {"Sens1": "a.sens"})
    r, s, o = tmp_path / "r.json", tmp_path / "s.json", tmp_path / "n.tex"
    r.write_text(json.dumps(res))
    s.write_text(json.dumps(spec))
    numbers_main(["--results", str(r), "--spec", str(s), "--out", str(o)])
    assert o.read_text().count("newcommand") == 3
