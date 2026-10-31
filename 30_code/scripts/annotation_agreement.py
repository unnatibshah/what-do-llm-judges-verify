"""Cohen's kappa (with raw agreement and PABAK) between two annotators' filled sheets, and of each against the agent's
answer key.

Works for every sheet of 20_method/ANNOTATION-PACKET.md (v3), recognised by its columns:
- cases (Task 2, H-04): fields decision, blocking_stage, deciding_clauses (a ';'-separated set, compared as a set);
  the key is 20_method/annotation/ANSWER_KEY_DO_NOT_SHARE.csv; kappa on `decision` is also given per cluster.
- links (Task 1, H-03): fields new_clause_id, relation, effective_date, wording; the key is
  LINKS_KEY_DO_NOT_SHARE.csv, its registry link types mapped to the sheet's relations (supersedes -> SUPERSEDED,
  partially_supersedes -> PARTIALLY_SUPERSEDED, amends -> AMENDED) and its EXPLICIT/IMPLICIT tag to `wording` (P2-6).
- quotes (Task 3, H-06) and controls (Task 4, H-05): field decision (no key; each item is right by construction,
  so the CORRECT / SUBSTITUTION_TEXT share is reported per annotator).
- clauses (optional): fields doc_url_ok, quote_matches, effective_date, superseded_by, confidence (no key).
Free-text columns are not scored. Blank cells count as their own category ("") so a skipped item is a
disagreement, not a dropped row. Writes agreement.json and disagreements.csv to --out.

Usage:
  python annotation_agreement.py --a A.csv --b B.csv [--key ANSWER_KEY_DO_NOT_SHARE.csv] --out DIR
"""

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ID_COLS = ("item_id", "link_id", "case_id", "clause_id")
FIELDS = {"cases": ["decision", "blocking_stage", "deciding_clauses"],
          "links": ["new_clause_id", "relation", "effective_date", "wording"],
          "quotes": ["decision"], "controls": ["decision"],
          "clauses": ["doc_url_ok", "quote_matches", "effective_date", "superseded_by", "confidence"]}
SET_FIELDS = {"deciding_clauses", "superseded_by", "new_clause_id"}
UPPER = {"decision", "doc_url_ok", "quote_matches", "confidence", "relation", "wording"}
RELATION = {"supersedes": "SUPERSEDED", "partially_supersedes": "PARTIALLY_SUPERSEDED", "amends": "AMENDED"}
EXPECTED = {"quotes": "SUBSTITUTION_TEXT", "controls": "CORRECT"}


def norm(field: str, v: str | None) -> str:
    v = (v or "").strip()
    if field in SET_FIELDS:
        return ";".join(sorted({x.strip() for x in v.replace(",", ";").split(";") if x.strip()}))
    return v.upper() if field in UPPER else v


def kappa(x: list[str], y: list[str]) -> float | None:
    """Cohen's kappa for two label lists; None when undefined (no items, or chance agreement is 1)."""
    n = len(x)
    if n == 0:
        return None
    po = sum(a == b for a, b in zip(x, y, strict=True)) / n
    cx, cy = Counter(x), Counter(y)
    pe = sum(cx[k] * cy[k] for k in cx) / (n * n)
    return None if pe == 1 else round((po - pe) / (1 - pe), 4)


def pabak(x: list[str], y: list[str]) -> float | None:
    """Prevalence- and bias-adjusted kappa (D42): (k * p_o - 1) / (k - 1) over the k categories either rater used;
    with skewed labels and few clauses, kappa alone is unstable, so raw agreement, kappa and PABAK are reported."""
    k = len(set(x) | set(y))
    if not x or k < 2:
        return None
    po = sum(a == b for a, b in zip(x, y, strict=True)) / len(x)
    return round((k * po - 1) / (k - 1), 4)


def read(path: Path) -> tuple[str, dict[str, dict[str, str]]]:
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    id_col = next(c for c in ID_COLS if rows and c in rows[0])
    return id_col, {r[id_col]: r for r in rows}


def kind_of(row: dict[str, str]) -> str:
    """Which sheet a row comes from, by its columns."""
    if "quote_shown_at_R3" in row:
        return "quotes"
    if "answer_decision" in row:
        return "controls"
    if "relation" in row:
        return "links"
    return "cases" if "case_id" in row else "clauses"


def link_key(key: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    """LINKS_KEY_DO_NOT_SHARE.csv in the link sheet's vocabulary."""
    return {i: {"new_clause_id": r["new_clause_id"], "relation": RELATION.get(r["link_type"], r["link_type"]),
                "effective_date": r["effective_date"], "wording": r["explicit_implicit_agent"]} for i, r in key.items()}


def agreement(a: dict[str, dict[str, str]], b: dict[str, dict[str, str]], key: dict[str, dict[str, str]] | None,
              fields: list[str]) -> tuple[dict[str, object], list[list[str]]]:
    ids = sorted(set(a) & set(b) & (set(key) if key else set(a)))
    out: dict[str, object] = {"items": len(ids), "missing_in_b": sorted(set(a) - set(b)),
                              "missing_in_a": sorted(set(b) - set(a))}
    per: dict[str, dict[str, object]] = {}
    dis = []
    for f in fields:
        xa, xb = [norm(f, a[i].get(f)) for i in ids], [norm(f, b[i].get(f)) for i in ids]
        res: dict[str, object] = {"kappa_a_b": kappa(xa, xb), "pabak_a_b": pabak(xa, xb),
                                  "agreement_a_b": round(sum(p == q for p, q in zip(xa, xb, strict=True)) / len(ids), 4)
                                  if ids else None}
        if key is not None:
            xk = [norm(f, key[i].get(f)) for i in ids]
            res.update(kappa_a_key=kappa(xa, xk), kappa_b_key=kappa(xb, xk))
        per[f] = res
        for i, p, q in zip(ids, xa, xb, strict=True):
            k = norm(f, key[i].get(f)) if key is not None else ""
            if p != q or (key is not None and (p != k or q != k)):
                dis.append([i, f, p, q, k])
    out["fields"] = per
    if key is not None and "cluster_id" in next(iter(key.values()), {}):
        clusters: dict[str, list[str]] = defaultdict(list)
        for i in ids:
            clusters[key[i]["cluster_id"]].append(i)
        out["decision_by_cluster"] = {
            c: {"n": len(v), "kappa_a_b": kappa([norm("decision", a[i]["decision"]) for i in v],
                                                [norm("decision", b[i]["decision"]) for i in v])}
            for c, v in sorted(clusters.items())}
    return out, dis


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--a", type=Path, required=True)
    ap.add_argument("--b", type=Path, required=True)
    ap.add_argument("--key", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    id_col, a = read(args.a)
    _, b = read(args.b)
    key = read(args.key)[1] if args.key else None
    kind = kind_of(next(iter(a.values())))
    if kind == "links" and key is not None:
        key = link_key(key)
    result, dis = agreement(a, b, key if kind in {"cases", "links"} else None, FIELDS[kind])
    result["sheet"] = kind
    if kind in EXPECTED:
        result["share_" + EXPECTED[kind]] = {
            who: round(sum(norm("decision", r.get("decision")) == EXPECTED[kind] for r in rows.values()) / len(rows), 4)
            for who, rows in (("a", a), ("b", b)) if rows}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "agreement.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    with open(args.out / "disagreements.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow([id_col, "field", "annotator_a", "annotator_b", "agent_key"])
        w.writerows(dis)
    print(json.dumps(result["fields"], indent=1), f"\n{len(dis)} disagreements -> {args.out / 'disagreements.csv'}")


if __name__ == "__main__":
    main()
