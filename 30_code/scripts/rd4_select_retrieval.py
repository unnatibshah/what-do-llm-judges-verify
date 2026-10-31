"""RD4: choose the retrieval stack on dev decisive-clause recall, never on the Gate 0 queries.

Procedure (00_tracking/decisions/DECISIONS.md, 2026-09-28; plan of 2026-09-29, RD4). The candidate
set and the selection rule below were fixed before this script was first run:

    candidates   1 dense            the Gate 0 stack (bge-m3 cosine, top 5)
                 2 dense+cap2       at most 2 chunks per document in the top 5
                 3 hybrid           dense + BM25, reciprocal rank fusion (k = 60)
                 4 hybrid+cap2      3 with the per-document cap
    metric       mean over the 60 dev cases of the share of the case's decisive clauses
                 (``applicable_rules``) held by a top-5 chunk (strict verbatim-span mapping), for the
                 generator's query (``application_query``)
    selection    the highest mean recall; a tie goes to the earlier (simpler) candidate

The chosen stack is then locked in ``suryabench.gate0.retriever.RD4_STACK`` and Gate 0 is re-run once
with the frozen 20 queries (``python -m suryabench.gate0.auditor --out-dir ...``).

Usage: python 30_code/scripts/rd4_select_retrieval.py
"""

import json

from suryabench.arms.arm1_rag import application_query
from suryabench.cases.schema import BenchmarkCase
from suryabench.corpus.manifest import load_manifest
from suryabench.gate0.retriever import LocalRetriever, build_corpus_chunks, map_chunks_to_clauses
from suryabench.graph.schema import SupersessionGraph
from suryabench.paths import BENCHMARK_DIR, CORPUS_DIR, RESULTS_DIR

CANDIDATES = {"dense": {}, "dense+cap2": {"per_doc_cap": 2}, "hybrid": {"hybrid": True},
              "hybrid+cap2": {"hybrid": True, "per_doc_cap": 2}}
OUT = RESULTS_DIR / "rd4_retrieval_selection" / "dev_recall.json"


def main() -> None:
    cases = [BenchmarkCase.model_validate(c)
             for c in json.loads((BENCHMARK_DIR / "dev_cases_60.json").read_text(encoding="utf-8"))]
    graph = SupersessionGraph.model_validate(
        json.loads((CORPUS_DIR / "graph" / "supersession.json").read_text(encoding="utf-8")))
    chunks = build_corpus_chunks(CORPUS_DIR / "text")
    clauses = map_chunks_to_clauses(chunks, graph.nodes.values(), CORPUS_DIR / "text")
    titles = {d.doc_id: d.title for d in load_manifest(CORPUS_DIR / "MANIFEST.json").documents}
    res: dict[str, dict[str, object]] = {}
    for name, opts in CANDIDATES.items():
        r = LocalRetriever(chunks, **opts)  # type: ignore[arg-type]
        r.index(cache_file=RESULTS_DIR / "embeddings_cache.json")
        r.chunk_clauses, r.doc_titles = clauses, titles
        per_case = {}
        for c in cases:
            got = set().union(*(clauses.get(x.chunk.chunk_id, set()) for x in r.retrieve(application_query(c), 5)))
            gold = [a.rule_id for a in c.applicable_rules]
            per_case[c.case_id] = sum(g in got for g in gold) / len(gold)
        res[name] = {"stack": r.describe(), "mean_recall": round(sum(per_case.values()) / len(per_case), 4),
                     "per_case": per_case}
        print(f"{name:12s} {r.describe():32s} dev decisive-clause recall@5 = {res[name]['mean_recall']:.4f}")
    best = max(CANDIDATES, key=lambda k: (res[k]["mean_recall"], -list(CANDIDATES).index(k)))
    print(f"selected: {best}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"selected": best, "candidates": res}, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
