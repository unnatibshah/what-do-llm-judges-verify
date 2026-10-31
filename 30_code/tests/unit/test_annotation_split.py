"""D45 annotation split: every item checked by at least one annotator, the shared subset as preregistered."""

import importlib.util

from suryabench.paths import ROOT

spec = importlib.util.spec_from_file_location("annotation_split", ROOT / "30_code/scripts/annotation_split.py")
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_split_covers_everything_with_preregistered_shares() -> None:
    links = [f"L{i:03d}" for i in range(52)]
    cases = [f"C{i:02d}" for i in range(60)]
    controls = {f"K{i:02d}": cases[i % 36] for i in range(40)}
    plan = mod.assign(links, set(links[:18]), cases, controls)
    assert set(plan["links"]) == set(links) and set(plan["cases"]) == set(cases) and set(plan["controls"]) == set(controls)
    shared = [i for i, w in plan["links"].items() if w == "AB"]
    assert len(shared) == 15 and sum(i in links[:18] for i in shared) == 5
    assert sorted(plan["cases"].values()).count("AB") == 20
    assert {w: list(plan["cases"].values()).count(w) for w in "AB"} == {"A": 20, "B": 20}
    assert sorted(plan["controls"].values()).count("A") == 20
    assert plan == mod.assign(links, set(links[:18]), cases, controls)  # seeded


def test_merge_compares_clause_lists_as_sets() -> None:
    assert mod.same_answer("deciding_clauses", "X#1; Y#2", "y#2,X#1")
    assert not mod.same_answer("deciding_clauses", "X#1", "X#1;Y#2")
    assert not mod.same_answer("decision", "APPROVED", "REJECTED")
