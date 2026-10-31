"""T8: apply the adjudicated annotation, validate, and seal the v3 test split.

Inputs, in ``--adjudicated`` (default ``20_method/annotation/``), written by the adjudicator. Each one is the
annotators' sheet with the agreed answer and a ``decided_by`` column:
- ``cases_ADJUDICATED.csv``: ``case_id, decision, blocking_stage, deciding_clauses, decided_by``.
- ``links_ADJUDICATED.csv``: ``link_id, relation, effective_date, substitution_quote, wording, decided_by``.
- ``controls_check.csv`` and ``r3_quotes_check.csv``: the adjudicated copies, with ``decision`` filled.
``annotation_split.py merge`` writes all four as a draft; the adjudicator fills each row marked ``decided_by=ADJUDICATE``
and changes that mark (e.g. to ``Unnati``). A row still marked ADJUDICATE, or with a blank decision or relation, blocks
the seal.

Rules (ANNOTATION-PACKET "After both submit", PREREGISTRATION_v3 section 3, as changed by amendment 2, D49):
- A case whose decision differs from the key is dropped. Relabelling would change the probe's planted items, so a
  corrected case is not reused. A rejected case whose blocking stage differs is dropped too. Since D49 a case whose
  deciding clauses alone differ is kept and listed in ``clause_disputed``; ``strict_dropped`` lists every case v3's
  rule would have dropped (sensitivity analysis S2).
- A link adjudicated NO_CHANGE or UNCLEAR is removed from the registry. A corrected effective date replaces the
  agent's. A non-SUBSTITUTION_TEXT R3 quote is replaced by the adjudicated ``substitution_quote``. Any change writes
  ``registry_real_v3.json``; otherwise the run keeps ``registry_real_v2_r3.json``.
- A replaced clause is dropped, with all its cases, when every registry link the key ties it to
  (``planted:<clause>`` in ``cited_by_test_pairs``) is rejected. Clauses with no link (NONE) rest on the case labels.
- Since D49 the controls check no longer blocks the seal: its CORRECT rate is reported, and the cases whose checked
  control was judged anything but CORRECT are listed in ``controls_flagged`` (sensitivity analysis S1).
- Fewer than 10 distinct replaced clauses: the seal still runs, and the manifest says no primary claim (stop rule 1).

    python 30_code/scripts/seal_test_v3.py --dry-run          # the agent key as a stand-in adjudication, to scratch
    python 30_code/scripts/seal_test_v3.py                    # the real seal (after adjudication)
"""

import argparse
import csv
import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

from suryabench.core.guard import TEST_HASHES_FILE, case_content_hash
from suryabench.paths import ANNOTATION_DIR, BENCHMARK_DIR, REGISTRIES_DIR, ROOT, resolve

CANDIDATE = BENCHMARK_DIR / "test_cases_v3_CANDIDATE.json"
CAND_MANIFEST = resolve("50_analysis/results/ladder_design/candidate_v3_manifest.json")
REGISTRY_V2 = REGISTRIES_DIR / "registry_real_v2_r3.json"
NOT_A_LINK = {"NO_CHANGE", "UNCLEAR"}
MIN_CLAUSES = 10


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def clauses(s: str) -> frozenset[str]:
    return frozenset(c.strip() for c in s.replace(",", ";").split(";") if c.strip())


def stand_in(adj: Path) -> None:
    """Dry run: write the agent's keys as if they were the adjudicated answers (everything kept)."""
    def write(name: str, header: list[str], rows: list[list[str]]) -> None:
        with (adj / name).open("w", encoding="utf-8", newline="\n") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(header)
            w.writerows(rows)

    key = read(ANNOTATION_DIR / "ANSWER_KEY_DO_NOT_SHARE.csv")
    write("cases_ADJUDICATED.csv", ["case_id", "decision", "blocking_stage", "deciding_clauses", "decided_by"],
          [[k["case_id"], k["decision"], k["blocking_stage"], k["deciding_clauses"], "dry-run"] for k in key])
    links = read(ANNOTATION_DIR / "LINKS_KEY_DO_NOT_SHARE.csv")
    write("links_ADJUDICATED.csv", ["link_id", "relation", "effective_date", "substitution_quote", "wording", "decided_by"],
          [[k["link_id"], "SUPERSEDED", k["effective_date"], k["quote"], k["explicit_implicit_agent"], "dry-run"]
           for k in links])
    ctrl = read(ANNOTATION_DIR / "controls_check.csv")
    write("controls_check.csv", ["item_id", "decision"], [[c["item_id"], "CORRECT"] for c in ctrl])
    quotes = read(ANNOTATION_DIR / "r3_quotes_check.csv")
    write("r3_quotes_check.csv", ["link_id", "decision"], [[q["link_id"], "SUBSTITUTION_TEXT"] for q in quotes])


def seal(adj: Path, out: Path, dry_run: bool) -> dict[str, Any]:
    cases = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    cmanifest = json.loads(CAND_MANIFEST.read_text(encoding="utf-8"))
    clause_of = {cid: r["clause"] for r in cmanifest["replaced_clauses"] for cid in r["cases"]}
    key = {k["case_id"]: k for k in read(ANNOTATION_DIR / "ANSWER_KEY_DO_NOT_SHARE.csv")}
    links_key = {k["link_id"]: k for k in read(ANNOTATION_DIR / "LINKS_KEY_DO_NOT_SHARE.csv")}
    adj_cases = {a["case_id"]: a for a in read(adj / "cases_ADJUDICATED.csv")}
    adj_links = {a["link_id"]: a for a in read(adj / "links_ADJUDICATED.csv")}
    problems: list[str] = []

    # a merge draft (annotation_split.py merge) leaves disagreements blank and marked ADJUDICATE; sealing it would
    # read a blank decision as a label change and drop the case, so every such row must be resolved first
    for name in ("cases_ADJUDICATED.csv", "links_ADJUDICATED.csv", "controls_check.csv", "r3_quotes_check.csv"):
        problems += [f"{name}: {next(iter(r.values()))} still marked ADJUDICATE" for r in read(adj / name)
                     if (r.get("decided_by") or "").strip().upper() == "ADJUDICATE"]
    problems += [f"case {cid} has no decision" for cid, a in adj_cases.items() if not a["decision"].strip()]
    problems += [f"link {lid} has no relation" for lid, a in adj_links.items() if not a["relation"].strip()]

    # every case and every link the test pairs use must be adjudicated
    problems += [f"case {c['case_id']} not adjudicated" for c in cases if c["case_id"] not in adj_cases]
    problems += [f"link {lid} (used by test pairs) not adjudicated" for lid, k in links_key.items()
                 if k["cited_by_test_pairs"] and lid not in adj_links]

    dropped: dict[str, str] = {}
    disputed: dict[str, str] = {}  # D49: kept; dropped under v3's rule
    for cid, a in adj_cases.items():
        k = key.get(cid)
        if k is None:
            problems.append(f"adjudicated case {cid} is not in the candidate")
        elif a["decision"].strip().upper() != k["decision"]:
            dropped[cid] = f"decision {k['decision']} -> {a['decision']}"
        elif k["decision"] == "REJECTED" and a["blocking_stage"].strip().lower() != k["blocking_stage"].lower():
            dropped[cid] = f"blocking stage {k['blocking_stage']} -> {a['blocking_stage']}"
        elif clauses(a["deciding_clauses"]) != clauses(k["deciding_clauses"]):
            disputed[cid] = f"deciding clauses {k['deciding_clauses']} -> {a['deciding_clauses']}"

    # registry: remove rejected links, apply corrected dates and quotes
    registry = json.loads(REGISTRY_V2.read_text(encoding="utf-8"))
    edges = registry["edges"]
    quotes_bad = {q["link_id"] for q in read(adj / "r3_quotes_check.csv") if q["decision"] != "SUBSTITUTION_TEXT"}
    changes: list[str] = []
    removed: set[int] = set()
    for lid, a in adj_links.items():
        i, e = int(lid[1:]), edges[int(lid[1:])]
        if a["relation"].strip().upper() in NOT_A_LINK:
            removed.add(i)
            changes.append(f"{lid} removed ({e['from_node']} -> {e['to_node']}: {a['relation']})")
            continue
        date = a["effective_date"].strip()
        if date and date != "UNKNOWN" and date != e.get("effective_date"):
            changes.append(f"{lid} effective date {e.get('effective_date')} -> {date}")
            e["effective_date"] = date
        if lid in quotes_bad and a["substitution_quote"].strip():
            changes.append(f"{lid} R3 quote replaced")
            e["evidence_quote"] = a["substitution_quote"].strip()
    registry["edges"] = [e for i, e in enumerate(edges) if i not in removed]
    planted: dict[str, set[int]] = {}  # replaced clause -> the registry links the key ties it to
    for lid, k in links_key.items():
        for tok in k["cited_by_test_pairs"].split(";"):
            if tok.startswith("planted:"):
                planted.setdefault(tok.removeprefix("planted:"), set()).add(int(lid[1:]))
    rejected = {cl for cl, ls in planted.items() if ls <= removed}
    for c in cases:
        if clause_of.get(c["case_id"]) in rejected and c["case_id"] not in dropped:
            dropped[c["case_id"]] = f"replaced clause {clause_of[c['case_id']]}: every link it relies on was rejected"

    ctrl = read(adj / "controls_check.csv")
    ctrl_ok = sum(c["decision"] == "CORRECT" for c in ctrl) / len(ctrl) if ctrl else 0.0
    problems += [f"control {c['item_id']} has no decision" for c in ctrl if not c["decision"].strip()]
    flagged = {c["item_id"].split("#")[0]: c["decision"] for c in ctrl if c["decision"] != "CORRECT"}

    sealed = [c for c in cases if c["case_id"] not in dropped]
    ids = [c["case_id"] for c in sealed]
    hashes = [case_content_hash(c) for c in sealed]
    if len(set(ids)) != len(ids) or len(set(hashes)) != len(hashes):
        problems.append("duplicate case id or content")
    n_clauses = len({clause_of[c] for c in ids})

    out.mkdir(parents=True, exist_ok=True)
    reg_file = REGISTRY_V2
    if changes:
        reg_file = out / "registry_real_v3.json" if dry_run else REGISTRIES_DIR / "registry_real_v3.json"
        reg_file.write_text(json.dumps(registry, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    kept = {c["case_id"] for c in cases} - set(dropped)
    report = {"dropped_cases": dropped, "registry_changes": changes, "controls_correct": round(ctrl_ok, 4),
              "controls_checked": len(ctrl),
              "clause_disputed": {c: v for c, v in disputed.items() if c in kept},
              "controls_flagged": {c: v for c, v in flagged.items() if c in kept},
              "strict_dropped": sorted(set(dropped) | set(disputed)), "problems": problems}
    if problems:
        return report

    test = out / "test_cases_v3.json"
    if test.exists():
        test.chmod(stat.S_IWUSR | stat.S_IRUSR)
    test.write_text(json.dumps(sealed, indent=2), encoding="utf-8", newline="\n")  # as build_test_candidate_v3
    digest = sha256(test)
    (out / "test_cases_v3.sha256").write_text(f"{digest}  test_cases_v3.json\n", encoding="utf-8", newline="\n")
    manifest = {
        "file": "test_cases_v3.json", "sha256": digest, "sealed": not dry_run, "n_cases": len(sealed),
        "distinct_replaced_clauses": n_clauses, "primary_claim_allowed": n_clauses >= MIN_CLAUSES,
        "candidate_sha256": sha256(CANDIDATE), "registry": reg_file.name, "registry_sha256": sha256(reg_file),
        **report,
    }
    (out / "TEST_MANIFEST_v3.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8", newline="\n")
    if not dry_run:
        old = json.loads(TEST_HASHES_FILE.read_text(encoding="utf-8")) if TEST_HASHES_FILE.exists() else []
        TEST_HASHES_FILE.write_text(json.dumps(sorted(set(old) | set(hashes)), indent=1) + "\n",
                                    encoding="utf-8", newline="\n")
        test.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adjudicated", default=str(ANNOTATION_DIR))
    ap.add_argument("--dry-run", action="store_true", help="stand-in adjudication (the agent key) into a scratch folder")
    args = ap.parse_args()
    if args.dry_run:
        base = Path(tempfile.mkdtemp(prefix="seal_v3_dry_"))
        adj, out = base / "adjudicated", base / "out"
        adj.mkdir()
        stand_in(adj)
    else:
        adj, out = Path(args.adjudicated), BENCHMARK_DIR
    result = seal(adj, out, args.dry_run)
    print(json.dumps({k: v for k, v in result.items() if k != "dropped_cases"} | {"dropped": len(result["dropped_cases"])},
                     indent=1))
    if result["problems"]:
        raise SystemExit("not sealed: " + "; ".join(result["problems"]))
    where = os.path.relpath(out, ROOT) if out.is_relative_to(ROOT) else str(out)
    print(f"{'dry run' if args.dry_run else 'sealed'}: {where}/test_cases_v3.json")
    if not args.dry_run:
        print("next: git add, commit, `git tag test-seal-v3`, push the tag; fill the fingerprint into PREREGISTRATION_v3")


if __name__ == "__main__":
    main()
