"""Arm 2: tool-using agent, a bounded ReAct loop (plan D7, 2026-10-01).

Each step the model returns one action: ``corpus_search`` (retrieve more regulatory text),
``read_application`` (re-read one application document), ``compute`` (run a pure calculator whose
every limit and input the model supplies) or ``final`` (the decision). Nothing decides for the model:
the calculators hold no regulatory values (``tools/calculators.py``), and the facsimile parser is not
used to bind inputs or to abstain. The model reads the documents, including any ``[UNREADABLE]``
fields, and abstains itself. The values it bound and computed (``final.computed``) are what F6/F7
score.

``evidence`` = (ids, rendered texts) fixes the evidence set: the controlled-exposure conditions and
Arm 2-O inject it, and ``corpus_search`` then returns no new text (the condition defines the record).
``critique`` (Arm 5) adds the model's initial determination and a verifier's critique.

Before 2026-10-01 Arm 2 was one call after fixed tool calls whose outputs (and, in the saved test
runs, whose PASS/FAIL verdicts) carried hard-coded current limits; see DECISIONS.md.
"""

import json
import time
from dataclasses import dataclass
from typing import Any

from suryabench.arms.arm1_rag import (
    BOUND_FIELDS,
    SOURCE_FIELDS,
    application_query,
    parse_blocking_stage,
    parse_bound_values,
)
from suryabench.arms.llm_client import as_str_list, call_llm_json
from suryabench.arms.tools.calculators import CALCULATOR_DOC, run_calculator
from suryabench.arms.tools.case_reader import parse_case_facsimiles
from suryabench.cases.schema import BLOCKING_STAGES, BenchmarkCase
from suryabench.core.exceptions import InvalidModelOutput
from suryabench.gate0.retriever import LocalRetriever

MAX_STEPS = 6
DECISIONS = {"APPROVED", "REJECTED", "AMEND", "ABSTAIN"}
SYSTEM = "You are a regulatory compliance agent for Indian rooftop-solar grid-connection applications. Respond in strict JSON."


@dataclass
class Arm2ExecutionResult:
    """Execution telemetry and diagnostic outputs for Arm 2 (and Arm 2-O / Arm 5, which reuse it)."""

    case_id: str
    arm_id: str
    decision: str
    is_approved: bool
    cited_rules: list[str]
    root_cause: str | None
    blocking_stage: str | None
    subsidy_amount_inr: float | None
    computed: list[dict[str, Any]]
    tool_outputs: dict[str, Any]
    retrieved_chunks: list[str]
    retrieved_chunk_ids: list[str]
    latency_sec: float
    prompt_tokens: int
    completion_tokens: int
    raw_output: dict[str, Any]


def _documents(case: BenchmarkCase) -> dict[str, str]:
    return {"bill": case.inputs.bill, "proposal": case.inputs.proposal, "portal": case.inputs.portal_state}


def _prompt(case: BenchmarkCase, case_date: str, evidence: list[str], transcript: list[str], step: int,
            closed: bool, critique: str | None) -> str:
    docs = _documents(case)
    search = ("corpus_search is not available: the evidence above is the complete regulatory record for this "
              "application." if closed else "corpus_search returns the 5 most relevant further passages of the corpus.")
    last = "This is your last step: reply with action \"final\"." if step >= MAX_STEPS else ""
    steps = "\n".join(transcript) or "(none yet)"
    return f"""Evaluate this rooftop-solar application as of {case_date}.

[APPLICATION DOCUMENTS]
Electricity bill:
{docs["bill"]}

EPC proposal:
{docs["proposal"]}

DISCOM portal status:
{docs["portal"]}

[REGULATORY EVIDENCE]
{chr(10).join(evidence) or "(none)"}

[CALCULATORS] (pure arithmetic: you supply every limit, rate and input value)
{CALCULATOR_DOC}

How to decide:
- For every requirement the application must meet, find the governing rule in the regulatory evidence, read
  the limit or condition it states, read the needed values from the application documents yourself, and compare.
- Decide "APPROVED" if the application meets every governing rule; "REJECTED" or "AMEND" if it breaches one;
  "ABSTAIN" if a value required to decide is missing or unreadable in the documents, or if two authoritative
  current sources genuinely conflict.
- Cite exact clause ids from the clause_ids field of the [SOURCE ...] headers. If a passage you relied on shows
  clause_ids=none, cite its document id (the part of chunk_id before '#'). Never cite chunk ids, titles or paraphrases.
- {search}
{critique or ""}
Reply with exactly one action per turn, as JSON:
{{"thought": "...", "action": "corpus_search", "args": {{"query": "..."}}}}
{{"thought": "...", "action": "read_application", "args": {{"document": "bill" | "proposal" | "portal"}}}}
{{"thought": "...", "action": "compute", "args": {{"tool": "<calculator name>", "args": {{...}}}}}}
{{"thought": "...", "action": "final", "args": {{
  "decision": "APPROVED" | "REJECTED" | "AMEND" | "ABSTAIN",
  "root_cause": "the rule breached and how, or null",
  "blocking_stage": one of {", ".join(BLOCKING_STAGES)}, or null if it can be approved as submitted,
  "cfa_subsidy_inr": the Central Financial Assistance the governing rule gives this application, or 0,
  "cited_rules": ["<clause id>", ...],
  "next_action": "...",
  "computed": [{{"field": <one of {", ".join(BOUND_FIELDS)}>, "value": <number>,
                 "inputs": {{<one of {", ".join(SOURCE_FIELDS)}>: <number>, ...}}}}, ...]}}}}
"computed" lists every value you read from the documents or calculated; "inputs" names the application field
each number came from.

[STEPS SO FAR]
{steps}

Step {step} of {MAX_STEPS}. {last}"""


def _final_args(out: dict[str, Any]) -> dict[str, Any] | None:
    if str(out.get("action", "")).lower() != "final":
        return None
    args = out.get("args")
    return args if isinstance(args, dict) and "decision" in args else out


def execute_arm2_agent(
    case: BenchmarkCase,
    retriever: LocalRetriever,
    model: str | None = None,
    top_k: int = 5,
    evidence: tuple[list[str], list[str]] | None = None,
    critique: str | None = None,
    search: bool | None = None,
) -> Arm2ExecutionResult:
    """Run the bounded ReAct loop on the application facsimiles (never on gold facts). ``search`` opens
    ``corpus_search`` over given evidence (Arm 5 recovery, D31); by default it is closed when evidence is given.
    A reply with no final decision, or a decision outside the label set, is an invalid output (D30)."""
    t0 = time.time()
    case_date = parse_case_facsimiles(case.inputs).case_date or "the application date"
    closed = evidence is not None if search is None else not search
    if evidence is None:
        results = retriever.retrieve(application_query(case), top_k=top_k)
        ids, texts = [r.chunk.chunk_id for r in results], [retriever.format_chunk(r.chunk) for r in results]
    else:
        ids, texts = list(evidence[0]), list(evidence[1])
    initial = list(texts)

    transcript: list[str] = []
    steps: list[dict[str, Any]] = []
    p_sum = c_sum = 0
    final: dict[str, Any] | None = None
    for step in range(1, MAX_STEPS + 2):  # the extra turn is the forced final
        prompt = _prompt(case, case_date, initial, transcript, min(step, MAX_STEPS), closed, critique)
        if step > MAX_STEPS:
            prompt += "\nYou have used every step. Reply now with action \"final\" and its args."
        out, p_tok, c_tok = call_llm_json(prompt=prompt, system_prompt=SYSTEM, model=model, temperature=0.0)
        p_sum, c_sum = p_sum + p_tok, c_sum + c_tok
        final = _final_args(out)
        if final is not None:
            steps.append({"action": "final"})
            break
        if step > MAX_STEPS:
            raise InvalidModelOutput(f"{case.case_id}: no final decision after {MAX_STEPS} steps and a forced final turn")
        action = str(out.get("action", ""))
        raw_args = out.get("args")
        args: dict[str, Any] = raw_args if isinstance(raw_args, dict) else {}
        if action == "corpus_search" and not closed:
            hits = retriever.retrieve(str(args.get("query", "")), top_k=top_k)
            new = [h for h in hits if h.chunk.chunk_id not in ids]
            ids += [h.chunk.chunk_id for h in new]
            texts += [retriever.format_chunk(h.chunk) for h in new]
            obs = "\n".join(retriever.format_chunk(h.chunk) for h in hits) or "no passages found"
        elif action == "corpus_search":
            obs = "corpus_search is not available: the evidence shown is the complete record."
        elif action == "read_application":
            obs = _documents(case).get(str(args.get("document", "")), "unknown document; use bill, proposal or portal")
        elif action == "compute":
            obs = json.dumps(run_calculator(str(args.get("tool", "")), args.get("args")))
        else:
            obs = f"unknown action '{action}'; use corpus_search, read_application, compute or final"
        steps.append({"action": action, "args": args, "observation": obs[:4000]})
        transcript.append(f"Step {step}: {json.dumps({'action': action, 'args': args})}\nObservation: {obs}")

    assert final is not None
    decision = str(final.get("decision", "")).strip().upper()
    if decision not in DECISIONS:
        raise InvalidModelOutput(f"{case.case_id}: final decision {decision!r} is not one of {sorted(DECISIONS)}")
    subsidy = final.get("cfa_subsidy_inr")
    computed = parse_bound_values(final.get("computed"))
    if isinstance(subsidy, int | float):
        computed.append({"subsidy_amount_inr": float(subsidy)})  # the model's own figure, scored by F7

    return Arm2ExecutionResult(
        case_id=case.case_id,
        arm_id="Arm-2",
        decision=decision,
        is_approved=decision == "APPROVED",
        cited_rules=as_str_list(final.get("cited_rules")),
        root_cause=final.get("root_cause"),
        blocking_stage=parse_blocking_stage(final.get("blocking_stage")),
        subsidy_amount_inr=float(subsidy) if isinstance(subsidy, int | float) else None,
        computed=computed,
        tool_outputs={"steps": steps, "closed_evidence": closed},
        retrieved_chunks=texts,
        retrieved_chunk_ids=ids,
        latency_sec=round(time.time() - t0, 4),
        prompt_tokens=p_sum,
        completion_tokens=c_sum,
        raw_output=final,
    )
