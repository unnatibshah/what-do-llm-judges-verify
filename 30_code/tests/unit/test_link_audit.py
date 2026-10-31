"""D49: the link-audit table keeps the human answers unchanged and its validator catches broken rows."""

import sys

from suryabench.paths import CODE_DIR

sys.path.insert(0, str(CODE_DIR / "scripts"))
import build_link_audit as la  # noqa: E402


def test_table_and_validator() -> None:
    rows = la.build()
    docs = {r[f].split("#")[0] for r in rows for f in ("old_clause_id", "new_clause_id")}
    assert len(rows) == 186 and la.check(rows, docs) == []
    checked = [r for r in rows if r["checked_as"] != "not_checked"]
    assert len(checked) == 52 and all(r["label_provenance"].startswith("human") for r in checked)
    bad = [dict(rows[0], link_id=rows[1]["link_id"], adjudicated_relation="MAYBE", new_clause_id=rows[0]["old_clause_id"])]
    problems = la.check(bad + rows[1:], docs)
    assert any("duplicate" in p for p in problems) and any("MAYBE" in p for p in problems)
    assert any("itself" in p for p in problems)
