"""Gate 0 text chunking, local vector indexing, and dense retrieval (protocol §3, §8)."""

import hashlib
import json
import math
import re
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from suryabench.core.exceptions import SuryaBenchError


@dataclass(frozen=True)
class TextChunk:
    """A single discrete text chunk with document provenance."""

    chunk_id: str
    doc_id: str
    text: str
    char_start: int
    char_end: int


@dataclass(frozen=True)
class RetrievalResult:
    """Result of a top-k retrieval query."""

    chunk: TextChunk
    score: float
    rank: int


def _find_clean_boundary(text: str, target_pos: int, window: int = 80) -> int:
    """Find a natural paragraph, line break, or sentence boundary near target_pos."""
    if target_pos >= len(text):
        return len(text)

    search_start = max(0, target_pos - window)
    search_end = min(len(text), target_pos + window)
    sub = text[search_start:search_end]
    rel_target = target_pos - search_start

    # Priority 1: Paragraph break \n\n
    p_idx = sub.rfind("\n\n", 0, min(len(sub), rel_target + 40))
    if p_idx != -1 and (search_start + p_idx) > search_start + 10:
        return search_start + p_idx + 2

    # Priority 2: Line break \n (prevents severing table rows or clause lines)
    l_idx = sub.rfind("\n", 0, min(len(sub), rel_target + 30))
    if l_idx != -1 and (search_start + l_idx) > search_start + 10:
        return search_start + l_idx + 1

    # Priority 3: Sentence end
    s_idx = sub.rfind(". ", 0, min(len(sub), rel_target + 20))
    if s_idx != -1 and (search_start + s_idx) > search_start + 10:
        return search_start + s_idx + 2

    # Fallback to word space
    sp_idx = sub.rfind(" ", 0, min(len(sub), rel_target + 10))
    if sp_idx != -1 and (search_start + sp_idx) > search_start:
        return search_start + sp_idx + 1

    return target_pos


def build_corpus_chunks(
    text_dir: Path,
    chunk_size: int = 600,
    overlap: int = 100,
) -> list[TextChunk]:
    """Slice all documents in text_dir into boundary-aware, table-preserving chunks."""
    chunks: list[TextChunk] = []
    text_files = sorted(text_dir.glob("*.txt"))

    for tf in text_files:
        doc_id = tf.stem
        content = tf.read_text(encoding="utf-8")
        if not content.strip():
            continue

        start = 0
        chunk_idx = 0
        while start < len(content):
            raw_end = min(len(content), start + chunk_size)
            end = _find_clean_boundary(content, raw_end)
            if end <= start:
                end = min(len(content), start + chunk_size)

            chunk_text = content[start:end].strip()
            if len(chunk_text) >= 40:  # Avoid empty or 1-word fragments
                chunk_id = f"{doc_id}#chk-{chunk_idx:04d}"
                chunks.append(
                    TextChunk(
                        chunk_id=chunk_id,
                        doc_id=doc_id,
                        text=chunk_text,
                        char_start=start,
                        char_end=end,
                    )
                )
                chunk_idx += 1

            if end >= len(content):
                break

            # Calculate next start using overlap
            next_target = max(start + 1, end - overlap)
            start = _find_clean_boundary(content, next_target, window=40)
            if start >= end:
                start = end

    return chunks


class _ClauseLike(Protocol):
    node_id: str
    doc_id: str
    clause_text_snippet: str


def map_chunks_to_clauses(
    chunks: list[TextChunk],
    nodes: Iterable[_ClauseLike],
    text_dir: Path,
) -> dict[str, set[str]]:
    """Map chunk_id -> clause node_ids whose verbatim snippet overlaps the chunk's char span.

    The snippet is located by its first 8 words, whitespace/punctuation-insensitive.
    A node whose snippet is not verbatim in the extracted text maps to no chunk, so
    it can never count as retrieved (see FailureClassifier F4-R/F4-C).
    """
    by_doc: dict[str, list[TextChunk]] = {}
    for c in chunks:
        by_doc.setdefault(c.doc_id, []).append(c)
    mapping: dict[str, set[str]] = {}
    for node in nodes:
        path = text_dir / f"{node.doc_id}.txt"
        words = re.findall(r"\w+", node.clause_text_snippet)[:8]
        if not words or not path.exists():
            continue
        m = re.search(r"\W+".join(map(re.escape, words)), path.read_text(encoding="utf-8"), re.I)
        if not m:
            continue
        start, end = m.start(), m.start() + len(node.clause_text_snippet)
        for c in by_doc.get(node.doc_id, []):
            if c.char_start < end and c.char_end > start:
                mapping.setdefault(c.chunk_id, set()).add(node.node_id)
    return mapping


def get_embedding(
    text: str,
    model: str = "bge-m3:latest",
    host: str = "http://127.0.0.1:11434",
    timeout: float = 10.0,
) -> list[float]:
    """Compute dense vector embedding using local Ollama instance."""
    url = f"{host.rstrip('/')}/api/embeddings"
    payload = json.dumps({"model": model, "prompt": text}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            emb = data.get("embedding")
            if not emb or not isinstance(emb, list):
                raise SuryaBenchError(f"Malformed embedding response from Ollama: {data}")
            return [float(x) for x in emb]
    except urllib.error.URLError as e:
        raise SuryaBenchError(
            f"Failed to connect to local Ollama embedding service at {url}: {e}"
        ) from e


def cosine_scores(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Cosine similarity of one query against every row (0.0 where either norm is 0), as cosine_similarity."""
    norms = np.sqrt(np.einsum("ij,ij->i", matrix, matrix)) * math.sqrt(float(query @ query))
    dots = matrix @ query
    out = np.zeros(len(matrix))
    np.divide(dots, norms, out=out, where=norms != 0.0)
    return out


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    dot = sum(a * b for a, b in zip(v1, v2, strict=False))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


_TITLE_CUES = [r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b", r"\b\d{4}-\d{2}-\d{2}\b", r"\bFY\s?\d{2,4}(-\d{2,4})?\b",
               r"\b(19|20)\d{2}(-\d{2,4})?\b", r"\b(original|amended|amendments?|amending|dated)\b"]


def strip_title(title: str) -> str:
    """A document title without the cues that date it (metadata off, D27): dates, years, financial years and the
    words original, amended, amendment, dated. Leftover empty brackets and separators are tidied."""
    for pat in _TITLE_CUES:
        title = re.sub(pat, "", title, flags=re.IGNORECASE)
    title = re.sub(r"\(\s*[,;:/-]?\s*\)", "", title)
    title = re.sub(r"\s+([,;:)])", r"\1", title)
    return re.sub(r"\s{2,}", " ", title).strip(" ,;:-")


# Retrieval stack locked by RD4 on 2026-09-30: chosen on dev decisive-clause recall
# (30_code/scripts/rd4_select_retrieval.py; 50_analysis/results/rd4_retrieval_selection/dev_recall.json),
# never on the Gate 0 queries. LocalRetriever's defaults stay the pre-RD4 (Gate 0) dense stack.
RD4_HYBRID, RD4_PER_DOC_CAP = True, None


class LocalRetriever:
    """In-memory dense retriever over corpus chunks using local embedding vectors."""

    def __init__(
        self,
        chunks: list[TextChunk],
        model: str = "bge-m3:latest",
        host: str = "http://127.0.0.1:11434",
        hybrid: bool = False,
        per_doc_cap: int | None = None,
    ) -> None:
        self.chunks = chunks
        self.model = model
        self.host = host
        # RD4 options (default off = the Gate 0 stack): fuse dense with BM25 ranks (reciprocal rank
        # fusion, k=60), and/or keep at most `per_doc_cap` chunks per document in the top k.
        self.hybrid = hybrid
        self.per_doc_cap = per_doc_cap
        self._bm25: tuple[list[Counter[str]], dict[str, float], float] | None = None
        # One float64 matrix (n_chunks x dim): about 0.1 GB for r3, against about 1 GB as Python lists.
        self.embeddings: np.ndarray = np.zeros((0, 0))
        # Registry metadata shown in context headers so generators can cite exact ids.
        self.chunk_clauses: dict[str, set[str]] = {}
        self.doc_titles: dict[str, str] = {}
        # Metadata factor (plan D11): when `meta` is on, every header, retrieved or injected alike, also
        # shows the document's issuer, jurisdiction and effective date (doc_meta: doc_id -> those fields).
        self.meta = False
        self.doc_meta: dict[str, dict[str, str]] = {}

    def meta_header(self, doc_id: str) -> str:
        """The metadata part of a [SOURCE ...] header: empty unless `meta` is on."""
        if not self.meta:
            return ""
        m = self.doc_meta.get(doc_id, {})
        return (f" | issuer={m.get('issuer', 'unknown')} | jurisdiction={m.get('jurisdiction', 'unknown')}"
                f" | effective={m.get('effective_date', 'unknown')}")

    def describe(self) -> str:
        """The retrieval stack, for run manifests."""
        return f"dense:{self.model}" + ("+bm25-rrf60" if self.hybrid else "") + (
            f"+cap{self.per_doc_cap}/doc" if self.per_doc_cap else "")

    def bm25_scores(self, query_text: str, k1: float = 1.5, b: float = 0.75) -> list[float]:
        """Okapi BM25 score of every chunk for the query (lower-cased word tokens)."""
        if self._bm25 is None:
            tfs = [Counter(re.findall(r"\w+", c.text.lower())) for c in self.chunks]
            df = Counter(t for tf in tfs for t in tf)
            n = len(tfs)
            idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}
            avgdl = sum(sum(tf.values()) for tf in tfs) / max(n, 1)
            self._bm25 = (tfs, idf, avgdl)
        tfs, idf, avgdl = self._bm25
        q = set(re.findall(r"\w+", query_text.lower())) & idf.keys()
        scores = []
        for tf in tfs:
            dl = sum(tf.values())
            scores.append(sum(idf[t] * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * dl / avgdl)) for t in q if t in tf))
        return scores

    def format_chunk(self, chunk: TextChunk) -> str:
        """Chunk text under a header naming its chunk id, document and contained clause ids. With metadata off
        the title loses its years, dates and "original"/"amended" words (D27)."""
        clauses = ", ".join(sorted(self.chunk_clauses.get(chunk.chunk_id, set()))) or "none"
        title = self.doc_titles.get(chunk.doc_id, "")
        title = title if self.meta else strip_title(title)
        doc = f"{chunk.doc_id}: {title}" if title else chunk.doc_id
        return f"[SOURCE chunk_id={chunk.chunk_id} | document={doc} | clause_ids={clauses}{self.meta_header(chunk.doc_id)}]\n{chunk.text}"

    def index(self, cache_file: Path | None = None) -> None:
        """Compute or load embeddings for all corpus chunks."""
        cached_dict: dict[str, list[float]] = {}
        if cache_file and cache_file.exists():
            try:
                with open(cache_file, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    cached_dict = data
                elif isinstance(data, list) and len(data) == len(self.chunks):
                    self.embeddings = np.asarray(data, dtype=np.float64)
                    return
            except Exception:
                cached_dict = {}

        chunk_hashes = [hashlib.sha256(chk.text.encode("utf-8")).hexdigest() for chk in self.chunks]
        missing_indices = [i for i, h in enumerate(chunk_hashes) if h not in cached_dict]

        if missing_indices:
            def _embed(idx: int) -> tuple[str, list[float]]:
                chk = self.chunks[idx]
                h = chunk_hashes[idx]
                emb = get_embedding(chk.text, model=self.model, host=self.host)
                return h, emb

            with ThreadPoolExecutor(max_workers=6) as executor:
                for h, emb in executor.map(_embed, missing_indices):
                    cached_dict[h] = emb

            if cache_file:
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                with open(cache_file, "w", encoding="utf-8", newline="\n") as f:
                    json.dump(cached_dict, f)

        self.embeddings = np.asarray([cached_dict[h] for h in chunk_hashes], dtype=np.float64)
        del cached_dict

    def retrieve(self, query_text: str, top_k: int = 5) -> list[RetrievalResult]:
        """Retrieve top_k chunks using unranked dense cosine similarity with lexical fallback."""
        if len(self.embeddings) == 0 or len(self.embeddings) != len(self.chunks):
            # Lexical keyword-overlap fallback for offline execution
            q_terms = {w.lower() for w in query_text.split() if len(w) > 3}
            lexical_scored: list[tuple[float, int, TextChunk]] = []
            for idx, chunk in enumerate(self.chunks):
                c_text = chunk.text.lower()
                matches = sum(1 for t in q_terms if t in c_text)
                score = matches / max(len(q_terms), 1)
                lexical_scored.append((score, idx, chunk))
            lexical_scored.sort(key=lambda x: x[0], reverse=True)
            return [
                RetrievalResult(chunk=chunk, score=score, rank=rank)
                for rank, (score, _, chunk) in enumerate(lexical_scored[:top_k], start=1)
            ]

        query_emb = get_embedding(query_text, model=self.model, host=self.host)
        scores = cosine_scores(np.asarray(query_emb, dtype=np.float64), self.embeddings)
        scored: list[tuple[float, int, TextChunk]] = [
            (float(score), idx, chunk) for idx, (score, chunk) in enumerate(zip(scores, self.chunks, strict=True))
        ]

        scored.sort(key=lambda x: x[0], reverse=True)

        if self.hybrid:
            bm25 = self.bm25_scores(query_text)
            bm25_rank = {idx: r for r, idx in enumerate(sorted(range(len(bm25)), key=lambda i: -bm25[i]), start=1)}
            fused = [(1 / (60 + r) + 1 / (60 + bm25_rank[idx]), idx, chunk)
                     for r, (_, idx, chunk) in enumerate(scored, start=1)]
            scored = sorted(fused, key=lambda x: x[0], reverse=True)

        per_doc: Counter[str] = Counter()
        results: list[RetrievalResult] = []
        for score, _, chunk in scored:
            if self.per_doc_cap and per_doc[chunk.doc_id] >= self.per_doc_cap:
                continue
            per_doc[chunk.doc_id] += 1
            results.append(RetrievalResult(chunk=chunk, score=score, rank=len(results) + 1))
            if len(results) == top_k:
                break

        return results
