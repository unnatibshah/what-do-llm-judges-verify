"""D45: split the annotation between the two annotators, check the R3 quotes by string match, and merge the filled
sheets into a draft for the adjudicator.

Every link, case and control is checked by at least one person; a seeded shared subset is checked by both and gives
the agreement numbers (PREREGISTRATION_v3 section 3). The split is fixed before annotation starts.

- Links (Task 1): 15 shared, stratified 5 test-used / 10 sampled (18 of 52 links are used by test pairs); the other
  37 alternate between A and B.
- Cases (Task 2): 20 shared; the other 40 split 20 / 20.
- Controls (Task 4): each goes to the annotator who labelled its case; controls on shared cases fill the two sides to
  20 / 20.
- R3 quotes (Task 3): annotator B only, after the agent's string match (``quotes``).

    python 30_code/scripts/annotation_split.py split    # writes sheets_A/, sheets_B/, ASSIGNMENT_D45.csv
    python 30_code/scripts/annotation_split.py quotes   # writes r3_quotes_stringmatch.csv
    python 30_code/scripts/annotation_split.py merge    # after both submit: writes adjudication/ for Unnati
"""

import argparse
import csv
import random
import re
from pathlib import Path

from suryabench.paths import ANNOTATION_DIR, CORPUS_R3_DIR

SEED = 45
N_SHARED_LINKS, N_SHARED_LINKS_TEST, N_SHARED_CASES = 15, 5, 20
SHEETS = {"links": ("links_to_verify.csv", "link_id"), "cases": ("cases_to_label.csv", "case_id"),
          "controls": ("controls_check.csv", "item_id")}
# The columns seal_test_v3.py reads, per sheet; the shared items must agree on all of them.
SEAL_FIELDS = {"links": ["relation", "effective_date", "substitution_quote", "wording"],
               "cases": ["decision", "blocking_stage", "deciding_clauses"], "controls": ["decision"]}


def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, header, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def alternate(ids: list[str]) -> dict[str, str]:
    return {i: "AB"[n % 2] for n, i in enumerate(ids)}


def assign(link_ids: list[str], test_links: set[str], case_ids: list[str],
           control_cases: dict[str, str]) -> dict[str, dict[str, str]]:
    """Item id -> "A", "B" or "AB" per sheet. Deterministic for a given seed and input order."""
    rng = random.Random(SEED)
    test = [i for i in link_ids if i in test_links]
    rest = [i for i in link_ids if i not in test_links]
    shared = set(rng.sample(test, N_SHARED_LINKS_TEST) + rng.sample(rest, N_SHARED_LINKS - N_SHARED_LINKS_TEST))
    single = [i for i in link_ids if i not in shared]
    rng.shuffle(single)
    links = {**alternate(single), **{i: "AB" for i in shared}}

    shared_cases = set(rng.sample(case_ids, N_SHARED_CASES))
    single = [i for i in case_ids if i not in shared_cases]
    rng.shuffle(single)
    cases = {**alternate(single), **{i: "AB" for i in shared_cases}}

    controls = {i: cases[c] for i, c in control_cases.items() if cases[c] != "AB"}
    half = len(control_cases) // 2
    for i in sorted(i for i in control_cases if i not in controls):
        controls[i] = "A" if sum(v == "A" for v in controls.values()) < half else "B"
    return {"links": links, "cases": cases, "controls": controls}


def split(adir: Path) -> None:
    rows = {k: read(adir / f) for k, (f, _) in SHEETS.items()}
    test_links = {r["link_id"] for r in read(adir / "LINKS_KEY_DO_NOT_SHARE.csv") if r["cited_by_test_pairs"].strip()}
    plan = assign([r["link_id"] for r in rows["links"]], test_links, [r["case_id"] for r in rows["cases"]],
                  {r["item_id"]: r["case_id"] for r in rows["controls"]})
    out = []
    for sheet, (_, id_col) in SHEETS.items():
        header = list(rows[sheet][0])
        for who in "AB":
            write(adir / f"sheets_{who}" / f"{sheet}_{who}.csv", header,
                  [r for r in rows[sheet] if who in plan[sheet][r[id_col]]])
        out += [{"sheet": sheet, "item_id": i, "annotator": w} for i, w in plan[sheet].items()]
    quotes = read(adir / "r3_quotes_check.csv")
    write(adir / "sheets_B" / "r3_quotes_B.csv", list(quotes[0]), quotes)
    write(adir / "ASSIGNMENT_D45.csv", ["sheet", "item_id", "annotator"], sorted(out, key=lambda r: (r["sheet"], r["item_id"])))
    for sheet, p in plan.items():
        print(sheet, {w: sum(v == w for v in p.values()) for w in ("A", "B", "AB")})


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def quotes(adir: Path) -> None:
    """Is each R3 quote, verbatim up to whitespace and case, in the amending document's saved text?
    For a miss, the share of the quote's 8-word windows found there tells a typo from a wrong quote."""
    newer = {r["link_id"]: r["newer_doc_id"] for r in read(adir / "links_to_verify.csv")}
    out = []
    for q in read(adir / "r3_quotes_check.csv"):
        doc = newer[q["link_id"]]
        text = norm((CORPUS_R3_DIR / "text" / f"{doc}.txt").read_text(encoding="utf-8"))
        quote = norm(q["quote_shown_at_R3"])
        words = quote.split()
        windows = [" ".join(words[i:i + 8]) for i in range(max(1, len(words) - 7))]
        share = sum(w in text for w in windows) / len(windows)
        out.append({"link_id": q["link_id"], "newer_doc_id": doc, "verbatim": "Y" if quote in text else "N",
                    "share_of_8word_windows_found": f"{share:.2f}"})
    write(adir / "r3_quotes_stringmatch.csv", list(out[0]), out)
    print(sum(r["verbatim"] == "Y" for r in out), "of", len(out), "quotes verbatim in their document")


def same_answer(field: str, x: str, y: str) -> bool:
    """Equal up to whitespace and case; a clause list is compared as a set, as seal_test_v3.py reads it."""
    if field == "deciding_clauses":
        return {norm(c) for c in re.split(r"[;,]", x) if c.strip()} == {norm(c) for c in re.split(r"[;,]", y) if c.strip()}
    return norm(x) == norm(y)


def merge(adir: Path, out: Path) -> None:
    """Union of the filled sheets in the format seal_test_v3.py reads. Shared items that agree are taken; shared items
    that disagree are left blank with decided_by=ADJUDICATE and both answers in a_/b_ columns for Unnati."""
    for sheet, (_, id_col) in SHEETS.items():
        a = {r[id_col]: r for r in read(adir / "sheets_A" / f"{sheet}_A.csv")}
        b = {r[id_col]: r for r in read(adir / "sheets_B" / f"{sheet}_B.csv")}
        fields = SEAL_FIELDS[sheet]
        rows = []
        for i in sorted(set(a) | set(b)):
            if i in a and i in b:
                same = all(same_answer(f, a[i].get(f, ""), b[i].get(f, "")) for f in fields)
                row = {f: a[i][f] if same else "" for f in fields}
                row["decided_by"] = "A+B" if same else "ADJUDICATE"
                if not same:
                    row |= {f"a_{f}": a[i].get(f, "") for f in fields} | {f"b_{f}": b[i].get(f, "") for f in fields}
            else:
                src, who = (a, "A") if i in a else (b, "B")
                row = {f: src[i].get(f, "") for f in fields} | {"decided_by": who}
            rows.append({id_col: i, **row})
        name = {"links": "links_ADJUDICATED.csv", "cases": "cases_ADJUDICATED.csv", "controls": "controls_check.csv"}
        write(out / name[sheet], [id_col, *fields, "decided_by", *[f"{w}_{f}" for w in "ab" for f in fields]], rows)
        print(sheet, sum(r["decided_by"] == "ADJUDICATE" for r in rows), "to adjudicate of", len(rows))
    q = read(adir / "sheets_B" / "r3_quotes_B.csv")
    write(out / "r3_quotes_check.csv", ["link_id", "decision", "decided_by"], [{**r, "decided_by": "B"} for r in q])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["split", "quotes", "merge"])
    ap.add_argument("--dir", type=Path, default=ANNOTATION_DIR)
    ap.add_argument("--out", type=Path, default=ANNOTATION_DIR / "adjudication")
    args = ap.parse_args()
    if args.cmd == "split":
        split(args.dir)
    elif args.cmd == "quotes":
        quotes(args.dir)
    else:
        merge(args.dir, args.out)


if __name__ == "__main__":
    main()
