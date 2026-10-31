"""D49: tables come from the result files, with S-both-only confusion counts."""

import sys

from suryabench.paths import CODE_DIR

sys.path.insert(0, str(CODE_DIR / "scripts"))
import make_tables_v3 as mt  # noqa: E402


def test_main_table_counts_and_empty_input() -> None:
    assert mt.main_table({}) == [] and mt.provenance_table({}, {}, {}) == []
    cell = {"catch_sboth": {"k": 9, "n": 12}, "false_alarm_sboth": {"k": 3, "n": 12}, "false_alarm_C": {"k": 1, "n": 10}}
    lad = {"models": {"qwen2.5:14b": {"R2": cell}},
           "discrimination": {"R2 @ qwen2.5:14b": {"mean_diff": 0.5, "ci95": [0.2, 0.7], "clauses": 12}}}
    row = [r for r in mt.main_table(lad) if r.startswith("Qwen 14B")][0]
    assert mt.disc_key("R4n-drop50", "m") == "R4n drop50 @ m" and mt.disc_key("R4", "m") == "R4 intact @ m"
    assert "& 9 & 3 & 3 & 9 & 75 & 75 & 75 & 75 & 1/10 & +50 [+20, +70] & 12" in row


def test_generated_tables_have_no_broken_percent() -> None:
    """A doubled backslash before % is a line break plus a comment in LaTeX: it silently eats the rest of a caption."""
    from suryabench.paths import ROOT
    for f in (ROOT / "60_paper_drafts" / "paper_v3" / "generated").glob("tab_*.tex"):
        assert "\\\\%" not in f.read_text(encoding="utf-8"), f.name
