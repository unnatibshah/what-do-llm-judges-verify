"""Precision and recall of the blind realistic registry against the gold supersession graph.

Nodes and edges are matched by normalised clause id (``verify_independent.norm_clause_id``: case,
punctuation and the ``cl-`` prefix ignored). Edges match on their (from, to) pair, and separately also on
kind (superseding vs amending: gold ``superseded_by``/``consolidated_into`` = registry ``supersedes``;
gold ``amended_by`` = registry ``partially_supersedes``; registry ``amends`` matches gold ``amended_by``
or ``clarified_by``). Whole-document supersessions are compared as sets of superseded documents.

    python 30_code/scripts/compare_registries.py                # corpus r3 -> registry_v2/compare_r3.json
    python 30_code/scripts/compare_registries.py --corpus r2    # the r2 result -> registry_v2/compare.json
The registry defaults to the one reg-real loads for that corpus (``runner.default_real_registry``).
"""

import argparse
import json
from typing import Any

from suryabench.arms.verify_independent import norm_clause_id
from suryabench.eval.runner import default_real_registry
from suryabench.paths import CORPORA, DEFAULT_CORPUS, RESULTS_DIR, corpus_dir, display, resolve

GOLD_KIND = {"superseded_by": "supersede", "consolidated_into": "supersede", "amended_by": "amend",
             "clarified_by": "amend"}
REAL_KIND = {"supersedes": "supersede", "partially_supersedes": "amend", "amends": "amend"}


def pr(found: set[Any], gold: set[Any]) -> dict[str, Any]:
    tp = len(found & gold)
    return {"registry": len(found), "gold": len(gold), "matched": tp,
            "precision": round(tp / len(found), 4) if found else None,
            "recall": round(tp / len(gold), 4) if gold else None}


def compare(gold: dict[str, Any], real: dict[str, Any]) -> dict[str, Any]:
    gold_nodes = {norm_clause_id(n) for n in gold["nodes"]}
    real_nodes = {norm_clause_id(n["node_id"]) for n in real["nodes"]}
    gold_pairs = {(norm_clause_id(e["from"]), norm_clause_id(e["to"])) for e in gold["edges"]}
    real_pairs = {(norm_clause_id(e["from_node"]), norm_clause_id(e["to_node"])) for e in real["edges"]}
    gold_typed = {p + (GOLD_KIND.get(e["relation"], e["relation"]),)
                  for e in gold["edges"] for p in [(norm_clause_id(e["from"]), norm_clause_id(e["to"]))]}
    real_typed = {p + (REAL_KIND.get(e["type"], e["type"]),)
                  for e in real["edges"] for p in [(norm_clause_id(e["from_node"]), norm_clause_id(e["to_node"]))]}
    gold_docs = set(gold.get("superseded_documents", {}))
    real_docs = {d["doc_from"] for d in real.get("document_supersessions", []) if "no_repeal" not in str(d.get("type"))}
    return {
        "nodes": pr(real_nodes, gold_nodes),
        "edges_pair": pr(real_pairs, gold_pairs),
        "edges_typed": pr(real_typed, gold_typed),
        "superseded_documents": pr(real_docs, gold_docs),
        "gold_edges_missed": sorted("->".join(p) for p in gold_pairs - real_pairs),
        "gold_nodes_missed": sorted(gold_nodes - real_nodes),
        "note": "Edge recall counts only clause-level edges; gold whole-document supersessions are compared "
                "separately. Ids are normalised, so a clause the registry numbered differently is a miss.",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=DEFAULT_CORPUS, choices=sorted(CORPORA))
    ap.add_argument("--gold", default=None, help="default: the corpus's gold supersession graph")
    ap.add_argument("--real", default=None, help="default: the registry reg-real loads for the corpus")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    real_default, warning = default_real_registry(args.corpus)
    args.gold = args.gold or str(corpus_dir(args.corpus) / "graph" / "supersession.json")
    args.real = args.real or str(real_default)
    args.out = args.out or str(RESULTS_DIR / "registry_v2" / ("compare.json" if args.corpus == "r2" else f"compare_{args.corpus}.json"))
    gold = json.loads(resolve(args.gold).read_text(encoding="utf-8"))
    real = json.loads(resolve(args.real).read_text(encoding="utf-8"))
    res = {"corpus": args.corpus, "gold": display(args.gold), "registry": display(args.real),
           **({"warning": warning} if warning and args.real == str(real_default) else {}), **compare(gold, real)}
    out = resolve(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: res[k] for k in ("nodes", "edges_pair", "edges_typed", "superseded_documents")}, indent=1))


if __name__ == "__main__":
    main()
