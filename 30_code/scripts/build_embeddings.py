"""Build (or complete) the dense bge-m3 index of a corpus with the runner's own chunking and cache.

    python 30_code/scripts/build_embeddings.py --corpus r3

Writes the git-ignored cache ``paths.EMBEDDING_CACHES[corpus]`` and prints chunk count and build time.
"""

import argparse
import json
import time

from suryabench.gate0.retriever import (
    RD4_HYBRID,
    RD4_PER_DOC_CAP,
    LocalRetriever,
    build_corpus_chunks,
)
from suryabench.paths import CORPORA, DEFAULT_CORPUS, corpus_dir, display, embeddings_cache


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=DEFAULT_CORPUS, choices=sorted(CORPORA))
    args = ap.parse_args()
    chunks = build_corpus_chunks(corpus_dir(args.corpus) / "text")
    cache = embeddings_cache(args.corpus)
    t0 = time.time()
    r = LocalRetriever(chunks, hybrid=RD4_HYBRID, per_doc_cap=RD4_PER_DOC_CAP)
    r.index(cache_file=cache)
    assert len(r.embeddings) == len(chunks), "index incomplete"
    print(json.dumps({"corpus": args.corpus, "chunks": len(chunks), "documents": len({c.doc_id for c in chunks}),
                      "build_seconds": round(time.time() - t0, 1), "cache": display(cache),
                      "retriever": r.describe()}))


if __name__ == "__main__":
    main()
