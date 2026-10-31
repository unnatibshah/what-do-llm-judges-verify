"""T4 (P3-11): how often does the generator's own retrieval return a replaced clause without its replacement?

No LLM is run. For every case of the candidate v3 split (and of dev, for comparison) the generator's query
(``arm1_rag.application_query``, built from the application only) goes to the RD4 retriever (dense + BM25,
per-document cap), top 5 as the generator uses. A retrieved clause is "replaced" when the gold graph says it is
superseded (or partially) at the case date; it is "without its replacement" when no clause it was superseded by is
in the same top 5. Reported per case: any replaced clause retrieved; any retrieved without its replacement. 95%
bootstrap over rule groups (``stats.cluster_bootstrap_ci_checked``). The case files are read for their application
text only; only the embedding model sees the query.

Output: 50_analysis/results/ladder_design/retrieval_old_without_new.json

Usage (repository root; Ollama up and otherwise idle: a query embedding times out behind a long generation):
    PYTHONPATH=30_code/src:30_code/scripts python 30_code/scripts/retrieval_old_without_new.py
"""

import json
from collections import Counter
from typing import Any

import numpy as np

from suryabench.analysis.stats import cluster_bootstrap_ci_checked
from suryabench.arms.arm1_rag import application_query
from suryabench.cases.schema import BenchmarkCase
from suryabench.core.enums import CurrencyVerdict, EdgeRelation
from suryabench.corpus.manifest import load_manifest
from suryabench.gate0.retriever import (
    RD4_HYBRID,
    RD4_PER_DOC_CAP,
    LocalRetriever,
    build_corpus_chunks,
    map_chunks_to_clauses,
)
from suryabench.graph.oracle import in_force
from suryabench.graph.schema import SupersessionGraph
from suryabench.paths import BENCHMARK_DIR, RESULTS_DIR, corpus_dir, embeddings_cache

OUT = RESULTS_DIR / "ladder_design" / "retrieval_old_without_new.json"
TOP_K = 5  # arm2_agent / arm1_rag default
SPLITS = {"v3_candidate": "test_cases_v3_CANDIDATE.json", "dev": "dev_cases_v2.json"}
STALE = {CurrencyVerdict.SUPERSEDED, CurrencyVerdict.PARTIALLY_SUPERSEDED}


def retriever_r3() -> tuple[LocalRetriever, SupersessionGraph]:
    d = corpus_dir("r3")
    graph = SupersessionGraph.model_validate(json.loads((d / "graph" / "supersession.json").read_text(encoding="utf-8")))
    chunks = build_corpus_chunks(d / "text")
    r = LocalRetriever(chunks, hybrid=RD4_HYBRID, per_doc_cap=RD4_PER_DOC_CAP)
    r.index(cache_file=embeddings_cache(d))
    assert len(r.embeddings) == len(chunks), "dense index incomplete"
    r.chunk_clauses = map_chunks_to_clauses(chunks, graph.nodes.values(), d / "text")
    r.doc_titles = {m.doc_id: m.title for m in load_manifest(d / "MANIFEST.json").documents}
    return r, graph


def per_case(case: BenchmarkCase, r: LocalRetriever, graph: SupersessionGraph) -> dict[str, Any]:
    hits = r.retrieve(application_query(case), top_k=TOP_K)
    shown = set().union(*(r.chunk_clauses.get(h.chunk.chunk_id, set()) for h in hits)) if hits else set()
    date = str(case.facts.case_date)
    successors: dict[str, set[str]] = {}
    for e in graph.edges:
        if e.relation in {EdgeRelation.SUPERSEDED_BY, EdgeRelation.AMENDED_BY}:
            successors.setdefault(e.from_node, set()).add(e.to_node)
    replaced = sorted(c for c in shown if c in graph.nodes and in_force(c, date, graph) in STALE)
    alone = sorted(c for c in replaced if not successors.get(c, set()) & shown)
    return {"case_id": case.case_id, "group": str(case.cluster_id), "replaced": replaced, "without_replacement": alone,
            "any_replaced": bool(replaced), "any_alone": bool(alone)}


def summary(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    ci, why = cluster_bootstrap_ci_checked(rows, "group", lambda rs: float(np.mean([r[key] for r in rs])))
    return {"k": sum(r[key] for r in rows), "n": len(rows), "rate": round(float(np.mean([r[key] for r in rows])), 4),
            "ci95_over_groups": [round(ci.ci_lower, 4), round(ci.ci_upper, 4)] if ci else None, "ci_refused": why,
            "groups": len({r["group"] for r in rows})}


def main() -> None:
    r, graph = retriever_r3()
    result: dict[str, Any] = {"top_k": TOP_K, "query": "arm1_rag.application_query (application facsimiles only)",
                              "retriever": f"RD4 hybrid={RD4_HYBRID} per_doc_cap={RD4_PER_DOC_CAP}"}
    for name, file in SPLITS.items():
        cases = [BenchmarkCase.model_validate(c) for c in json.loads((BENCHMARK_DIR / file).read_text(encoding="utf-8"))]
        rows = [per_case(c, r, graph) for c in cases]
        result[name] = {"cases": len(rows), "any_replaced_retrieved": summary(rows, "any_replaced"),
                        "replaced_without_replacement": summary(rows, "any_alone"),
                        "replaced_clauses_seen_alone": dict(Counter(c for x in rows for c in x["without_replacement"])),
                        "per_case": rows}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8", newline="\n")
    for name in SPLITS:
        s = result[name]["replaced_without_replacement"]
        print(f"{name}: replaced clause retrieved without its replacement in {s['k']}/{s['n']} cases "
              f"(rate {s['rate']}, 95% CI over {s['groups']} groups {s['ci95_over_groups'] or s['ci_refused']})")


if __name__ == "__main__":
    main()
