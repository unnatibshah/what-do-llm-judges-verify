"""D33 verifier probe: fixed generator answers, so verification is measured apart from generation.

For every dev case and every controlled-exposure plan (``build_exposure``: S-both, S-swap, J, A; the plan's
own skips apply) the probe builds a MATCHED PAIR of fixed answers (``Arm2ExecutionResult``):

- FAULT: cites the planted clause in place of the cluster anchor. Its decision is the trap-implied decision when
  applying the plant is computed to flip the case's approve/block outcome (``outcome_changing=True``), else the
  gold decision (a "basis-only" fault: right outcome, invalid basis).
- CONTROL: the gold decision citing the case's decisive clauses that its evidence shows (D35): in S-swap the
  anchor is removed from the evidence, so the control cites the remaining decisive clauses, and the pair has
  no control when the anchor was the only one.

Both come from one neutral template (decision, cited clause ids, one sentence quoting the basis clause's own
text, blocking stage, the subsidy the basis clause gives when the case claims one), so a pair differs only in
the basis (and, when ``outcome_changing``, in the decision it implies). Condition C adds one gold answer per
case on the decisive clauses (extra controls). Cases whose gold decision is ABSTAIN are left out (an abstention
has no decision basis to swap). A plant computed to give the anchor's outcome is kept as a basis-only fault
(``build_exposure(keep_same_outcome=True)``, D38). The verifier sees exactly the plan's evidence, rendered as the generator's
evidence is rendered (``format_nodes``), at the configuration's metadata level (``render_ids``); it never sees
which answer is the fault. The verifier functions are the D32 ones, unchanged.
"""

import dataclasses
import re
from dataclasses import dataclass
from typing import Any

from suryabench.applicability.schema import ApplicabilityPredicate
from suryabench.arms.arm2_agent import Arm2ExecutionResult
from suryabench.arms.controlled_exposure import (
    build_exposure,
    cluster_anchor,
    format_nodes,
    render_ids,
)
from suryabench.arms.verify_independent import (
    Registry,
    execute_amend_quote,
    execute_registry_check,
    execute_registry_llm,
    execute_verify_independent,
    noisy_registry,
    spurious_registry,
)
from suryabench.arms.verify_reflect import execute_verify_reflect
from suryabench.arms.verify_shared import VerifierResult, execute_verify_shared
from suryabench.cases import rules
from suryabench.cases.schema import BenchmarkCase
from suryabench.core.enums import ExpectedDecision, FaultClass
from suryabench.core.exceptions import InvalidModelOutput
from suryabench.eval.failure_classifier import (
    CLASS_REASON,
    VALIDITY_REASONS,
    FailureClassifier,
    _split_flag,
)
from suryabench.gate0.retriever import LocalRetriever
from suryabench.graph.schema import SupersessionGraph

PLANT_CONDITIONS = ("S-both", "S-swap", "J", "A")
CONDITIONS = ("C", *PLANT_CONDITIONS)
PRIMARY = ("S-both", "J", "A")  # the preregistered primary cells (F3 in S-both, F2 in J, F5 in A)

# name -> (kind, prompt variant, verifier metadata on)
CONFIGS: dict[str, tuple[str, str, bool]] = {
    "support": ("shared", "support", True),
    "validity": ("shared", "validity", True),
    "support-metaoff": ("shared", "support", False),
    "validity-metaoff": ("shared", "validity", False),
    "reflect": ("reflect", "support", True),
    "100-neutral": ("independent", "support", True),
    "reg-real-llm": ("registry-llm", "support", True),
    "reg-oracle": ("registry", "", True),
    "reg-real": ("registry", "", True),
    # D37 information ladder (T2). R3 and R4 are siblings built on R2 (validity, metadata on); R4' is R4 on S-swap.
    "validity-amendquote": ("amendquote", "validity", True),
    "validity-regstatus": ("registry-llm", "validity", True),
    # E2 "can't confirm": the validity prompt with the reason list that adds currency_unconfirmed
    "validity-cc": ("shared", "validity-cc", True),
    "validity-cc-metaoff": ("shared", "validity-cc", False),
}
# E3 damaged registry (D31 functions, applied to the real registry): R5 reg-<damage>-s<seed> and
# R4 validity-regstatus-<damage>-s<seed>. damage -> (kind, fraction).
DAMAGE: dict[str, tuple[str, float]] = {"drop25": ("drop", 0.25), "drop50": ("drop", 0.50), "spurious10": ("spurious", 0.10)}
DAMAGE_SEEDS = range(5)
DAMAGED = tuple(f"reg-{d}-s{k}" for d in DAMAGE for k in DAMAGE_SEEDS)
CONFIGS.update({n: ("registry", "", True) for n in DAMAGED})
CONFIGS.update({f"validity-regstatus-{n.removeprefix('reg-')}": ("registry-llm", "validity", True) for n in DAMAGED})
# D49 R4n: R4 with a clause the registry links to nothing shown as "no_amendment_recorded" instead of "in_force"
NO_RECORD = "validity-regnorec"
CONFIGS.update({NO_RECORD: ("registry-llm", "validity", True)})
CONFIGS.update({f"{NO_RECORD}-{n.removeprefix('reg-')}": ("registry-llm", "validity", True) for n in DAMAGED})
LLM_CONFIGS = tuple(k for k, v in CONFIGS.items() if v[0] != "registry")

# (configuration, condition) -> ladder rung (D37). Condition C carries the same configuration's false-alarm control
# (R1 and R2 share C's evidence). Damaged registries are labelled by damage level, every seed alike.
_RUNG = {("validity-metaoff", "S-swap"): "R0", ("validity", "S-swap"): "R1", ("validity", "S-both"): "R2",
         ("validity-amendquote", "S-both"): "R3", ("validity-regstatus", "S-both"): "R4",
         ("validity-regstatus", "S-swap"): "R4'", ("reg-real", "S-both"): "R5", ("reg-real", "S-swap"): "R5",
         ("validity-cc-metaoff", "S-swap"): "R0-cc", ("validity-cc", "S-swap"): "R1-cc", ("validity-cc", "S-both"): "R2-cc"}
_RUNG_C = {"validity-metaoff": "R0", "validity": "R1-R2", "validity-amendquote": "R3", "validity-regstatus": "R4",
           "reg-real": "R5", "validity-cc-metaoff": "R0-cc", "validity-cc": "R1-R2-cc"}


def registry_of(config: str) -> str:
    """The registry a configuration consults: its own name for a deterministic one, else the real registry
    (damaged for validity-regstatus-<damage>-s<seed>)."""
    if CONFIGS[config][0] == "registry":
        return config
    for prefix in ("validity-regstatus-", f"{NO_RECORD}-"):
        if config.startswith(prefix):
            return "reg-" + config.removeprefix(prefix)
    return "reg-real"


def rung(config: str, condition: str) -> str | None:
    """The ladder rung a block measures, or None outside the ladder (support, reflect, J, A, ...)."""
    if config == NO_RECORD:
        return "R4n" if condition in {"S-both", "C"} else None
    damaged = ("reg-drop", "reg-spurious", "validity-regstatus-", f"{NO_RECORD}-")
    base = config.rsplit("-s", 1)[0] if config.startswith(damaged) else config
    if base != config:  # damaged: reg-drop25 -> R5-drop25; validity-regstatus-drop25 -> R4-drop25 (R4'- on S-swap)
        damage = base.removeprefix("reg-").removeprefix("validity-regstatus-").removeprefix(f"{NO_RECORD}-")
        if condition not in {"S-both", "S-swap", "C"}:
            return None
        if base.startswith("reg-"):
            return f"R5-{damage}"
        if base.startswith(NO_RECORD):
            return None if condition == "S-swap" else f"R4n-{damage}"
        return f"R4'-{damage}" if condition == "S-swap" else f"R4-{damage}"
    return _RUNG_C.get(config) if condition == "C" else _RUNG.get((config, condition))


def damaged_registries(real: Registry) -> dict[str, Registry]:
    """Every DAMAGED registry, built from the real one (same entries and chunk map; edges dropped or added)."""
    out = {}
    for name in DAMAGED:
        kind, fraction = DAMAGE[name.split("-")[1]]
        seed = int(name.rsplit("-s", 1)[1])
        graph = noisy_registry(real.graph, fraction, seed) if kind == "drop" else spurious_registry(real.graph, fraction, seed)
        out[name] = Registry(name, graph, real.chunk_map)
    return out

_CFA_RULES = {"IN-C1-001#cl-4.1", "IN-C1-002#cl-2"}


@dataclass(frozen=True)
class ProbeItem:
    """One fixed answer and the evidence its verifier sees. ``role``: fault, control, or c-control (condition C)."""

    item_id: str
    pair_id: str
    role: str
    condition: str
    case_id: str
    cluster: str
    planted: str | None
    fault_class: str | None
    outcome_changing: bool
    evidence_ids: list[str]
    answer: Arm2ExecutionResult


def gold_outcome(case: BenchmarkCase) -> tuple[str, str | None]:
    """(decision, blocking stage) of the gold answer."""
    stage = case.expected_answer.blocking_stage if case.expected_answer else None
    return ("REJECTED" if stage else "APPROVED"), stage


def _claimed(case: BenchmarkCase) -> float | None:
    gold = {k: v for c in case.expected_answer.computed for k, v in c.items()} if case.expected_answer else {}
    v = gold.get("claimed_cfa_inr")
    return float(v) if isinstance(v, int | float) else None


def plant_outcome(case: BenchmarkCase, anchor: str, plant: str, implied_flip: bool | None) -> tuple[str, str | None] | None:
    """The trap-implied (decision, blocking stage) when deciding on ``plant`` instead of ``anchor`` provably flips the
    gold approve/block outcome, else None. Capacity and transformer rules: the plan's ``implied_flip`` (N11). CFA
    rules: ``rules.cfa_claim`` on the claimed amount, when the subsidy stage is the only possible blocker."""
    decision, stage = gold_outcome(case)
    flip = implied_flip
    if flip is None and {anchor, plant} <= _CFA_RULES and case.facts.subsidy_claimed:
        claimed = _claimed(case)
        if claimed is not None and stage in {None, "subsidy_approval"}:
            cap = case.facts.proposed_capacity_kw or 0.0
            flip = rules.cfa_claim(plant, cap, int(claimed)).ok != rules.cfa_claim(anchor, cap, int(claimed)).ok
    if not flip:
        return None
    if decision == "APPROVED":
        return "REJECTED", "subsidy_approval" if plant in _CFA_RULES else "technical_feasibility"
    return "APPROVED", None


def _quote(text: str, limit: int = 300) -> str:
    """The clause's own text (table rules and quotes dropped, whitespace collapsed), cut at a word near ``limit``."""
    s = " ".join(re.sub(r"[|\"]|-{3,}", " ", text).split())
    return s if len(s) <= limit else s[:limit].rsplit(" ", 1)[0] + " ..."


def fixed_answer(case: BenchmarkCase, cited: list[str], basis: str, decision: str, stage: str | None,
                 graph: SupersessionGraph, evidence_ids: list[str]) -> Arm2ExecutionResult:
    """The neutral template shared by every probe answer."""
    verb = "approved" if decision == "APPROVED" else f"rejected at the {str(stage).replace('_', ' ')} stage"
    rationale = f"The application is {verb} under {basis}, which provides: \"{_quote(graph.nodes[basis].clause_text_snippet)}\""
    subsidy = None
    if case.facts.subsidy_claimed and basis in _CFA_RULES:
        subsidy = float(rules.cfa_amount(basis, case.facts.proposed_capacity_kw or 0.0))
    return Arm2ExecutionResult(
        case_id=case.case_id, arm_id="probe", decision=decision, is_approved=decision == "APPROVED",
        cited_rules=cited, root_cause=rationale, blocking_stage=stage, subsidy_amount_inr=subsidy, computed=[],
        tool_outputs={}, retrieved_chunks=[], retrieved_chunk_ids=list(evidence_ids), latency_sec=0.0,
        prompt_tokens=0, completion_tokens=0, raw_output={})


def build_items(cases: list[BenchmarkCase], graph: SupersessionGraph, predicates: list[ApplicabilityPredicate],
                retriever: LocalRetriever) -> tuple[list[ProbeItem], dict[str, str]]:
    """(items, skips): matched fault/control pairs per plan plus condition-C controls; skips by '<case>#<cond>'."""
    items: list[ProbeItem] = []
    skips: dict[str, str] = {}
    meta = retriever.meta
    retriever.meta = True  # the generator's evidence ids, as the exposure runs build them
    try:
        for case in cases:
            for cond in CONDITIONS:
                key = f"{case.case_id}#{cond}"
                if case.expected_decision == ExpectedDecision.ABSTAIN:
                    skips[key] = "gold decision is ABSTAIN (no decision basis to swap)"
                    continue
                plan, why = build_exposure(case, cond, graph, predicates, retriever.chunk_clauses, keep_same_outcome=True)
                if plan is None:
                    skips[key] = why
                    continue
                ids, _ = format_nodes(plan.node_ids, graph, retriever)
                decisive = [r.rule_id for r in case.applicable_rules]
                anchor = cluster_anchor(case, graph)
                gold_dec, gold_stage = gold_outcome(case)
                basis = anchor if anchor in decisive else decisive[0]
                cluster = str(case.cluster_id or anchor)
                seen = shown_clauses(ids, retriever)
                grounded = [r for r in decisive if r in seen]  # D35: a control cites only what its evidence shows
                control = fixed_answer(case, grounded, basis if basis in grounded else grounded[0], gold_dec, gold_stage,
                                       graph, ids) if grounded else None
                if plan.fault_event is None:  # C: every decisive clause is shown
                    assert control is not None, key
                    items.append(ProbeItem(f"{key}#c-control", key, "c-control", cond, case.case_id, cluster, None, None,
                                           False, ids, control))
                    continue
                plant = plan.fault_event.gold_evidence[0]
                implied = plant_outcome(case, basis, plant, plan.implied_flip)
                dec, stage = implied or (gold_dec, gold_stage)
                cited = [plant if r == basis else r for r in decisive]
                fault = fixed_answer(case, cited, plant, dec, stage, graph, ids)
                fc = plan.fault_event.fault_class.value
                if control is None:
                    skips[f"{key}#control"] = f"no control: {anchor}, the only decisive clause, is not in the evidence"
                for role, ans in (("fault", fault), ("control", control)):
                    if ans is None:
                        continue
                    items.append(ProbeItem(f"{key}#{role}", key, role, cond, case.case_id, cluster, plant, fc,
                                           implied is not None, ids, ans))
    finally:
        retriever.meta = meta
    return items, skips


def shown_clauses(evidence_ids: list[str], retriever: LocalRetriever) -> set[str]:
    """Clause ids the rendered evidence contains: every clause of each chunk shown, or the clause itself when it was
    rendered as a snippet."""
    return set().union(*(retriever.chunk_clauses.get(i, {i}) for i in evidence_ids))


def evidence_texts(items: list[ProbeItem], graph: SupersessionGraph, retriever: LocalRetriever) -> dict[tuple[str, bool], list[str]]:
    """Every item's evidence rendered at both metadata levels, once, before any thread runs (``retriever.meta`` is
    shared state). Keyed by (pair id, metadata on)."""
    out: dict[tuple[str, bool], list[str]] = {}
    meta = retriever.meta
    try:
        for it in items:
            for m in (True, False):
                if (it.pair_id, m) not in out:
                    retriever.meta = m
                    out[(it.pair_id, m)] = render_ids(it.evidence_ids, graph, retriever)
    finally:
        retriever.meta = meta
    return out


@dataclass
class ProbeContext:
    """What one verification needs besides the item: the unlabelled case (gold fields hidden), the rendered evidence,
    the retriever (100-neutral), the registries, and the metadata-off source labels."""

    cases: dict[str, BenchmarkCase]
    texts: dict[tuple[str, bool], list[str]]
    retriever: LocalRetriever
    registries: dict[str, Registry]
    labels: dict[str, str]


def verify_item(item: ProbeItem, config: str, model: str, ctx: ProbeContext) -> VerifierResult:
    """One verification of one fixed answer. An invalid reply (D30) comes back with verdict INVALID."""
    kind, variant, meta = CONFIGS[config]
    case = ctx.cases[item.case_id]
    view = dataclasses.replace(item.answer, retrieved_chunks=ctx.texts[(item.pair_id, meta)])
    labels = None if meta else ctx.labels
    try:
        if kind == "shared":
            return execute_verify_shared(case, view, model=model, variant=variant, labels=labels)
        if kind == "reflect":
            return execute_verify_reflect(case, view, model=model, variant=variant, labels=labels)
        if kind == "independent":
            return execute_verify_independent(case, view, ctx.retriever, config, model=model, variant=variant)
        if kind == "registry-llm":
            return execute_registry_llm(case, view, ctx.retriever, ctx.registries[registry_of(config)], model, variant,
                                        no_record=config.startswith(NO_RECORD))
        if kind == "amendquote":
            return execute_amend_quote(case, view, ctx.retriever, ctx.registries[registry_of(config)], model, variant)
        return execute_registry_check(case, view, ctx.retriever, ctx.registries[registry_of(config)])
    except InvalidModelOutput as e:
        return VerifierResult(case_id=item.case_id, verifier_id="probe", independence_config=config, verdict="INVALID",
                              is_flagged=False, flagged_faults=[], audit_reason="invalid model output", latency_sec=0.0,
                              prompt_tokens=0, completion_tokens=0, raw_output={"invalid_output": str(e)[:500]}, model=model)


def score(item: ProbeItem, res: VerifierResult, classifier: FailureClassifier) -> dict[str, bool]:
    """Per item (D32 matching): right-reason catch (planted clause named with the reason of its class), clause-only
    catch (named, any reason), wrong-reason catch (named, never with the right reason), any finding, and a finding
    with a validity reason. D30: an invalid reply catches nothing and counts as a finding (a false alarm).
    E2 (D37): a ``currency_unconfirmed`` finding is scored apart (``cant_confirm``): it is neither a catch nor a
    false alarm, so a reply whose only findings say "can't confirm" counts as no finding."""
    invalid = res.verdict == "INVALID"
    split = [_split_flag(f) for f in res.flagged_faults]
    findings = [f for f in split if f[2] != "currency_unconfirmed"]
    cant_confirm = len(findings) < len(split)
    plant = item.planted
    want = CLASS_REASON.get(FaultClass(item.fault_class)) if item.fault_class else None

    def names(clause: str) -> bool:
        if not plant or not clause:
            return False
        return bool(classifier._names(clause) & {plant}) or (item.fault_class == "F3" and clause.split("#")[0] == plant.split("#")[0])

    clause = any(names(cl) for _, cl, _ in findings)
    right = any(names(cl) and r == want for _, cl, r in findings)
    flagged = bool(findings) or (res.is_flagged and not split)  # a FLAG with only can't-confirm findings is not one
    return {"invalid": invalid, "any": invalid or flagged, "clause": clause, "right": right,
            "wrong": clause and not right, "validity_reason": any(r in VALIDITY_REASONS for _, _, r in findings),
            "cant_confirm": cant_confirm}


def record(item: ProbeItem, config: str, model: str, res: VerifierResult, classifier: FailureClassifier) -> dict[str, Any]:
    """The saved row for one (item, configuration, verifier model)."""
    return {"item_id": item.item_id, "pair_id": item.pair_id, "role": item.role, "condition": item.condition,
            "case_id": item.case_id, "cluster": item.cluster, "planted": item.planted, "fault_class": item.fault_class,
            "outcome_changing": item.outcome_changing, "config": config, "rung": rung(config, item.condition),
            "model": model, "prompt_sha256": res.prompt_sha256,
            "decision": item.answer.decision, "cited": item.answer.cited_rules, "verdict": res.verdict,
            "flags": res.flagged_faults, "rationale": res.audit_reason[:600], "latency_sec": res.latency_sec,
            "prompt_tokens": res.prompt_tokens, "completion_tokens": res.completion_tokens,
            "invalid_output": res.raw_output.get("invalid_output") if res.verdict == "INVALID" else None,
            **score(item, res, classifier)}
