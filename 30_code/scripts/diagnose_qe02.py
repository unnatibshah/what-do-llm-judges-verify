"""Q-E-02 control failure diagnostic (50_analysis/results/diagnostics/QE02_CROWDING.md).

Read-only; uses the locked Gate 0 stack and the embedding cache. Paths come from suryabench.paths.
"""

import json

from suryabench.gate0.retriever import (
    LocalRetriever,
    build_corpus_chunks,
    cosine_similarity,
    get_embedding,
)
from suryabench.paths import CORPUS_DIR, RESULTS_DIR

TARGET_DOC, CROWDING_DOC = "MH-C3-002", "MH-C3-004"

chunks = build_corpus_chunks(CORPUS_DIR / "text")
retriever = LocalRetriever(chunks)
retriever.index(cache_file=RESULTS_DIR / "embeddings_cache.json")
with open(CORPUS_DIR / "graph" / "GATE0_QUERIES.json", encoding="utf-8") as f:
    query = next(q["text"] for q in json.load(f)["queries"] if q["query_id"] == "Q-E-02")

q_emb = get_embedding(query)
ranked = sorted(
    ((cosine_similarity(q_emb, e), c) for c, e in zip(chunks, retriever.embeddings, strict=True)),
    key=lambda x: -x[0],
)
target = [
    (i, round(s, 4), c.chunk_id) for i, (s, c) in enumerate(ranked, 1) if c.doc_id == TARGET_DOC
]
print(f"{TARGET_DOC} chunks (rank, score):", target[:5])
above = sum(
    1 for i, (_, c) in enumerate(ranked, 1) if c.doc_id == CROWDING_DOC and i < target[0][0]
)
print(f"{CROWDING_DOC} chunks ranked above best {TARGET_DOC}:", above)
print(f"top5 excl {CROWDING_DOC}:", [c.chunk_id for _, c in ranked if c.doc_id != CROWDING_DOC][:5])

seen: set[str] = set()
capped: list[str] = []
for _, c in ranked:
    if c.doc_id not in seen:
        seen.add(c.doc_id)
        capped.append(c.chunk_id)
    if len(capped) == 5:
        break
print("top5 cap 1/doc:", capped)
