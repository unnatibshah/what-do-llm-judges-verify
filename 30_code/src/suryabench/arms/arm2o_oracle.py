"""Arm 2-O: diagnostic oracle. The Arm 2 agent with the case's decisive clauses as its fixed evidence.

Per protocol §13: identical to Arm 2 except that retrieval is replaced by the ground-truth governing
clauses, so Arm 2 vs Arm 2-O separates retrieval-attributed from reasoning-attributed error.

This is the one arm that reads a gold field, by design and explicitly: ``case.applicable_rules`` (the
runner passes Arm 2-O the unlabelled case with that field kept). The clauses are rendered exactly as
retrieved chunks (``controlled_exposure.format_nodes``), so Arm 2-O equals controlled-exposure condition C.
"""

from suryabench.arms.arm2_agent import Arm2ExecutionResult, execute_arm2_agent
from suryabench.arms.controlled_exposure import format_nodes
from suryabench.cases.schema import BenchmarkCase
from suryabench.gate0.retriever import LocalRetriever
from suryabench.graph.schema import SupersessionGraph


def execute_arm2o_oracle(
    case: BenchmarkCase,
    graph: SupersessionGraph,
    retriever: LocalRetriever,
    model: str | None = None,
) -> Arm2ExecutionResult:
    """Run Arm 2 on the decisive clauses only (oracle access to ``case.applicable_rules``)."""
    evidence = format_nodes([r.rule_id for r in case.applicable_rules], graph, retriever)
    result = execute_arm2_agent(case=case, retriever=retriever, model=model, evidence=evidence)
    result.arm_id = "Arm-2-O"
    return result
