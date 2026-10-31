"""Arm 3: shared-evidence verifier (independence 000), and the verifier prompt and output used by all.

The verifier sees the generator's output, the application documents and the generator's own evidence.

Output (plan D8, 2026-10-01; D32, 2026-10-02): ``{"verdict": "PASS"|"FLAG", "risk": 0-1, "findings":
[{"clause_id", "reason", "rationale", "class"?}]}``; ``reason`` is a code from the closed set ``REASONS``. A finding names a fault class and the clause (or document) it concerns,
so a catch can be scored at evidence level, not by a class label alone. The old instruction "return every
class that applies" is gone: it rewarded listing classes indiscriminately.

Prompt variants (D26): ``support`` and two paraphrases (``support-p1``, ``support-p2``) ask only whether the
decision is supported by the cited evidence and which cited clauses are a problem; ``validity`` asks of every
cited clause whether it is in force at the case date, from the case's jurisdiction, and applicable.
``taxonomy=True`` adds the fault-class definitions and an optional class per finding (an ablation; off by default).
``validity-cc`` (D37 E2, "can't confirm"): the validity task with a second reason list that adds
``currency_unconfirmed``; every other variant keeps ``REASONS`` byte for byte.
"""

import hashlib
import re
import time
from dataclasses import dataclass, field
from typing import Any

from suryabench.arms.arm1_rag import Arm1ExecutionResult
from suryabench.arms.arm2_agent import Arm2ExecutionResult
from suryabench.arms.llm_client import call_llm_json
from suryabench.cases.schema import BenchmarkCase
from suryabench.core.exceptions import InvalidModelOutput

# Protocol §13 taxonomy, shared verbatim by every verifier prompt that shows it.
FAULT_TAXONOMY = """Fault classes:
- F1 Fabrication: a cited clause does not exist.
- F2 Jurisdiction error: a real, current rule from the wrong jurisdiction (e.g. a Rajasthan rule applied to a Maharashtra case; central IN- rules govern every state).
- F3 Currency error: a real rule of the right jurisdiction that is superseded at the case date.
- F4 Omission: an applicable rule was never retrieved or never cited. Use "F4-R" if the rule is absent from the evidence shown, "F4-C" if it is present in the evidence but not incorporated into the answer.
- F5 Applicability error: a current, in-jurisdiction rule applied to a case it does not govern (e.g. a residential subsidy clause cited for a commercial consumer, or net-metering rules for a gross-metered consumer).
- F6 Input-binding error: correct rule, wrong input values (e.g. connected load used where sanctioned load is required, or a value that does not match the application documents).
- F7 Arithmetic or unit error in a computed value.
- F8 Failure to abstain: two authoritative current sources genuinely conflict, so the correct decision is ABSTAIN.
- F9 Failure to abstain: required case information is absent from the application documents, so the correct decision is ABSTAIN."""

# D26 (2026-10-01): the support prompts ask only whether the decision is supported by the cited evidence, and the
# validity prompt asks three questions of every cited clause without naming any planted clause, class or case
# dimension. The fault-class definitions are not in either prompt; ``taxonomy=True`` adds them (an ablation).
TASKS = {
    "support": "Is the generator's decision supported by the regulatory evidence it cites, read together with the "
               "application documents? List any cited clause that is a problem for the decision, with the reason.",
    "support-p1": "Check that the generator's decision follows from the evidence it cites and from the application "
                  "documents. Name every cited clause that does not back the decision, and say why.",
    "support-p2": "Audit the generator's answer: does the evidence it cites, read with the application documents, back "
                  "up its decision? Point out each cited clause that causes a problem, with a reason.",
    "validity": "For every clause the generator cited, check three things from the evidence and the application "
                "documents: (a) is the clause in force on the application date? (b) is it from the jurisdiction of "
                "this application (central rules govern every state)? (c) does it apply to this case? Then say "
                "whether the decision is supported by the cited clauses that pass all three. List every cited clause "
                "that fails (a), (b) or (c), or does not support the decision, with the reason.",
}
TASKS["validity-cc"] = TASKS["validity"]  # E2: same task; only its reason list differs (CC_REASONS)
VARIANTS = tuple(TASKS)


# D32 (2026-10-02): every finding carries a reason code from this closed set. The block is identical in every
# verifier prompt (all support variants, validity, reflect, independent, registry-LLM), names no clause and no
# planted fault, and is independent of the taxonomy ablation (class definitions).
REASONS: dict[str, str] = {
    "not_in_force": "the clause is superseded, or not yet in force, at the application date",
    "wrong_jurisdiction": "the clause is a rule of another state or authority",
    "not_applicable": "the clause does not govern this case's facts or category",
    "missing_rule": "an applicable rule was not considered",
    "content_or_arithmetic": "the decision does not follow from the clause's content (wrong numbers, thresholds or calculation)",
    "other": "any other problem",
}
# E2 (D37): the "can't confirm" reason list, REASONS plus one code before "other".
CC_REASONS: dict[str, str] = {
    **{k: v for k, v in REASONS.items() if k != "other"},
    "currency_unconfirmed": "the evidence shown does not establish whether the clause is in force at the application date",
    "other": REASONS["other"],
}


def reasons_for(variant: str) -> dict[str, str]:
    """The reason list a prompt variant shows and its replies are parsed against."""
    return CC_REASONS if variant.endswith("-cc") else REASONS


def reason_block(reasons: dict[str, str]) -> str:
    return "Reason codes (give exactly one per finding):\n" + "\n".join(f"- {k}: {v}." for k, v in reasons.items())


REASON_BLOCK = reason_block(REASONS)


def reason_code(raw: Any, reasons: dict[str, str] = REASONS) -> str:
    """A reply's reason, normalised to a code of ``reasons``; anything else (missing, free text) is ``other``."""
    code = re.sub(r"[\s-]+", "_", str(raw or "").strip().lower())
    return code if code in reasons else "other"


def output_spec(taxonomy: bool, reasons: dict[str, str] = REASONS) -> str:
    cls = ', "class": "<fault class id from the list above, e.g. F3>"' if taxonomy else ""
    return f"""{reason_block(reasons)}

Reply in strict JSON:
{{"verdict": "PASS" or "FLAG",
 "risk": <probability from 0 to 1 that the generator's decision is wrong>,
 "findings": [{{"clause_id": "<the cited clause or document id the problem concerns; for missing_rule, the missing clause id>", "reason": "<one reason code from the list above>", "rationale": "<one sentence>"{cls}}}]}}
Report a finding only for a specific problem you can tie to a specific clause or value. A PASS has no findings."""


def flag(f: dict[str, str]) -> str:
    """``<class>:<clause_id>:<reason>`` (D32); the reason field is empty when a finding has none (old runs)."""
    return f"{f['class']}:{f['clause_id']}:{f.get('reason', '')}"


def verifier_task(variant: str, taxonomy: bool) -> str:
    """Task statement, optional fault-class list (ablation) and output specification for one prompt variant."""
    if variant not in TASKS:
        raise ValueError(f"Unknown verifier prompt variant '{variant}'; one of {VARIANTS}")
    return "\n\n".join([TASKS[variant], *([FAULT_TAXONOMY] if taxonomy else []),
                        output_spec(taxonomy, reasons_for(variant))])


def _class_id(raw: Any, taxonomy: bool) -> str:
    m = re.search(r"F\s*([1-9])(?:\s*-\s*([RC]))?", str(raw).upper()) if taxonomy and raw else None
    if m is None:
        return "ANY"  # no class asked for, or none given: matched on the clause alone
    return f"F{m.group(1)}" + (f"-{m.group(2)}" if m.group(2) else "")


def parse_verdict(out: dict[str, Any], taxonomy: bool = False,
                  reasons: dict[str, str] = REASONS) -> tuple[str, float | None, list[dict[str, str]], list[str]]:
    """(verdict, risk, findings, flags). Flags are ``<class>:<clause_id>:<reason>`` strings (D32); the class is
    ``ANY`` unless the taxonomy was shown and the finding gives one. A reply without a PASS/FLAG verdict is an
    invalid output (D30), not a crash."""
    verdict = str(out.get("verdict", "")).strip().upper()
    if verdict not in {"PASS", "FLAG"}:
        raise InvalidModelOutput(f"Verifier reply has no PASS/FLAG verdict: {str(out)[:300]}")
    try:
        risk: float | None = min(1.0, max(0.0, float(out["risk"])))
    except (KeyError, TypeError, ValueError):
        risk = None
    findings: list[dict[str, str]] = []
    raw = out.get("findings")
    for f in raw if isinstance(raw, list) else []:
        if isinstance(f, dict):
            findings.append({"class": _class_id(f.get("class"), taxonomy), "clause_id": str(f.get("clause_id") or "").strip(),
                             "reason": reason_code(f.get("reason"), reasons), "rationale": str(f.get("rationale") or "")})
    flags = [flag(f) for f in findings]
    return verdict, risk, findings, flags


def relabel(text: str, labels: dict[str, str] | None) -> str:
    """Metadata off (D27): every document id in a verifier prompt becomes its opaque per-run source label."""
    if not labels:
        return text
    pat = re.compile(r"(?<![A-Za-z0-9])(?:" + "|".join(re.escape(d) for d in sorted(labels, key=len, reverse=True))
                     + r")(?![0-9])")
    return pat.sub(lambda m: labels[m.group(0)], text)


def unlabel(findings: list[dict[str, str]], labels: dict[str, str] | None) -> tuple[list[dict[str, str]], list[str]]:
    """Findings (and flags) with source labels mapped back to document ids, so scoring sees real ids."""
    back = {v: k for k, v in (labels or {}).items()}
    if back:
        pat = re.compile("|".join(re.escape(v) for v in back))
        findings = [{**f, "clause_id": pat.sub(lambda m: back[m.group(0)], f["clause_id"])} for f in findings]
    return findings, [flag(f) for f in findings]


def application_context(
    case: BenchmarkCase,
    generator_result: Arm1ExecutionResult | Arm2ExecutionResult,
) -> str:
    """Application documents and generator-bound values: what F6, F7 and F9 are checked against."""
    return f"""[APPLICATION DOCUMENTS]
Electricity bill:
{case.inputs.bill}

EPC proposal:
{case.inputs.proposal}

DISCOM portal status:
{case.inputs.portal_state}

[VALUES BOUND AND COMPUTED BY THE GENERATOR]
{generator_result.computed or "none recorded"}"""


def generator_block(generator_result: Arm1ExecutionResult | Arm2ExecutionResult) -> str:
    return f"""[GENERATOR OUTPUT TO VERIFY]
Decision: {generator_result.decision}
Blocking stage: {generator_result.blocking_stage}
Cited rules: {generator_result.cited_rules}
Subsidy: Rs {generator_result.subsidy_amount_inr}
Root cause: {generator_result.root_cause}"""


@dataclass
class VerifierResult:
    """Telemetry and verdicts returned by a verifier system."""

    case_id: str
    verifier_id: str
    independence_config: str
    verdict: str  # "PASS" or "FLAG"
    is_flagged: bool
    flagged_faults: list[str]  # "<class>:<clause_id>:<reason>" per finding (D32)
    audit_reason: str
    latency_sec: float
    prompt_tokens: int
    completion_tokens: int
    raw_output: dict[str, Any]
    is_correct: bool = True
    retrieved_chunks: list[str] = field(default_factory=list)
    retrieved_chunk_ids: list[str] = field(default_factory=list)
    # Everything the verifier consulted that the generator did not cite, for the Table 8 Jaccard.
    evidence_ids: list[str] = field(default_factory=list)
    risk: float | None = None
    findings: list[dict[str, str]] = field(default_factory=list)
    model: str | None = None
    prompt_sha256: str | None = None  # of the exact prompt(s) sent, after relabelling; None without an LLM call


def prompt_sha256(*prompts: str) -> str:
    return hashlib.sha256("\n\x00\n".join(prompts).encode("utf-8")).hexdigest()


def llm_verdict(
    case: BenchmarkCase,
    generator_result: Arm1ExecutionResult | Arm2ExecutionResult,
    evidence: str,
    verifier_id: str,
    config: str,
    model: str | None,
    variant: str,
    taxonomy: bool,
    extra: str = "",
    labels: dict[str, str] | None = None,
) -> VerifierResult:
    """One LLM verification call over the given evidence text (shared by Arms 3 and 4). ``labels`` (metadata
    off): document ids in the prompt are replaced by opaque source labels, and mapped back in the findings."""
    assert not getattr(case, "fault_events", None), (
        f"Isolation breach: case '{case.case_id}' fault_events must be empty/inaccessible in verification path"
    )
    t0 = time.time()
    prompt = f"""You are a regulatory compliance verifier for Indian rooftop-solar applications.

{generator_block(generator_result)}

{application_context(case, generator_result)}

[REGULATORY EVIDENCE]
{evidence}
{extra}
{verifier_task(variant, taxonomy)}
"""
    # No fallback: a failed call must fail the run (retained in results/failed/).
    sent = relabel(prompt, labels)
    out, p_tok, c_tok = call_llm_json(prompt=sent, model=model, temperature=0.0)
    verdict, risk, _findings, _ = parse_verdict(out, taxonomy, reasons_for(variant))
    findings, flags = unlabel(_findings, labels)
    return VerifierResult(
        case_id=case.case_id,
        verifier_id=verifier_id,
        independence_config=config,
        verdict=verdict,
        is_flagged=verdict == "FLAG" or bool(findings),
        flagged_faults=flags,
        audit_reason=" | ".join(f["rationale"] for f in findings) or str(out.get("reason", "")),
        latency_sec=round(time.time() - t0, 4),
        prompt_tokens=p_tok,
        completion_tokens=c_tok,
        raw_output=out,
        risk=risk,
        findings=findings,
        model=model,
        prompt_sha256=prompt_sha256(sent),
    )


def execute_verify_shared(
    case: BenchmarkCase,
    generator_result: Arm1ExecutionResult | Arm2ExecutionResult,
    model: str | None = None,
    variant: str = "support",
    taxonomy: bool = False,
    labels: dict[str, str] | None = None,
) -> VerifierResult:
    """Arm 3 (000): the generator's own evidence, nothing else."""
    res = llm_verdict(case, generator_result, "\n---\n".join(generator_result.retrieved_chunks), "Arm-3", "000",
                      model, variant, taxonomy, labels=labels)
    res.retrieved_chunks = generator_result.retrieved_chunks
    res.retrieved_chunk_ids = list(generator_result.retrieved_chunk_ids)
    res.evidence_ids = list(generator_result.retrieved_chunk_ids)
    return res
