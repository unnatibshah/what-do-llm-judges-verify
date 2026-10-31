"""Arm 5: closed-loop recovery (exploratory, not preregistered).

When a verifier FLAGs a generator output, its critique (``flagged_faults`` and ``audit_reason``) is
given back to the Arm 2 generator with the generator's own evidence and initial determination, and
the generator re-evaluates. The revised output is scored like any generator output, so the runner
can measure:

- Recovery Rate (RR): initially wrong cases that end correct, over initially wrong cases;
- Degradation Rate (DR): initially correct cases that end wrong, over initially correct cases;
- net effect: (recovered - degraded) / cases,

both on full correctness and on the decision outcome alone (plan item 1.16), where the final answer is the
revision if the verifier flagged, and the initial answer if it passed. The revision re-runs the Arm 2 loop from
the generator's evidence plus the critique, and may search the corpus again (D31, 2026-10-01: under S-swap
the successor clause is otherwise not available to recover with).
"""

from suryabench.arms.arm2_agent import Arm2ExecutionResult, execute_arm2_agent
from suryabench.arms.verify_shared import VerifierResult
from suryabench.cases.schema import BenchmarkCase
from suryabench.gate0.retriever import LocalRetriever


def critique_block(initial: Arm2ExecutionResult, verifier: VerifierResult) -> str:
    """The prompt section that hands a verifier's critique back to the generator."""
    return f"""
[YOUR INITIAL DETERMINATION]
Decision: {initial.decision}
Root cause: {initial.root_cause}
Blocking stage: {initial.blocking_stage}
Cited rules: {initial.cited_rules}
CFA: Rs {initial.subsidy_amount_inr}

[VERIFIER CRITIQUE]
Findings: {verifier.findings or verifier.flagged_faults}
Reason: {verifier.audit_reason}

Re-evaluate your initial determination in light of the critique. Check each finding against the regulatory
evidence and the application documents: revise the determination where the critique is right, and keep it
where the critique is wrong. Your final answer replaces the initial determination.
"""


def execute_recovery(
    case: BenchmarkCase,
    initial: Arm2ExecutionResult,
    verifier: VerifierResult,
    retriever: LocalRetriever,
    model: str | None = None,
) -> Arm2ExecutionResult:
    """Revised Arm 2 output after a FLAG: the initial evidence, corpus_search open, the calculators and the critique."""
    assert verifier.is_flagged, "recovery runs only on a flagged output"
    revised = execute_arm2_agent(
        case=case,
        retriever=retriever,
        model=model,
        evidence=(initial.retrieved_chunk_ids, initial.retrieved_chunks),
        critique=critique_block(initial, verifier),
        search=True,
    )
    revised.arm_id = "Arm-5"
    return revised
