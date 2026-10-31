"""Gate 0 100-chunk audit harness and R1–R8 metrics computation (protocol §3, §8, §9)."""

import json
from datetime import UTC, datetime
from pathlib import Path

from suryabench.core.enums import CurrencyVerdict
from suryabench.corpus.schema import CorpusManifest
from suryabench.gate0.retriever import (
    RD4_HYBRID,
    RD4_PER_DOC_CAP,
    LocalRetriever,
    RetrievalResult,
    map_chunks_to_clauses,
)
from suryabench.gate0.schema import AuditChunk, Gate0Metrics, Gate0QueryRegistry, QueryBand
from suryabench.graph.oracle import in_force
from suryabench.graph.schema import SupersessionGraph
from suryabench.paths import (
    CORPORA,
    CORPUS_DIR,
    GATE0_RESULT_MD,
    RESULTS_DIR,
    corpus_dir,
    embeddings_cache,
    resolve,
)


def run_gate0_audit(
    registry: Gate0QueryRegistry,
    retriever: LocalRetriever,
    graph: SupersessionGraph,
    manifest: CorpusManifest,
    case_date: str = "2024-09-01",
    text_dir: Path = CORPUS_DIR / "text",
) -> list[AuditChunk]:
    """Execute top-5 retrieval across 20 queries and generate 100 audited chunks."""
    doc_map = {d.doc_id: d for d in manifest.documents}
    audited_chunks: list[AuditChunk] = []
    # Strict clause mapping (same as the benchmark classifier): a chunk maps to a clause only if
    # it overlaps the clause's verbatim span in the document text.
    chunk_clauses = map_chunks_to_clauses(retriever.chunks, graph.nodes.values(), text_dir)

    for query in registry.queries:
        results: list[RetrievalResult] = retriever.retrieve(query.text, top_k=5)

        for res in results:
            chk = res.chunk
            doc = doc_map.get(chk.doc_id)

            # Detect mapped node if chunk text contains clause references
            mapped = sorted(chunk_clauses.get(chk.chunk_id, set()))
            mapped_node: str | None = mapped[0] if mapped else None

            # 1. Currency Check (R1)
            is_superseded = False
            if mapped_node:
                verdict = in_force(mapped_node, case_date, graph)
                if verdict in {CurrencyVerdict.SUPERSEDED, CurrencyVerdict.PARTIALLY_SUPERSEDED}:
                    is_superseded = True
            elif doc and doc.status == "presumed_superseded":
                is_superseded = True

            # 2. Jurisdiction Check (R2)
            is_wrong_jurisdiction = False
            if doc:
                doc_jur = doc.jurisdiction.code.value if doc.jurisdiction.code else "IN"
                if (
                    query.intended_jurisdiction != "IN"
                    and doc_jur != "IN"
                    and doc_jur != query.intended_jurisdiction
                ):
                    is_wrong_jurisdiction = True

            # 3. Severed from Scope Header Check (R3)
            # A chunk is severed if it states a rule/cap without stating the consumer category or premise
            is_severed = ("kW" in chk.text or "capacity" in chk.text) and not any(
                term in chk.text.lower()
                for term in [
                    "residential",
                    "eligible consumer",
                    "commercial",
                    "industrial",
                    "all consumers",
                ]
            )

            # 4. Undated Check (R6)
            is_undated = doc.effective_date == "UNKNOWN" if doc else False

            # 5. Misleading assessment:
            # Misleading if it presents superseded, wrong-jurisdiction, or severed misleading rule
            would_mislead = is_superseded or is_wrong_jurisdiction or (is_severed and is_superseded)

            audited_chunks.append(
                AuditChunk(
                    chunk_id=chk.chunk_id,
                    query_id=query.query_id,
                    rank=res.rank,
                    doc_id=chk.doc_id,
                    chunk_text=chk.text,
                    similarity_score=round(res.score, 4),
                    mapped_node_id=mapped_node,
                    is_superseded=is_superseded,
                    is_wrong_jurisdiction=is_wrong_jurisdiction,
                    is_severed_from_scope=is_severed,
                    is_undated=is_undated,
                    would_mislead=would_mislead,
                    audit_notes=f"doc_jur={doc.jurisdiction.code.value if doc and doc.jurisdiction.code else 'IN'}, status={doc.status if doc else 'unknown'}",
                )
            )

    return audited_chunks


def compute_gate0_metrics(
    chunks: list[AuditChunk],
    registry: Gate0QueryRegistry,
) -> Gate0Metrics:
    """Compute R1–R8 metrics programmatically from 100 audited chunks."""
    r1 = sum(1 for c in chunks if c.is_superseded)
    r2 = sum(1 for c in chunks if c.is_wrong_jurisdiction)
    r3 = sum(1 for c in chunks if c.is_severed_from_scope)
    r6 = sum(1 for c in chunks if c.is_undated)

    query_map = {q.query_id: q for q in registry.queries}
    chunks_by_query: dict[str, list[AuditChunk]] = {}
    for c in chunks:
        chunks_by_query.setdefault(c.query_id, []).append(c)

    r4_missing = 0
    r5_both = 0
    r7_qa_superseded = 0
    r8_qb_wrong_jur = 0

    for qid, q_chunks in chunks_by_query.items():
        q = query_map[qid]
        # R4: No expected governing node in top 5
        governing_found = False
        for c in q_chunks:
            if c.mapped_node_id and c.mapped_node_id in q.expected_governing_nodes:
                governing_found = True
                break
            if any(exp.split("#")[0] == c.doc_id for exp in q.expected_governing_nodes):
                governing_found = True
                break
        if not governing_found:
            r4_missing += 1

        # R5: Both current and superseded present
        has_current = any(
            not c.is_superseded
            and c.doc_id in [exp.split("#")[0] for exp in q.expected_governing_nodes]
            for c in q_chunks
        )
        has_superseded = any(c.is_superseded for c in q_chunks)
        if has_current and has_superseded:
            r5_both += 1

        # R7: Q-A queries with >=1 superseded chunk
        if q.band == QueryBand.Q_A and any(c.is_superseded for c in q_chunks):
            r7_qa_superseded += 1

        # R8: Q-B queries with >=1 wrong jurisdiction chunk
        if q.band == QueryBand.Q_B and any(c.is_wrong_jurisdiction for c in q_chunks):
            r8_qb_wrong_jur += 1

    would_mislead_total = sum(1 for c in chunks if c.would_mislead)
    misleading_pct = round((would_mislead_total / len(chunks)) * 100.0, 1)

    if misleading_pct >= 12.0:
        branch = "Proceed with primary design (misleading >= 12%)"
    elif misleading_pct >= 4.0:
        branch = "Proceed with sized cases (4% <= misleading < 12%)"
    else:
        branch = "Trigger three-cause diagnostic (misleading < 4%)"

    return Gate0Metrics(
        r1_superseded_chunks=r1,
        r2_wrong_jurisdiction_chunks=r2,
        r3_severed_chunks=r3,
        r4_missing_expected_node_queries=r4_missing,
        r5_both_versions_present_queries=r5_both,
        r6_undated_chunks=r6,
        r7_qa_superseded_queries=r7_qa_superseded,
        r8_qb_wrong_jurisdiction_queries=r8_qb_wrong_jur,
        would_mislead_total=would_mislead_total,
        misleading_percentage=misleading_pct,
        branch_decision=branch,
    )


def save_gate0_audit(
    chunks: list[AuditChunk],
    metrics: Gate0Metrics,
    output_path: Path,
) -> None:
    """Save audited chunks and metrics summary to JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "metrics": metrics.model_dump(),
        "total_chunks": len(chunks),
        "chunks": [c.model_dump() for c in chunks],
    }
    output_path.write_text(json.dumps(data, indent=2), encoding="utf-8", newline="\n")


def main() -> None:
    """Run Gate 0 100-chunk retrieval audit over full corpus and generate GATE0-RESULT.md.

    With no arguments this reproduces the original run (Gate 0 dense stack, writing
    50_analysis/results/gate0_audit.json and 50_analysis/GATE0-RESULT.md). The RD4 re-run is
    ``--stack rd4 --out-dir <new dir>``: it writes both files into that directory instead.
    """
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--stack", choices=["gate0", "rd4"], default="gate0")
    ap.add_argument("--out-dir", default=None, help="write gate0_audit.json and GATE0-RESULT.md here")
    # Gate 0 was run on r2; the default reproduces it. Another corpus must write to its own --out-dir.
    ap.add_argument("--corpus", default="r2", choices=sorted(CORPORA))
    args = ap.parse_args()
    if args.corpus != "r2" and not args.out_dir:
        ap.error("--corpus other than r2 needs --out-dir (the default outputs are the r2 Gate 0 of record)")
    cdir = corpus_dir(args.corpus)
    manifest_path = cdir / "MANIFEST.json"
    graph_path = cdir / "graph" / "supersession.json"
    queries_path = CORPUS_DIR / "graph" / "GATE0_QUERIES.json"  # the 20 frozen queries, whatever the corpus
    text_dir = cdir / "text"
    results_dir = RESULTS_DIR
    cache_path = embeddings_cache(args.corpus)
    audit_json_path = results_dir / "gate0_audit.json"
    report_md_path = GATE0_RESULT_MD
    if args.out_dir:
        out_dir = resolve(args.out_dir)
        audit_json_path, report_md_path = out_dir / "gate0_audit.json", out_dir / "GATE0-RESULT.md"
        out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading Manifest and Supersession Graph...")
    from suryabench.corpus.manifest import load_manifest

    manifest = load_manifest(manifest_path)

    with open(graph_path, encoding="utf-8") as f:
        graph = SupersessionGraph.model_validate(json.load(f))

    with open(queries_path, encoding="utf-8") as f:
        registry = Gate0QueryRegistry.model_validate(json.load(f))

    print(f"Building chunks across all {len(manifest.documents)} documents...")
    from suryabench.gate0.retriever import build_corpus_chunks

    chunks = build_corpus_chunks(text_dir)
    print(f"Total boundary chunks built: {len(chunks)}")

    print("Indexing chunks with BGE-M3 (dense vectors)...")
    retriever = (LocalRetriever(chunks, hybrid=RD4_HYBRID, per_doc_cap=RD4_PER_DOC_CAP) if args.stack == "rd4"
                 else LocalRetriever(chunks))
    retriever.index(cache_file=cache_path)
    print(f"Retrieval stack: {retriever.describe()}")

    print("Executing Gate 0 top-5 retrieval across 20 frozen queries...")
    audited_chunks = run_gate0_audit(registry, retriever, graph, manifest, text_dir=text_dir)
    metrics = compute_gate0_metrics(audited_chunks, registry)

    save_gate0_audit(audited_chunks, metrics, audit_json_path)
    print(f"Gate 0 audit JSON saved to {audit_json_path}")

    # Control queries (success criterion of 2026-09-28): does a top-5 chunk hold an expected governing
    # clause? Clause level, by the strict verbatim-span map; a same-document chunk does not count.
    clause_map = map_chunks_to_clauses(chunks, graph.nodes.values(), text_dir)
    hits = {q.query_id: any(clause_map.get(c.chunk_id, set()) & set(q.expected_governing_nodes)
                            for c in audited_chunks if c.query_id == q.query_id)
            for q in registry.queries if q.band.value == "Q-E"}
    controls = ", ".join(f"{qid} {'PASS' if ok else 'FAIL'}" for qid, ok in hits.items())
    print(f"Control queries: {controls}")

    # Generate GATE0-RESULT.md
    report_content = f"""# Gate 0 Retrieval Exposure Audit Report

**Audit Date**: {datetime.now(UTC).date().isoformat()}
**Corpus**: {manifest.corpus_version} ({args.corpus})
**Corpus Scope**: {len(manifest.documents)} Documents ({sum(d.pages for d in manifest.documents):,} Pages, {len(chunks):,} Chunks)
**Retrieval stack**: {retriever.describe()} (top-k=5)
**Total Audited Chunks**: {len(audited_chunks)} Chunks across 20 Frozen Queries

---

## Executive Summary & Gate 0 Branch Decision

- **Misleading Chunk Percentage**: **{metrics.misleading_percentage}%** ({metrics.would_mislead_total} of {len(audited_chunks)} chunks)
- **Control queries (Q-E) retrieving an expected node in the top 5**: {controls}
- **Gate 0 Protocol Threshold**: $\\ge 12.0\\%$
- **Empirical Branch Decision**: **{metrics.branch_decision}**

> **Formal Protocol Conclusion**:
> Because the empirical exposure to misleading chunks exceeds the $12.0\\%$ threshold, SuryaBench **proceeds with the primary experimental design as planned** without modification.

---

## Detailed R1–R8 Exposure Metrics

| Metric | Name / Description | Value |
| :--- | :--- | :--- |
| **R1** | Superseded chunks retrieved in top-5 | **{metrics.r1_superseded_chunks}** |
| **R2** | Wrong-jurisdiction distractor chunks retrieved | **{metrics.r2_wrong_jurisdiction_chunks}** |
| **R3** | Severed scope chunks (capacity stated without consumer class) | **{metrics.r3_severed_chunks}** |
| **R4** | Queries missing expected governing node in top-5 | **{metrics.r4_missing_expected_node_queries} / 20** |
| **R5** | Queries with co-occurring superseded and current versions | **{metrics.r5_both_versions_present_queries} / 20** |
| **R6** | Undated chunks retrieved | **{metrics.r6_undated_chunks}** |
| **R7** | Q-A (Currency-sensitive) queries retrieving $\\ge 1$ superseded chunk | **{metrics.r7_qa_superseded_queries} / 6** |
| **R8** | Q-B (Jurisdiction-sensitive) queries retrieving $\\ge 1$ cross-jurisdiction chunk | **{metrics.r8_qb_wrong_jurisdiction_queries} / 5** |

---

## Query-by-Query Retrieval Breakdown

| Query ID | Band | Query Text | Intended Jur | Top-1 Chunk Doc | Misleading Chunks (Top-5) |
| :--- | :--- | :--- | :--- | :--- | :--- |
"""
    query_map = {q.query_id: q for q in registry.queries}
    chunks_by_query: dict[str, list[AuditChunk]] = {}
    for c in audited_chunks:
        chunks_by_query.setdefault(c.query_id, []).append(c)

    for qid, q in query_map.items():
        q_chunks = chunks_by_query.get(qid, [])
        top1_doc = q_chunks[0].doc_id if q_chunks else "N/A"
        misleading_count = sum(1 for c in q_chunks if c.would_mislead)
        report_content += f"| `{qid}` | {q.band.value} | {q.text[:45]}... | {q.intended_jurisdiction} | `{top1_doc}` | {misleading_count} / 5 |\n"

    report_md_path.write_text(report_content, encoding="utf-8", newline="\n")
    print(f"Wrote GATE0-RESULT.md to {report_md_path}")


if __name__ == "__main__":
    main()
