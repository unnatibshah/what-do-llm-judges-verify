"""Arm 3-Reflect: two-pass reflective verifier over the shared evidence (compute control, protocol §13).

Pass 1 critiques the generator's output against the same evidence Arm 3 sees; pass 2 adjudicates from
that critique. It separates "more work on the same evidence" from "independent evidence".
"""

import time

from suryabench.arms.arm1_rag import Arm1ExecutionResult
from suryabench.arms.arm2_agent import Arm2ExecutionResult
from suryabench.arms.llm_client import call_llm_json
from suryabench.arms.verify_shared import (
    FAULT_TAXONOMY,
    TASKS,
    VerifierResult,
    application_context,
    generator_block,
    output_spec,
    parse_verdict,
    prompt_sha256,
    relabel,
    unlabel,
)
from suryabench.cases.schema import BenchmarkCase


def execute_verify_reflect(
    case: BenchmarkCase,
    generator_result: Arm1ExecutionResult | Arm2ExecutionResult,
    model: str | None = None,
    variant: str = "support",
    taxonomy: bool = False,
    labels: dict[str, str] | None = None,
) -> VerifierResult:
    """Arm 3-Reflect: critique, then adjudicate, over exactly Arm 3's evidence."""
    assert not getattr(case, "fault_events", None), (
        f"Isolation breach: case '{case.case_id}' fault_events must be empty/inaccessible in verification path"
    )
    t0 = time.time()
    context_str = "\n---\n".join(generator_result.retrieved_chunks)
    classes = f"\n\n{FAULT_TAXONOMY}" if taxonomy else ""

    pass1_prompt = f"""You are a critical regulatory auditor (stage 1 of 2: reflection).
{TASKS[variant]}

{generator_block(generator_result)}

{application_context(case, generator_result)}

[REGULATORY EVIDENCE]
{context_str}{classes}

Write a careful critique of possible flaws. Reply in strict JSON:
{{"reflection": "<critique>", "preliminary_verdict": "FLAG" or "PASS"}}
"""
    # No fallback: a failed call must fail the run (retained in results/failed/).
    sent1 = relabel(pass1_prompt, labels)
    p1_out, p1_p, p1_c = call_llm_json(prompt=sent1, model=model, temperature=0.0)

    pass2_prompt = f"""You are the final verifier (stage 2 of 2: adjudication).
Your stage-1 critique:
{p1_out.get('reflection')}

{generator_block(generator_result)}{classes}

{output_spec(taxonomy)}
"""
    sent2 = relabel(pass2_prompt, labels)
    p2_out, p2_p, p2_c = call_llm_json(prompt=sent2, model=model, temperature=0.0)
    verdict, risk, _findings, _ = parse_verdict(p2_out, taxonomy)
    findings, flags = unlabel(_findings, labels)

    return VerifierResult(
        case_id=case.case_id,
        verifier_id="Arm-3-Reflect",
        independence_config="000-reflect",
        verdict=verdict,
        is_flagged=verdict == "FLAG" or bool(findings),
        flagged_faults=flags,
        audit_reason=f"Reflection: {p1_out.get('reflection', '')} | Findings: "
                     + " | ".join(f["rationale"] for f in findings),
        latency_sec=round(time.time() - t0, 4),
        prompt_tokens=p1_p + p2_p,
        completion_tokens=p1_c + p2_c,
        raw_output={"pass1": p1_out, "pass2": p2_out},
        retrieved_chunks=generator_result.retrieved_chunks,
        retrieved_chunk_ids=list(generator_result.retrieved_chunk_ids),
        evidence_ids=list(generator_result.retrieved_chunk_ids),
        risk=risk,
        findings=findings,
        model=model,
        prompt_sha256=prompt_sha256(sent1, sent2),
    )
