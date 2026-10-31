"""D49: the amendment-link audit table. Every link of the non-gold registry, with what the human check found.

No label is created here. Each row is one registry link (``registry_real_v2_r3.json``, link id = edge index, as
``seal_test_v3.py`` reads it). For the 52 links the annotators checked (18 used by the test items, 34 a seeded 20%
random sample of the other links, ``build_annotation_materials.py``), it adds both annotators' raw answers and the
adjudicated answer, unchanged. The other links stay ``not_checked``: their relation is the AI extractor's, provisional.

    PYTHONPATH=30_code/src python 30_code/scripts/build_link_audit.py     # writes 40_data/link_audit_v1/links.csv

``check`` validates the table (unique ids, known values, dates, documents in the corpus, no contradictory links) and
returns the problems; the build refuses to write a table with any.
"""

import csv
import json
import re
from pathlib import Path

from suryabench.paths import ANNOTATION_DIR, CORPUS_R3_DIR, DATA_DIR, REGISTRIES_DIR

OUT = DATA_DIR / "link_audit_v1" / "links.csv"
REGISTRY = REGISTRIES_DIR / "registry_real_v2_r3.json"
HUMAN = {"SUPERSEDED", "PARTIALLY_SUPERSEDED", "AMENDED", "NO_CHANGE", "UNCLEAR"}
AGENT = {"supersedes", "partially_supersedes", "amends"}
SAME = {"supersedes": "SUPERSEDED", "partially_supersedes": "PARTIALLY_SUPERSEDED", "amends": "AMENDED"}
FIELDS = ["link_id", "old_clause_id", "new_clause_id", "registry_relation", "registry_effective_date",
          "registry_confidence", "registry_quote", "checked_as", "a_relation", "b_relation", "adjudicated_relation",
          "adjudicated_effective_date", "adjudicated_wording", "decided_by", "outcome", "label_provenance"]


def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def outcome(registry_relation: str, adjudicated: str) -> str:
    if not adjudicated:
        return "not_checked"
    if adjudicated in {"NO_CHANGE", "UNCLEAR"}:
        return "not_a_link" if adjudicated == "NO_CHANGE" else "unclear"
    return "confirmed" if SAME[registry_relation] == adjudicated else "relation_changed"


def build() -> list[dict[str, str]]:
    edges = json.loads(REGISTRY.read_text(encoding="utf-8"))["edges"]
    key = {r["link_id"]: r for r in read(ANNOTATION_DIR / "LINKS_KEY_DO_NOT_SHARE.csv")}
    adj = {r["link_id"]: r for r in read(ANNOTATION_DIR / "adjudication" / "links_ADJUDICATED.csv")}
    raw = {s: {r["link_id"]: r for r in read(ANNOTATION_DIR / f"sheets_{s}" / f"links_{s}.csv")} for s in "AB"}
    rows = []
    for i, e in enumerate(edges):
        lid = f"L{i:03d}"
        a = adj.get(lid, {})
        rel = a.get("relation", "").strip().upper()
        rows.append({
            "link_id": lid, "old_clause_id": e["from_node"], "new_clause_id": e["to_node"],
            "registry_relation": e["type"], "registry_effective_date": e.get("effective_date") or "",
            "registry_confidence": str(e.get("confidence") or ""), "registry_quote": " ".join(str(e.get("evidence_quote") or "").split()),
            "checked_as": key[lid]["selected_as"] if lid in key else "not_checked",
            "a_relation": raw["A"].get(lid, {}).get("relation", ""), "b_relation": raw["B"].get(lid, {}).get("relation", ""),
            "adjudicated_relation": rel, "adjudicated_effective_date": a.get("effective_date", ""),
            "adjudicated_wording": a.get("wording", ""), "decided_by": a.get("decided_by", ""),
            "outcome": outcome(e["type"], rel),
            "label_provenance": "human (annotators, adjudicated)" if a else "AI extractor, provisional",
        })
    return rows


def check(rows: list[dict[str, str]], corpus_docs: set[str]) -> list[str]:
    problems = []
    ids = [r["link_id"] for r in rows]
    if len(set(ids)) != len(ids):
        problems.append("duplicate link ids")
    seen: dict[tuple[str, str], str] = {}
    for r in rows:
        lid = r["link_id"]
        if r["registry_relation"] not in AGENT:
            problems.append(f"{lid}: registry relation {r['registry_relation']!r}")
        if r["adjudicated_relation"] and r["adjudicated_relation"] not in HUMAN:
            problems.append(f"{lid}: adjudicated relation {r['adjudicated_relation']!r}")
        if bool(r["adjudicated_relation"]) != (r["checked_as"] != "not_checked"):
            problems.append(f"{lid}: checked_as {r['checked_as']} but adjudicated {r['adjudicated_relation']!r}")
        for f in ("registry_effective_date", "adjudicated_effective_date"):
            if r[f] and r[f] != "UNKNOWN" and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", r[f]):
                problems.append(f"{lid}: {f} {r[f]!r}")
        if r["old_clause_id"] == r["new_clause_id"]:
            problems.append(f"{lid}: links a clause to itself")
        for f in ("old_clause_id", "new_clause_id"):
            if r[f].split("#")[0] not in corpus_docs:
                problems.append(f"{lid}: {f} document not in the corpus")
        pair = (r["old_clause_id"], r["new_clause_id"])
        if pair in seen and seen[pair] != r["registry_relation"]:
            problems.append(f"{lid}: {pair} has two relations")
        seen[pair] = r["registry_relation"]
    return problems


def main() -> None:
    rows = build()
    docs = {d["doc_id"] for d in json.loads((CORPUS_R3_DIR / "MANIFEST.json").read_text(encoding="utf-8"))["documents"]}
    problems = check(rows, docs)
    if problems:
        raise SystemExit("not written:\n" + "\n".join(problems))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="\n") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    counts: dict[str, int] = {}
    for r in rows:
        counts[f"{r['checked_as']}/{r['outcome']}"] = counts.get(f"{r['checked_as']}/{r['outcome']}", 0) + 1
    print(f"{len(rows)} links, 0 problems -> {OUT.relative_to(DATA_DIR.parent)}")
    for k, v in sorted(counts.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
