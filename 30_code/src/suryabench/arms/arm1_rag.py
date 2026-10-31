"""Arm 1: Single-turn RAG generator using retrieved chunks and LLM inference."""

import time
from dataclasses import dataclass
from typing import Any

from suryabench.arms.llm_client import as_str_list, call_llm_json
from suryabench.arms.tools.case_reader import parse_case_facsimiles
from suryabench.cases.schema import BLOCKING_STAGES, BenchmarkCase
from suryabench.gate0.retriever import LocalRetriever


@dataclass
class Arm1ExecutionResult:
    """Execution telemetry and diagnostic outputs for Arm 1 RAG."""

    case_id: str
    arm_id: str
    decision: str
    is_approved: bool
    cited_rules: list[str]
    root_cause: str | None
    blocking_stage: str | None
    subsidy_amount_inr: float | None
    computed: list[dict[str, Any]]
    retrieved_chunks: list[str]
    retrieved_chunk_ids: list[str]
    latency_sec: float
    prompt_tokens: int
    completion_tokens: int
    raw_output: dict[str, Any]


# Names the LLM may use; classifier F6/F7 read `field` (sanctioned_kw, saturation_pct, excess_kw).
BOUND_FIELDS = (
    "sanctioned_kw", "connected_kw", "proposed_kw", "dt_capacity_kva",
    "cumulative_solar_kw", "saturation_pct", "excess_kw", "subsidy_amount_inr", "days_elapsed",
)
SOURCE_FIELDS = (
    "sanctioned_load_kw", "connected_load_kw", "contract_demand_kva", "proposed_capacity_kw",
    "dt_capacity_kva", "existing_solar_kw", "cumulative_solar_kw",
)


STATE_NAMES = {"MH": "Maharashtra", "RJ": "Rajasthan", "GJ": "Gujarat", "KA": "Karnataka", "TN": "Tamil Nadu",
               "DL": "Delhi", "UP": "Uttar Pradesh"}


def application_query(case: BenchmarkCase) -> str:
    """Generator retrieval query: the question the workflow stage raises, plus key application facts.

    Built only from the facsimiles. Raw facsimile text as a query retrieves tariff tables, not
    rules (dense similarity to bill-like text), so the query is phrased as the regulatory question.
    """
    p = parse_case_facsimiles(case.inputs)
    state = STATE_NAMES.get(p.state or "", "India")
    stage = (p.application_stage or "").lower()
    if "subsidy" in stage:
        q = "What central financial assistance (CFA) per kWp applies under PM Surya Ghar for this rooftop solar system?"
    elif "equipment" in stage:
        q = "Are ALMM-listed modules and domestic content (DCR) mandatory for this subsidised rooftop solar system?"
    elif stage == "technical feasibility":
        q = f"Within how many days must the technical feasibility study be completed in {state}, and when is it deemed accepted?"
    else:
        q = f"What distribution transformer hosting limit and capacity limit versus sanctioned load apply in {state}?"
    return (f"{q} {state}, {p.consumer_category or 'consumer'}, {p.proposed_capacity_kw} kW proposed, "
            f"sanctioned load {p.sanctioned_load_kw} kW.")


def parse_blocking_stage(raw: Any) -> str | None:
    """Normalise the model's blocking_stage; null-like values mean 'not blocked'."""
    if raw is None:
        return None
    stage = str(raw).strip().lower().replace(" ", "_").replace("-", "_")
    return None if stage in {"", "none", "null", "n/a"} else stage


def parse_bound_values(raw: Any) -> list[dict[str, Any]]:
    """Normalise the LLM's `computed` list into field-level provenance records.

    Each record: {"field", "value", "tool": "llm_direct", "inputs": {source_field: value}}.
    `inputs` names the application field each value was read from, which is what
    separates a binding error (F6) from a correct binding. Malformed entries are dropped.
    """
    records: list[dict[str, Any]] = []
    for entry in raw if isinstance(raw, list) else []:
        if not isinstance(entry, dict) or not isinstance(entry.get("field"), str):
            continue
        try:
            value = float(entry["value"])
        except (KeyError, TypeError, ValueError):
            continue
        inputs = entry.get("inputs")
        records.append({
            "field": entry["field"],
            "value": value,
            "tool": "llm_direct",
            "inputs": inputs if isinstance(inputs, dict) else {},
        })
    return records


def execute_arm1_rag(
    case: BenchmarkCase,
    retriever: LocalRetriever,
    model: str | None = None,
    top_k: int = 5,
) -> Arm1ExecutionResult:
    """Execute Arm 1 (single-turn RAG generator).

    Retrieves top_k relevant regulatory chunks from the 52-document corpus,
    presents surface facsimiles, and queries the LLM with constrained JSON decoding.
    """
    t0 = time.time()
    case_date = parse_case_facsimiles(case.inputs).case_date or "the application date"

    # 1. Retrieve evidence chunks
    search_results = retriever.retrieve(application_query(case), top_k=top_k)
    retrieved_texts = [retriever.format_chunk(r.chunk) for r in search_results]
    context_str = "\n---\n".join(retrieved_texts)

    # 2. Formulate Prompt
    prompt = f"""You are an Indian Rooftop Solar Interconnection and Regulatory Compliance Verification Agent.
Evaluate this application on date {case_date}:

[DOCUMENT 1: ELECTRICITY BILL FACSIMILE]
{case.inputs.bill}

[DOCUMENT 2: SOLAR EPC PROPOSAL FACSIMILE]
{case.inputs.proposal}

[DOCUMENT 3: DISCOM PORTAL STATUS FACSIMILE]
{case.inputs.portal_state}

[RETRIEVED REGULATORY CONTEXT]
{context_str}

Evaluate whether the application is technically and regulatorily eligible for approval.
Determine:
1. "decision": "APPROVED", "REJECTED", or "ABSTAIN" (if mandatory documentation is unreadable or missing)
2. "root_cause": specific regulatory breach or null if approved
   Also give "blocking_stage": the stage at which this application is blocked, exactly one of {", ".join(BLOCKING_STAGES)}; null if it can be approved as submitted
3. "cfa_subsidy_inr": exact Central Financial Assistance in INR or 0
4. "cited_rules": list of exact clause ids copied from the clause_ids field of the [SOURCE ...] headers of the evidence you relied on (e.g. "MH-C3-001#cl-5.2"); if a passage you relied on shows clause_ids=none, cite its document id (the part of chunk_id before '#'). Never cite chunk ids, topic names, titles or paraphrases
5. "next_action": recommended operational action
6. "computed": every value you read from the documents or calculated, as a list of
   {{"field": <one of {", ".join(BOUND_FIELDS)}>, "value": <number>,
     "inputs": {{<source field>: <number>, ...}}}}
   "inputs" names the application field each number was read from, one of:
   {", ".join(SOURCE_FIELDS)}.
   A value read directly from a document has one input (the field it was read from);
   a calculated value lists every input it was calculated from.

Respond in strict JSON with keys "decision", "root_cause", "blocking_stage", "cfa_subsidy_inr", "cited_rules", "next_action", "computed".
"""

    # No fallback: a failed call must fail the run (retained in results/failed/),
    # never be replaced by a synthetic answer.
    output, p_tok, c_tok = call_llm_json(prompt=prompt, model=model, temperature=0.0)

    elapsed = time.time() - t0
    decision = str(output.get("decision", "REJECTED")).upper()
    is_approved = decision == "APPROVED"

    return Arm1ExecutionResult(
        case_id=case.case_id,
        arm_id="Arm-1",
        decision=decision,
        is_approved=is_approved,
        cited_rules=as_str_list(output.get("cited_rules")),
        root_cause=output.get("root_cause"),
        blocking_stage=parse_blocking_stage(output.get("blocking_stage")),
        subsidy_amount_inr=output.get("cfa_subsidy_inr"),
        computed=parse_bound_values(output.get("computed")),
        retrieved_chunks=retrieved_texts,
        retrieved_chunk_ids=[r.chunk.chunk_id for r in search_results],
        latency_sec=round(elapsed, 4),
        prompt_tokens=p_tok,
        completion_tokens=c_tok,
        raw_output=output,
    )
