"""D49, exploratory: reply agreement between the main run and its same-machine repeat (fresh cache, temperature 0).

    PYTHONPATH=30_code/src python 30_code/scripts/compare_repeat.py     # -> probe_test_v3_repeat/agreement.json
"""

import json
from pathlib import Path

from suryabench.paths import RESULTS_DIR

MAIN, REPEAT = RESULTS_DIR / "probe_test_v3", RESULTS_DIR / "probe_test_v3_repeat"


def rows(model_dir: Path) -> dict[tuple[str, str], dict]:
    out = {}
    for f in sorted((model_dir / "blocks").glob("*.json")):
        b = json.loads(f.read_text(encoding="utf-8"))
        out.update({(b["config"], r["item_id"]): r for r in b["rows"]})
    return out


def main() -> None:
    res = {}
    for d in sorted(p for p in REPEAT.iterdir() if (p / "blocks").is_dir()):
        a, b = rows(MAIN / d.name), rows(d)
        common = [k for k in b if k in a]
        res[d.name] = {"items": len(common), "same_verdict": sum(a[k]["verdict"] == b[k]["verdict"] for k in common),
                       "same_findings": sum(a[k]["flags"] == b[k]["flags"] for k in common),
                       "same_scores": sum(all(a[k][f] == b[k][f] for f in ("right", "any", "clause")) for k in common)}
    (REPEAT / "agreement.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(res)


if __name__ == "__main__":
    main()
