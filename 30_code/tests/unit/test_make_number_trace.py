"""make_number_trace.py: every macro in the committed numbers.tex has a source file and key (T11, U6)."""

import importlib.util

from suryabench import paths

_spec = importlib.util.spec_from_file_location("make_number_trace", paths.CODE_DIR / "scripts" / "make_number_trace.py")
assert _spec and _spec.loader
nt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nt)


def test_every_macro_is_traced() -> None:
    rows = nt.trace(nt.NUMBERS, "L.json", str(nt.mn.MANIFEST.relative_to(paths.ROOT)), "A")
    assert len(rows) > 1000 and not [r["macro"] for r in rows if r["source_file"] == "UNMAPPED"]
    by = {r["macro"]: r for r in rows}
    assert by["NClausesSBoth"]["key"] == "distinct_planted_clauses_by_condition[S-both]"
    assert by["CatchQwenFourteenRTwo"]["key"] == "models[qwen2.5:14b][R2].catch.mean"
    assert by["KappaCasesDecision"]["source_file"] == "A/cases/agreement.json"
    assert "textcolor" not in by["CatchQwenFourteenRTwo"]["value"]
