"""Arm 4: independent verifiers (plan D9, 2026-10-01).

Independent retrieval (I1), LLM verifiers:
- ``100``: the audit-phrased query (currently in force regulations ... governing <stage>).
- ``100-neutral`` (RD3, D29): the application facts and stage only, phrased like the generator's query.
  Neither query contains any generator output (root cause, decision or cited ids).

Registries, replacing the old 110/111 (whose registry was the answer key that also planted the faults):
- ``reg-oracle``: the benchmark's own supersession graph, an upper bound and labelled as one;
- ``reg-real``: a registry built separately, blind to the gold graph, from the corpus text
  (``40_data/registries/registry_real_v1.json``, WP6; its own schema, converted by ``load_registry``);
- ``reg-noisy25-s<k>`` / ``reg-noisy50-s<k>``: the oracle with 25% / 50% of its edges dropped, nested, seeds 0-4;
- ``reg-spurious10-s<k>``: the oracle plus 10% wrong superseded_by edges, seeds 0-4 (D31).
Each runs deterministically, with no LLM and no override of anything: for every citation it looks up the
registry entry, then raises F2 (reason ``wrong_jurisdiction``) and F3 (``not_in_force`` at the application date,
D32) findings, and F1 (``other``) for a citation that names nothing in the corpus. ``reg-real-llm`` instead gives the registry facts to
an LLM verifier as evidence lines beside the generator's evidence, with no deterministic verdict.

A citation is resolved to registry entries through the passage it came from: an exact or normalised
registry id (``MH-C3-001#cl-2.1j`` = ``MH-C3-001#cl-2.1(j)``), or the registry entries whose text lies in the
cited chunk (or in the chunk that contains the cited clause). A real passage with no entry is unknown, not
fabricated.
"""

import json
import random
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from suryabench.arms.arm1_rag import STATE_NAMES, Arm1ExecutionResult
from suryabench.arms.arm2_agent import Arm2ExecutionResult
from suryabench.arms.tools.case_reader import ParsedCaseFacts as ParsedCase
from suryabench.arms.tools.case_reader import parse_case_facsimiles
from suryabench.arms.verify_shared import VerifierResult, flag, llm_verdict
from suryabench.cases.schema import BenchmarkCase
from suryabench.core.enums import ConfidenceLevel, CurrencyVerdict, EdgeRelation
from suryabench.gate0.retriever import LocalRetriever
from suryabench.graph.oracle import in_force
from suryabench.graph.schema import Edge, Node, SupersessionGraph

GeneratorResult = Arm1ExecutionResult | Arm2ExecutionResult

LLM_CONFIGS = ("100", "100-neutral")
# D31 (2026-10-01): nested edge deletions (the 50% set contains the 25% set) and 10% spurious supersession
# edges, each over NOISE_SEEDS seeds; all deterministic. name -> (kind, fraction, seed).
NOISE_SEEDS = 5
NOISE: dict[str, tuple[str, float, int]] = {
    **{f"reg-noisy{p}-s{k}": ("drop", p / 100, k) for p in (25, 50) for k in range(NOISE_SEEDS)},
    **{f"reg-spurious10-s{k}": ("spurious", 0.10, k) for k in range(NOISE_SEEDS)},
}
REGISTRY_CONFIGS = ("reg-oracle", "reg-real", *NOISE)

# Words of the audit-phrased query that the neutral template must never contain (RD3).
AUDIT_WORDS = ("currently", "in force", "amendment", "supersed", "superseding", "circular", "limit", "order")


@dataclass
class Registry:
    """A clause registry and the chunk -> registry-entry map built from its own clause texts."""

    name: str
    graph: SupersessionGraph
    chunk_map: dict[str, set[str]] = field(default_factory=dict)

    def by_norm(self, clause_id: str) -> list[str]:
        """Registry entries whose id equals ``clause_id`` after normalisation."""
        key = norm_clause_id(clause_id)
        return sorted(n for n in self.graph.nodes if norm_clause_id(n) == key)


def norm_clause_id(clause_id: str) -> str:
    """``MH-C3-001#cl-2.1(j)`` and ``MH-C3-001#cl-2.1j`` -> ``MH-C3-001#21j``: case, punctuation and the
    ``cl-`` prefix ignored after the document id."""
    doc, _, ref = clause_id.partition("#")
    return f"{doc}#{re.sub(r'[^0-9a-z]', '', ref.lower().removeprefix('cl-'))}"


# registry_real_v1 edge type -> graph relation: supersedes -> superseded (in_force SUPERSEDED);
# partially_supersedes -> amended_by (PARTIALLY_SUPERSEDED, also a currency finding); amends -> no effect.
_REAL_RELATION = {"supersedes": EdgeRelation.SUPERSEDED_BY, "partially_supersedes": EdgeRelation.AMENDED_BY,
                  "amends": EdgeRelation.CLARIFIED_BY}


def load_registry(path: Path, doc_dates: dict[str, str] | None = None) -> SupersessionGraph:
    """A registry file: either the supersession-graph schema, or the WP6 schema (``generated_by``, list
    ``nodes``, typed ``edges``, ``document_supersessions``), converted so ``in_force`` reads it. Fields the
    WP6 schema lacks (date basis, status, authority) get neutral placeholders that ``in_force`` never reads.
    A document supersession supersedes every clause of ``doc_from`` from the effective date of ``doc_to``
    (``doc_dates``, from the corpus manifest), unless its type says the instrument was not repealed
    (``*no_repeal``); a ``doc_from`` outside the corpus is ignored."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data.get("nodes"), dict):
        return SupersessionGraph.model_validate(data)
    conf = {c.value for c in ConfidenceLevel}
    nodes: dict[str, Node] = {}
    for n in data["nodes"]:
        code = str(n.get("jurisdiction") or "IN")
        date = str(n.get("effective_date") or "")
        nodes[n["node_id"]] = Node.model_validate({
            "node_id": n["node_id"], "doc_id": n["doc_id"], "clause_ref": str(n.get("clause_ref") or ""),
            "clause_text_snippet": str(n.get("snippet") or ""), "subject": str(n.get("topic") or "unknown"),
            "jurisdiction": {"level": "central" if code == "IN" else "state", "code": code},
            "effective_date": date if date.startswith(("19", "20")) else "UNKNOWN",
            "effective_date_basis": "E1", "effective_date_confidence": n.get("confidence") if n.get("confidence") in conf else "low",
            "status_at_snapshot": "unknown", "authority_rank": "A1"})
    edges = [Edge.model_validate({
        "from": e["from_node"], "to": e["to_node"], "relation": _REAL_RELATION[e["type"]],
        "from_date": e.get("effective_date") or "UNKNOWN",
        "evidence": {"type": "explicit", "quote_text": str(e.get("evidence_quote") or ""), "doc_id": e["to_node"].split("#")[0]},
        "confidence": e.get("confidence") if e.get("confidence") in conf else "low"})
        for e in data.get("edges", []) if e.get("type") in _REAL_RELATION]
    docs = {n.doc_id for n in nodes.values()} | set(doc_dates or {})
    superseded = {d["doc_from"]: (doc_dates or {}).get(d["doc_to"], "UNKNOWN")
                  for d in data.get("document_supersessions", [])
                  if d["doc_from"] in docs and "no_repeal" not in str(d.get("type", ""))
                  and d.get("confidence") != "low"}
    return SupersessionGraph(nodes=nodes, edges=edges,
                             superseded_documents={k: v for k, v in superseded.items() if v != "UNKNOWN"})


def noisy_registry(graph: SupersessionGraph, fraction: float, seed: int = 0) -> SupersessionGraph:
    """The graph with ``fraction`` of its edges dropped. Nested (D31): one seeded permutation of the edges,
    and the first ``round(n * fraction)`` of it are dropped, so at one seed the 50% drop set contains the 25%
    set. A wholly superseded document stays superseded only while a superseded_by edge from one of its
    clauses remains."""
    edges = list(graph.edges)
    order = list(range(len(edges)))
    random.Random(seed).shuffle(order)
    dropped = set(order[:round(len(edges) * fraction)])
    kept = [e for i, e in enumerate(edges) if i not in dropped]
    backed = {graph.nodes[e.from_node].doc_id for e in kept
              if e.relation == EdgeRelation.SUPERSEDED_BY and e.from_node in graph.nodes}
    return graph.model_copy(update={"edges": kept, "superseded_documents": {
        d: since for d, since in graph.superseded_documents.items() if d in backed}})


def spurious_registry(graph: SupersessionGraph, fraction: float, seed: int = 0) -> SupersessionGraph:
    """The graph plus ``round(n_edges * fraction)`` wrong ``superseded_by`` edges (D31): each from a seeded
    choice of a dated clause that has no outgoing edge to another clause of the same jurisdiction, effective
    from the clause's own date, so the registry calls an in-force clause superseded and its FPR can move."""
    rng = random.Random(seed)
    out_nodes = {e.from_node for e in graph.edges}
    dated = sorted(n for n, node in graph.nodes.items()
                   if n not in out_nodes and node.effective_date[:2] in {"19", "20"}
                   and node.effective_date_confidence != ConfidenceLevel.LOW)
    by_j: dict[str, list[str]] = {}
    for n in graph.nodes:
        by_j.setdefault(str(getattr(graph.nodes[n].jurisdiction.code, "value", graph.nodes[n].jurisdiction.code)), []).append(n)
    added: list[Edge] = []
    for src in rng.sample(dated, min(len(dated), round(len(graph.edges) * fraction))):
        node = graph.nodes[src]
        pool = sorted(t for t in by_j[str(getattr(node.jurisdiction.code, "value", node.jurisdiction.code))] if t != src)
        if not pool:
            continue
        added.append(Edge.model_validate({
            "from": src, "to": rng.choice(pool), "relation": EdgeRelation.SUPERSEDED_BY, "from_date": node.effective_date,
            "evidence": {"type": "implicit", "quote_text": "", "doc_id": node.doc_id}, "confidence": "medium"}))
    return graph.model_copy(update={"edges": [*graph.edges, *added]})


def registry_variant(graph: SupersessionGraph, name: str) -> SupersessionGraph:
    """The oracle graph under a NOISE configuration."""
    kind, fraction, seed = NOISE[name]
    return noisy_registry(graph, fraction, seed) if kind == "drop" else spurious_registry(graph, fraction, seed)


def audit_query(parsed: ParsedCase, state: str) -> str:
    """Config 100: the audit-phrased I1 query (no generator reasoning in it)."""
    return (
        f"Currently in force regulations, amendments and superseding orders in {state} governing "
        f"{parsed.application_stage or 'rooftop solar applications'}: "
        f"{parsed.proposed_capacity_kw} kW proposed, sanctioned load {parsed.sanctioned_load_kw} kW."
    )


def neutral_query(parsed: ParsedCase) -> str:
    """100-neutral (D29, 2026-10-01): a topical question built from the application facts and the stage only.
    No generator output enters it (before: its decision and cited clause ids, which pulled back the planted
    document under BM25)."""
    state = STATE_NAMES.get(parsed.state or "", "India")
    stage = (parsed.application_stage or "rooftop solar application").lower()
    return (
        f"Which rules decide a {stage} for a rooftop solar system in {state}? "
        f"{state}, {parsed.consumer_category or 'consumer'}, {parsed.proposed_capacity_kw} kW proposed, "
        f"sanctioned load {parsed.sanctioned_load_kw} kW."
    )


def resolve_citation(citation: str, registry: Registry, retriever: LocalRetriever) -> list[str] | None:
    """Registry entries a citation names: [] for a real passage or document with no entry, None when the
    citation names nothing in the corpus (fabrication)."""
    cited = citation.strip()
    if cited in registry.graph.nodes:
        return [cited]
    if cited in retriever.chunk_clauses:
        chunks = [cited]
    else:  # a clause id: the chunk(s) that contain it are the passage the generator saw
        chunks = [cid for cid, clauses in retriever.chunk_clauses.items() if cited in clauses]
    named = registry.by_norm(cited) if "#" in cited and "#chk-" not in cited else []
    if chunks or named:
        return sorted(set(named) | {n for cid in chunks for n in registry.chunk_map.get(cid, set())})
    doc_ids = {c.doc_id for c in retriever.chunks}
    return [] if cited.split("#")[0] in doc_ids else None


@dataclass
class CitationFacts:
    """What a registry says about one citation: entries (None = names nothing in the corpus), their
    jurisdictions, and each entry's in-force status at the application date."""

    citation: str
    nodes: list[str] | None
    jurisdiction: list[str] = field(default_factory=list)
    status: dict[str, str] = field(default_factory=dict)


def registry_facts(
    generator_result: GeneratorResult,
    registry: Registry,
    retriever: LocalRetriever,
    case_date: str | None,
) -> list[CitationFacts]:
    """Per citation: resolved entries, their jurisdictions, and in-force status at the case date."""
    facts: list[CitationFacts] = []
    for cited in generator_result.cited_rules:
        nodes = resolve_citation(cited, registry, retriever)
        doc = cited.split("#")[0]
        if nodes is None:
            facts.append(CitationFacts(cited, None))
            continue
        juris = sorted({str(getattr(registry.graph.nodes[n].jurisdiction.code, "value", registry.graph.nodes[n].jurisdiction.code))
                        for n in nodes}) or [retriever.doc_meta.get(doc, {}).get("jurisdiction", "unknown")]
        status: dict[str, str] = {}
        if case_date:
            for n in nodes:
                status[n] = in_force(n, case_date, registry.graph).value
            since = registry.graph.superseded_documents.get(doc)
            if since and since <= case_date:
                status[doc] = f"{CurrencyVerdict.SUPERSEDED.value} (whole instrument, from {since})"
        facts.append(CitationFacts(cited, nodes, juris, status))
    return facts


def execute_registry_check(
    case: BenchmarkCase,
    generator_result: GeneratorResult,
    retriever: LocalRetriever,
    registry: Registry,
) -> VerifierResult:
    """Deterministic registry verifier: no LLM call, no override; findings are the registry's alone."""
    assert not getattr(case, "fault_events", None), f"Isolation breach: case '{case.case_id}'"
    t0 = time.time()
    parsed = parse_case_facsimiles(case.inputs)  # the application, never gold facts
    state = parsed.state or "IN"
    findings: list[dict[str, str]] = []
    consulted: list[str] = []
    for f in registry_facts(generator_result, registry, retriever, parsed.case_date):
        cited = f.citation
        if f.nodes is None:
            findings.append({"class": "F1", "clause_id": cited, "reason": "other", "rationale": f"'{cited}' names nothing in the corpus."})
            continue
        consulted += f.nodes
        alien = [j for j in f.jurisdiction if j not in {state, "IN", "unknown"}]
        if alien:
            findings.append({"class": "F2", "clause_id": cited, "reason": "wrong_jurisdiction",
                             "rationale": f"'{cited}' is from jurisdiction {alien[0]}, not {state}."})
        stale = [k for k, v in f.status.items() if v.startswith(
            (CurrencyVerdict.SUPERSEDED.value, CurrencyVerdict.PARTIALLY_SUPERSEDED.value))]
        if stale:
            findings.append({"class": "F3", "clause_id": cited, "reason": "not_in_force",
                             "rationale": f"'{cited}' is not in force on {parsed.case_date} ({stale[0]})."})
    flags = [flag(f) for f in findings]
    cited_set = set(generator_result.cited_rules)
    return VerifierResult(
        case_id=case.case_id,
        verifier_id=f"Arm-4-{registry.name}",
        independence_config=registry.name,
        verdict="FLAG" if findings else "PASS",
        is_flagged=bool(findings),
        flagged_faults=flags,
        audit_reason=" | ".join(f["rationale"] for f in findings),
        latency_sec=round(time.time() - t0, 4),
        prompt_tokens=0,
        completion_tokens=0,
        raw_output={"findings": findings},
        evidence_ids=[n for n in dict.fromkeys(consulted) if n not in cited_set],
        risk=1.0 if findings else 0.0,
        findings=findings,
    )


def execute_registry_llm(
    case: BenchmarkCase,
    generator_result: GeneratorResult,
    retriever: LocalRetriever,
    registry: Registry,
    model: str | None = None,
    variant: str = "support",
    taxonomy: bool = False,
    labels: dict[str, str] | None = None,
    no_record: bool = False,
) -> VerifierResult:
    """reg-real-llm: an LLM verifier given the registry's facts as evidence (no deterministic verdict). With
    ``no_record`` (D49, R4n) an entry the registry links to nothing reads "no_amendment_recorded", not "in_force":
    the registry records amendments, so it cannot tell an unamended clause from a dropped link."""
    parsed = parse_case_facsimiles(case.inputs)
    lines = []
    for f in registry_facts(generator_result, registry, retriever, parsed.case_date):
        if f.nodes is None:
            lines.append(f"- {f.citation}: not found in the corpus")
        elif not f.nodes:
            lines.append(f"- {f.citation}: no registry entry; document jurisdiction {', '.join(f.jurisdiction)}")
        else:
            shown = {k: NO_RECORD_STATUS if no_record and v == CurrencyVerdict.IN_FORCE.value else v
                     for k, v in f.status.items()}
            status = "; ".join(f"{k}: {v}" for k, v in shown.items()) or "no application date"
            lines.append(f"- {f.citation}: registry entries {', '.join(f.nodes)}; jurisdiction "
                         f"{', '.join(f.jurisdiction)}; status on {parsed.case_date}: {status}")
    extra = "\n[CLAUSE REGISTRY LOOKUP OF THE GENERATOR'S CITATIONS]\n" + ("\n".join(lines) or "(no citations)") + "\n"
    res = llm_verdict(case, generator_result, "\n---\n".join(generator_result.retrieved_chunks),
                      f"Arm-4-{registry.name}-llm", f"{registry.name}-llm", model, variant, taxonomy, extra, labels)
    res.retrieved_chunks = generator_result.retrieved_chunks
    res.retrieved_chunk_ids = list(generator_result.retrieved_chunk_ids)
    res.evidence_ids = list(generator_result.retrieved_chunk_ids)
    return res


NO_RECORD_STATUS = "no_amendment_recorded"
AMEND_QUOTE_LABEL = "Text of the amending instrument"


def amendment_quotes(generator_result: GeneratorResult, registry: Registry, retriever: LocalRetriever) -> list[str]:
    """R3 (D37): for each cited clause with a registry link, the link's verbatim ``evidence_quote``, one line each,
    in citation order, deduplicated. Quotes only: no status, date, relation or target clause is added."""
    lines: list[str] = []
    for cited in generator_result.cited_rules:
        nodes = set(resolve_citation(cited, registry, retriever) or [])
        for e in registry.graph.edges:
            quote = " ".join(e.evidence.quote_text.split())
            line = f'- {cited}: "{quote}"'
            if e.from_node in nodes and quote and line not in lines:
                lines.append(line)
    return lines


def execute_amend_quote(
    case: BenchmarkCase,
    generator_result: GeneratorResult,
    retriever: LocalRetriever,
    registry: Registry,
    model: str | None = None,
    variant: str = "validity",
) -> VerifierResult:
    """R3, validity-amendquote: the generator's evidence plus, under AMEND_QUOTE_LABEL, the amending instrument's
    own words for each cited clause the registry links. With no quote the prompt equals the plain variant's."""
    lines = amendment_quotes(generator_result, registry, retriever)
    extra = f"\n[{AMEND_QUOTE_LABEL.upper()}]\n" + "\n".join(lines) + "\n" if lines else ""
    res = llm_verdict(case, generator_result, "\n---\n".join(generator_result.retrieved_chunks),
                      "Arm-4-amendquote", "amendquote", model, variant, False, extra)
    res.retrieved_chunks = generator_result.retrieved_chunks
    res.retrieved_chunk_ids = list(generator_result.retrieved_chunk_ids)
    res.evidence_ids = list(generator_result.retrieved_chunk_ids)
    return res


def execute_verify_independent(
    case: BenchmarkCase,
    generator_result: GeneratorResult,
    retriever: LocalRetriever,
    independence_config: str = "100-neutral",
    model: str | None = None,
    variant: str = "support",
    taxonomy: bool = False,
    labels: dict[str, str] | None = None,
) -> VerifierResult:
    """Config 100 or 100-neutral: an LLM verifier over its own retrieval only."""
    if independence_config not in LLM_CONFIGS:
        raise ValueError(f"execute_verify_independent runs {LLM_CONFIGS}, not '{independence_config}'")
    parsed = parse_case_facsimiles(case.inputs)
    query = (neutral_query(parsed) if independence_config == "100-neutral"
             else audit_query(parsed, STATE_NAMES.get(parsed.state or "", "India")))
    hits = retriever.retrieve(query, top_k=5)
    res = llm_verdict(case, generator_result, "\n---\n".join(retriever.format_chunk(h.chunk) for h in hits),
                      "Arm-4-Independent", independence_config, model, variant, taxonomy, labels=labels)
    res.retrieved_chunks = [retriever.format_chunk(h.chunk) for h in hits]
    res.retrieved_chunk_ids = [h.chunk.chunk_id for h in hits]
    res.evidence_ids = list(res.retrieved_chunk_ids)
    return res
