"""Benchmark execution runner for SuryaBench (WS8 / D9).

Executes experimental arms (Arms 0–4, Arm 2-O) across benchmark splits,
enforcing determinism, TestSplitGuard, RunManifest generation, and
comprehensive deterministic evaluations with rule-node clustered bootstrap CIs.
"""

import dataclasses
import hashlib
import inspect
import json
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from suryabench.applicability.schema import ApplicabilityPredicate
from suryabench.arms.arm0_rules import Arm0DecisionTree
from suryabench.arms.arm1_rag import Arm1ExecutionResult, execute_arm1_rag
from suryabench.arms.arm2_agent import Arm2ExecutionResult, execute_arm2_agent
from suryabench.arms.arm2o_oracle import execute_arm2o_oracle
from suryabench.arms.arm5_recovery import execute_recovery
from suryabench.arms.completeness import check_rule_completeness
from suryabench.arms.controlled_exposure import (
    CONDITIONS,
    ExposurePlan,
    build_exposure,
    format_nodes,
    render_ids,
)
from suryabench.arms.llm_client import MODEL_INFO, set_run_seed
from suryabench.arms.tools.case_reader import parse_case_facsimiles
from suryabench.arms.verify_independent import (
    NOISE,
    REGISTRY_CONFIGS,
    Registry,
    execute_registry_check,
    execute_registry_llm,
    execute_verify_independent,
    load_registry,
    registry_variant,
)
from suryabench.arms.verify_reflect import execute_verify_reflect
from suryabench.arms.verify_shared import VARIANTS, VerifierResult, execute_verify_shared
from suryabench.cases.schema import BenchmarkCase
from suryabench.core.exceptions import InvalidModelOutput, SuryaBenchError
from suryabench.core.guard import TestSplitGuard
from suryabench.corpus.manifest import compute_file_sha256, load_manifest
from suryabench.eval.evaluators import (
    BenchmarkScorecard,
    compute_benchmark_scorecard,
)
from suryabench.eval.failure_classifier import (
    CaseClassificationResult,
    FailureClassifier,
)
from suryabench.eval.manifest import RunManifest, save_run_manifest
from suryabench.gate0.retriever import (
    RD4_HYBRID,
    RD4_PER_DOC_CAP,
    LocalRetriever,
    build_corpus_chunks,
    map_chunks_to_clauses,
)
from suryabench.graph.schema import SupersessionGraph
from suryabench.paths import REGISTRIES_DIR, RESULTS_DIR, corpus_name, display, embeddings_cache

PROMPT_MODULES = [
    sys.modules[f.__module__]
    for f in (
        execute_arm1_rag, execute_arm2_agent, execute_arm2o_oracle,
        execute_verify_shared, execute_verify_reflect, execute_verify_independent,
        execute_recovery, build_exposure, check_rule_completeness, set_run_seed,
    )
] + [sys.modules[FailureClassifier.__module__]]


def invalid_generation(case_id: str, error: str) -> Arm2ExecutionResult:
    """An unusable generator reply (D24): decision INVALID, which the classifier scores as incorrect."""
    return Arm2ExecutionResult(case_id=case_id, arm_id="Arm-2", decision="INVALID", is_approved=False, cited_rules=[],
                               root_cause=None, blocking_stage=None, subsidy_amount_inr=None, computed=[],
                               tool_outputs={}, retrieved_chunks=[], retrieved_chunk_ids=[], latency_sec=0.0,
                               prompt_tokens=0, completion_tokens=0, raw_output={"invalid_output": error[:500]})


def invalid_verification(case_id: str, arm_id: str, ind: str, error: str) -> VerifierResult:
    """An unusable verifier reply (D24): verdict INVALID, no flag, no findings."""
    return VerifierResult(case_id=case_id, verifier_id=arm_id, independence_config=ind, verdict="INVALID",
                          is_flagged=False, flagged_faults=[], audit_reason="invalid model output", latency_sec=0.0,
                          prompt_tokens=0, completion_tokens=0, raw_output={"invalid_output": error[:500]})


def code_hash() -> str:
    """SHA-256 over every prompt-bearing and scoring module: a run made with other code is stale."""
    h = hashlib.sha256()
    for mod in sorted(PROMPT_MODULES, key=lambda m: m.__name__):
        h.update(inspect.getsource(mod).encode("utf-8"))
    return h.hexdigest()


# Verifier arms -> configuration label (plan D9). 110/111 are retired (their registry planted the faults).
VERIFIER_ARMS: dict[str, str] = {
    "arm3": "000", "arm3_reflect": "000-reflect", "arm4_100": "100", "arm4_100n": "100-neutral",
    "reg_oracle": "reg-oracle", "reg_real": "reg-real", "reg_real_llm": "reg-real-llm",
    **{name.replace("-", "_"): name for name in NOISE},  # reg_noisy25_s0 .. reg_spurious10_s4 (D31)
}
REAL_REGISTRY = REGISTRIES_DIR / "registry_real_v1.json"
REAL_REGISTRY_R3 = REGISTRIES_DIR / "registry_real_v2_r3.json"


def default_real_registry(corpus: str | None) -> tuple[Path, str | None]:
    """(reg-real file, warning): r3 runs use registry_real_v2_r3.json once it exists; until then
    registry_real_v1.json, with a warning recorded in the run manifest (never a failure)."""
    if corpus == "r3" and not REAL_REGISTRY_R3.exists():
        return REAL_REGISTRY, (f"{display(REAL_REGISTRY_R3)} not found; reg-real falls back to "
                               f"{display(REAL_REGISTRY)} (extracted from corpus r2)")
    return (REAL_REGISTRY_R3 if corpus == "r3" else REAL_REGISTRY), None
LLM_VERIFIER_ARMS = {"arm3", "arm3_reflect", "arm4_100", "arm4_100n", "reg_real_llm"}


def _plan_record(plan: ExposurePlan | None) -> dict[str, Any] | None:
    """What a controlled-exposure condition showed and planted, kept with each case's record."""
    if plan is None:
        return None
    return {"condition": plan.condition, "node_ids": plan.node_ids,
            "planted": plan.fault_event.gold_evidence[0] if plan.fault_event else None,
            "implied_flip": plan.implied_flip}


class _Hidden:
    """Stands in for a gold field on the case an arm receives: any read fails the run (plan item 1.8)."""

    def __init__(self, name: str) -> None:
        object.__setattr__(self, "_name", name)

    def __getattr__(self, attr: str) -> Any:
        if attr.startswith("__"):
            raise AttributeError(attr)
        raise AssertionError(f"Isolation breach: an arm read gold field '{self._name}.{attr}'")

    def __iter__(self) -> Any:
        raise AssertionError(f"Isolation breach: an arm iterated gold field '{self._name}'")

    def __len__(self) -> int:
        raise AssertionError(f"Isolation breach: an arm read gold field '{self._name}'")


class BenchmarkRunConfig(BaseModel):
    """Configuration for an experimental evaluation run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str | None = None
    arm_id: str = Field(..., description="arm0, arm1, arm2, arm2o, arm3, arm3_reflect, arm4")
    model_id: str = Field(default="mock", description="Model identifier")
    temperature: float = Field(default=0.0, description="Sampling temperature")
    seed: int = Field(default=42, description="Random seed")
    verifier_model_id: str | None = Field(
        default=None, description="Verifier model; None = the generator's model (cross-model when different)"
    )
    prompt_variant: str = Field(default="support", description="Verifier prompt: support, support-p1, support-p2, validity")
    taxonomy: bool = Field(default=False, description="Ablation (D26): add the fault-class list to LLM verifier prompts")
    metadata: bool = Field(
        default=False, description="D27: the VERIFIER's evidence headers show issuer, jurisdiction, effective date and "
        "title (on), or opaque source labels and an undated title (off). The generator always sees metadata on"
    )
    registry_path: Path | None = Field(
        default=None, description="reg-real registry file; default by corpus (see default_real_registry)"
    )
    model_training_cutoff: str | None = Field(
        default=None, description="Model training cutoff date (e.g. '2023-12')"
    )
    cases_path: Path
    corpus_dir: Path
    output_dir: Path = Field(default=RESULTS_DIR / "runs")
    generator_cache: Path | None = Field(
        default=None,
        description="JSON cache of Arm 2 outputs by case_id, shared by arm2/arm3/arm3_reflect/arm4 runs "
        "of the same model and seed, so every verifier configuration checks the same generator output",
    )
    completeness: bool = Field(
        default=False,
        description="Apply the affirmative completeness checklist to F4 scoring (ablation on/off)",
    )
    exposure_condition: str | None = Field(
        default=None,
        description="Controlled-exposure condition (N, C, S-swap, S-both, J, A, O) for the Arm 2 generator; "
        "None is the original natural-retrieval run",
    )
    recovery: bool = Field(
        default=False, description="Arm 5: after a verifier FLAG, give the critique back to the generator"
    )
    allow_test_split: bool = Field(
        default=False, description="Whether test split access is explicitly authorized"
    )
    max_cases: int | None = Field(
        default=None, description="Optional cap on number of cases evaluated"
    )


class RunResult(BaseModel):
    """Execution output bundle."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    manifest: RunManifest
    scorecard: BenchmarkScorecard
    evaluations: list[CaseClassificationResult]
    raw_outputs: list[dict[str, Any]]


class BenchmarkRunner:
    """Benchmark runner executing arms and scoring deterministic metrics."""

    def __init__(self, config: BenchmarkRunConfig) -> None:
        self.config = config
        if config.exposure_condition is not None and config.exposure_condition not in CONDITIONS:
            raise ValueError(f"Unknown exposure condition '{config.exposure_condition}'")
        if config.prompt_variant not in VARIANTS:
            raise ValueError(f"Unknown prompt variant '{config.prompt_variant}'")
        self.exposure_skips: dict[str, str] = {}
        self.verifier_model = config.verifier_model_id or config.model_id

        # 1. Enforce TestSplitGuard before touching cases file
        TestSplitGuard.verify_access(
            config.cases_path,
            is_test_split=None if not config.allow_test_split else False,
        )

        # 2. Compute SHA-256 hashes for reproducibility
        manifest_file = config.corpus_dir / "MANIFEST.json"
        self.corpus = corpus_name(config.corpus_dir)  # r2 / r3; None for a test fixture
        self.real_registry, self.registry_warning = (
            (config.registry_path, None) if config.registry_path else default_real_registry(self.corpus))
        self.corpus_hash = compute_file_sha256(manifest_file)
        self.benchmark_hash = compute_file_sha256(config.cases_path)

        # 3. Load Corpus Manifest & Supersession Graph
        self.corpus_manifest = load_manifest(manifest_file)
        graph_file = config.corpus_dir / "graph" / "supersession.json"
        with open(graph_file, encoding="utf-8") as f:
            graph_data = json.load(f)
        self.graph = SupersessionGraph.model_validate(graph_data)

        # 4. Load Applicability Predicates if present
        pred_file = config.corpus_dir / "graph" / "applicability.json"
        self.predicates: list[ApplicabilityPredicate] = []
        if pred_file.exists():
            with open(pred_file, encoding="utf-8") as f:
                p_data = json.load(f)
            self.predicates = [ApplicabilityPredicate.model_validate(p) for p in p_data]

        # 5. Load Cases (under authorized context if requested)
        if config.allow_test_split:
            with TestSplitGuard.authorize():
                self.cases = self._load_cases(config.cases_path, config.max_cases)
        else:
            self.cases = self._load_cases(config.cases_path, config.max_cases)

        # Scientific assertions: ensure case grounding integrity per protocol
        for c in self.cases:
            if not c.applicable_rules:
                raise AssertionError(f"Case '{c.case_id}' missing mandatory applicable_rules.")
            if not c.inputs.bill or not c.inputs.proposal or not c.inputs.portal_state:
                raise AssertionError(f"Case '{c.case_id}' missing input surface facsimiles.")
            if c.facts.sanctioned_load_kw is None or c.facts.proposed_capacity_kw is None:
                raise AssertionError(f"Case '{c.case_id}' missing per-value input ground truth for F6 binding.")
            if not c.ground_truth_provenance or not c.ground_truth_provenance.basis:
                raise AssertionError(f"Case '{c.case_id}' missing ground_truth_provenance.")

        # 6. Initialize LocalRetriever for retrieval arms
        text_dir = config.corpus_dir / "text"
        chunks = build_corpus_chunks(text_dir) if text_dir.exists() else []
        self.retriever = LocalRetriever(chunks, hybrid=RD4_HYBRID, per_doc_cap=RD4_PER_DOC_CAP)  # RD4 stack
        # Dense BGE-M3 retrieval (protocol). LocalRetriever.retrieve() silently falls back
        # to lexical matching when unindexed, so an index failure must be fatal here.
        # One cache per real corpus beside the real results; a fixture corpus keeps its cache next to itself.
        self.retriever.index(cache_file=embeddings_cache(config.corpus_dir))
        if chunks and len(self.retriever.embeddings) != len(chunks):
            raise SuryaBenchError(
                f"Dense index incomplete: {len(self.retriever.embeddings)}/{len(chunks)} chunks embedded"
            )

        # 7. Initialize Failure Classifier (chunk -> clause map drives F4-R vs F4-C)
        self.classifier = FailureClassifier(
            graph=self.graph,
            manifest=self.corpus_manifest,
            chunk_clauses=map_chunks_to_clauses(chunks, self.graph.nodes.values(), text_dir),
        )
        self.retriever.chunk_clauses = self.classifier.chunk_clauses
        self.retriever.doc_titles = {d.doc_id: d.title for d in self.corpus_manifest.documents}
        self.retriever.meta = True  # D27: the generator always sees metadata; _verify switches to the verifier's view
        # Metadata off: document ids become opaque per-run source labels in every verifier prompt (D27).
        salt = f"{config.run_id or config.arm_id}|{config.seed}"
        self.labels: dict[str, str] | None = None if config.metadata else {
            d.doc_id: "SRC-" + hashlib.sha256(f"{salt}|{d.doc_id}".encode()).hexdigest()[:6].upper()
            for d in self.corpus_manifest.documents}
        assert self.labels is None or len(set(self.labels.values())) == len(self.labels), "source label collision"
        self.retriever.doc_meta = {
            d.doc_id: {"issuer": str(getattr(d, "issuer", "") or "unknown"),
                       "jurisdiction": str(getattr(d.jurisdiction.code, "value", d.jurisdiction.code)),
                       "effective_date": str(getattr(d, "effective_date", "") or "unknown")}
            for d in self.corpus_manifest.documents}
        self._chunks, self._text_dir = chunks, text_dir
        self._registries: dict[str, Registry] = {}

    def _registry(self, name: str) -> Registry:
        """The registry a reg-* configuration consults, built once per run."""
        if name not in self._registries:
            if name == "reg-oracle":
                reg = Registry(name, self.graph, self.classifier.chunk_clauses)
            elif name in NOISE:
                reg = Registry(name, registry_variant(self.graph, name), self.classifier.chunk_clauses)
            elif name == "reg-real":
                path = self.real_registry
                if not path.exists():
                    raise SuryaBenchError(f"reg-real needs the separately built registry {path} (WP6); it does not exist")
                real = load_registry(path, {d: m["effective_date"] for d, m in self.retriever.doc_meta.items()})
                reg = Registry(name, real, map_chunks_to_clauses(self._chunks, real.nodes.values(), self._text_dir))
            else:
                raise ValueError(f"Unknown registry '{name}'")
            self._registries[name] = reg
        return self._registries[name]

    def _generate(self, case: BenchmarkCase, plan: ExposurePlan | None = None) -> Arm2ExecutionResult:
        """Arm 2 output for a case, generated once per (model, seed, condition) when a cache is configured.

        With an injected plan (any condition but N) the generator sees the plan's nodes instead of
        its own retrieval; the cache file must then be specific to the condition.
        """
        evidence = None
        if plan is not None and plan.condition != "N":
            evidence = format_nodes(plan.node_ids, self.graph, self.retriever)

        def fresh() -> Arm2ExecutionResult:
            try:
                return execute_arm2_agent(case=case, retriever=self.retriever, model=self.config.model_id,
                                          evidence=evidence)
            except InvalidModelOutput as e:  # D24: scored as an invalid (wrong) answer, counted per model
                return invalid_generation(case.case_id, str(e))

        path = self.config.generator_cache
        if path is None:
            return fresh()
        if not hasattr(self, "_gen_cache"):
            self._gen_cache: dict[str, dict[str, Any]] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if case.case_id not in self._gen_cache:
            self._gen_cache[case.case_id] = dataclasses.asdict(fresh())
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self._gen_cache, default=str), encoding="utf-8", newline="\n")
        return Arm2ExecutionResult(**self._gen_cache[case.case_id])

    def _exposure(self, case: BenchmarkCase) -> tuple[BenchmarkCase, ExposurePlan | None] | None:
        """(case to score, plan), or None when the condition has no material for the case.

        The planted distractor is added to the scored case's fault events, so the classifier
        reports whether it was committed and whether the verifier caught it.
        """
        cond = self.config.exposure_condition
        if cond is None:
            return case, None
        plan, reason = build_exposure(case, cond, self.graph, self.predicates, self.classifier.chunk_clauses)
        if plan is None:
            self.exposure_skips[case.case_id] = reason
            return None
        if plan.fault_event is not None:
            case = case.model_copy(update={"fault_events": [*case.fault_events, plan.fault_event]})
        return case, plan

    def _completeness(
        self, case: BenchmarkCase, gen: Arm1ExecutionResult | Arm2ExecutionResult
    ) -> dict[str, Any]:
        """Affirmative completeness checklist (facts + registry only); scored iff config.completeness."""
        res = check_rule_completeness(
            case_id=case.case_id,
            parsed=parse_case_facsimiles(case.inputs),
            graph=self.graph,
            retrieved_chunk_ids=gen.retrieved_chunk_ids,
            cited_rules=gen.cited_rules,
            chunk_clauses=self.classifier.chunk_clauses,
        )
        return {"completeness_flags": res.flags, "completeness_applied": self.config.completeness}

    def _load_cases(self, cases_path: Path, max_cases: int | None) -> list[BenchmarkCase]:
        with open(cases_path, encoding="utf-8") as f:
            cases_data = json.load(f)
        cases = [BenchmarkCase.model_validate(c) for c in cases_data]
        if max_cases:
            cases = cases[:max_cases]
        return cases

    @staticmethod
    def _unlabelled(case: BenchmarkCase, oracle: bool = False) -> BenchmarkCase:
        """The case as the arms may see it: its id and application documents. Every gold field is removed or
        replaced by a tripwire that fails the run if read. Arm 2-O alone keeps ``applicable_rules`` (its oracle)."""
        update: dict[str, Any] = {"fault_events": [], "expected_answer": None, "failure_class_probed": None,
                                  "non_fault_opportunities": [], "facts": _Hidden("facts"),
                                  "ground_truth_provenance": _Hidden("ground_truth_provenance"),
                                  "expected_decision": _Hidden("expected_decision"),
                                  "abstention_reason": _Hidden("abstention_reason"),
                                  "cluster_id": _Hidden("cluster_id")}
        if not oracle:
            update["applicable_rules"] = _Hidden("applicable_rules")
        return case.model_copy(update=update)

    def _verify(self, arm_id: str, ind: str, case: BenchmarkCase, gen: Arm2ExecutionResult) -> VerifierResult:
        if ind in REGISTRY_CONFIGS:  # deterministic: no prompt, no metadata factor
            return execute_registry_check(case, gen, self.retriever, self._registry(ind))
        m, v, t, lab = self.verifier_model, self.config.prompt_variant, self.config.taxonomy, self.labels
        # D27: the verifier sees the generator's evidence re-rendered at the verifier's metadata level
        # (the generator output itself is shared by both levels).
        self.retriever.meta = self.config.metadata
        try:
            view = dataclasses.replace(gen, retrieved_chunks=render_ids(gen.retrieved_chunk_ids, self.graph, self.retriever))
            if arm_id == "arm3":
                return execute_verify_shared(case=case, generator_result=view, model=m, variant=v, taxonomy=t, labels=lab)
            if arm_id == "arm3_reflect":
                return execute_verify_reflect(case=case, generator_result=view, model=m, variant=v, taxonomy=t, labels=lab)
            if ind == "reg-real-llm":
                return execute_registry_llm(case, view, self.retriever, self._registry("reg-real"), m, v, t, lab)
            return execute_verify_independent(case=case, generator_result=view, retriever=self.retriever,
                                              independence_config=ind, model=m, variant=v, taxonomy=t, labels=lab)
        finally:
            self.retriever.meta = True

    def _recover(self, scored: BenchmarkCase, unlabelled: BenchmarkCase, gen: Arm2ExecutionResult,
                 ver: VerifierResult, initial_correct: bool) -> dict[str, Any]:
        """Arm 5: revise after a FLAG; the final answer is the revision if flagged, else the initial one."""
        initial_outcome = self.classifier.classify_case(scored, gen).outcome_correct
        if not ver.is_flagged:
            return {"flagged": False, "initial_correct": initial_correct, "final_correct": initial_correct,
                    "initial_outcome_correct": initial_outcome, "final_outcome_correct": initial_outcome}
        try:
            revised = execute_recovery(unlabelled, gen, ver, self.retriever, self.config.model_id)
        except InvalidModelOutput as e:  # D24: an invalid revision is a wrong final answer
            return {"flagged": True, "initial_correct": initial_correct, "final_correct": False,
                    "initial_outcome_correct": initial_outcome, "final_outcome_correct": False,
                    "revised_invalid": str(e)[:500]}
        rc = self.classifier.classify_case(scored, revised, retrieved_chunk_ids=revised.retrieved_chunk_ids)
        return {"flagged": True, "initial_correct": initial_correct, "final_correct": rc.is_correct,
                "initial_outcome_correct": initial_outcome, "final_outcome_correct": rc.outcome_correct,
                "revised": dataclasses.asdict(revised), "revised_classification": rc.model_dump(mode="json")}

    def run(self) -> RunResult:
        """Execute the benchmark run over all cases."""
        timestamp = datetime.now(UTC).isoformat()
        run_id = (
            self.config.run_id
            or f"{self.config.arm_id}-{self.config.model_id}-{self.config.seed}-{int(datetime.now(UTC).timestamp())}"
        )

        arm_id = self.config.arm_id.lower()
        set_run_seed(self.config.seed)
        evaluations: list[CaseClassificationResult] = []
        raw_outputs: list[dict[str, Any]] = []
        scored_cases: list[BenchmarkCase] = []  # the cases actually run, with any planted fault event

        try:
            # Instantiate Arm
            if arm_id == "arm0":
                arm0 = Arm0DecisionTree(graph=self.graph, predicates=self.predicates)
                for case in self.cases:
                    out = arm0.evaluate_case(case)
                    classification = self.classifier.classify_case(case, out)
                    evaluations.append(classification)
                    scored_cases.append(case)
                    raw_outputs.append({"case_id": case.case_id, "output": out.model_dump()})

            elif arm_id == "arm1":
                for case in self.cases:
                    res1 = execute_arm1_rag(
                        case=self._unlabelled(case),
                        retriever=self.retriever,
                        model=self.config.model_id,
                    )
                    classification = self.classifier.classify_case(
                        case,
                        res1,
                        retrieved_chunk_ids=res1.retrieved_chunk_ids,
                        **self._completeness(case, res1),
                    )
                    evaluations.append(classification)
                    scored_cases.append(case)
                    raw_outputs.append(
                        {"case_id": case.case_id, "output": dataclasses.asdict(res1)}
                    )

            elif arm_id == "arm2":
                for case in self.cases:
                    exposed = self._exposure(case)
                    if exposed is None:
                        continue
                    scored, plan = exposed
                    res2 = self._generate(self._unlabelled(case), plan)
                    classification = self.classifier.classify_case(
                        scored,
                        res2,
                        retrieved_chunk_ids=res2.retrieved_chunk_ids,
                        **self._completeness(case, res2),
                    )
                    evaluations.append(classification)
                    scored_cases.append(scored)
                    raw_outputs.append(
                        {"case_id": case.case_id, "output": dataclasses.asdict(res2), "exposure": _plan_record(plan)}
                    )

            elif arm_id in {"arm2o", "arm2_oracle"}:
                for case in self.cases:
                    res2o = execute_arm2o_oracle(
                        case=self._unlabelled(case, oracle=True),
                        graph=self.graph,
                        retriever=self.retriever,
                        model=self.config.model_id,
                    )
                    classification = self.classifier.classify_case(
                        case, res2o, retrieved_chunk_ids=res2o.retrieved_chunk_ids
                    )
                    evaluations.append(classification)
                    scored_cases.append(case)
                    raw_outputs.append(
                        {"case_id": case.case_id, "output": dataclasses.asdict(res2o)}
                    )

            elif arm_id in VERIFIER_ARMS:
                # Arm 3 (000), Arm 3-Reflect (compute control), Arm 4 (100, 100-neutral) and the
                # registries. Every configuration checks the same cached Arm 2 output, so verifier
                # comparisons are paired by case.
                ind = VERIFIER_ARMS[arm_id]
                for case in self.cases:
                    exposed = self._exposure(case)
                    if exposed is None:
                        continue
                    scored, plan = exposed
                    unlabelled_case = self._unlabelled(case)
                    res_gen = self._generate(unlabelled_case, plan)
                    try:
                        res_ver = self._verify(arm_id, ind, unlabelled_case, res_gen)
                    except InvalidModelOutput as e:  # D24: an invalid verifier reply flags nothing, counted
                        res_ver = invalid_verification(case.case_id, arm_id, ind, str(e))
                    classification = self.classifier.classify_case(
                        scored,
                        res_gen,
                        verifier_flags=res_ver.flagged_faults,
                        retrieved_chunk_ids=res_gen.retrieved_chunk_ids,
                        verifier_chunk_ids=res_ver.evidence_ids,
                        **self._completeness(case, res_gen),
                        independence_config=ind,
                    )
                    record: dict[str, Any] = {
                        "case_id": case.case_id,
                        "generator": dataclasses.asdict(res_gen),
                        "verifier": dataclasses.asdict(res_ver),
                        "exposure": _plan_record(plan),
                    }
                    if self.config.recovery:
                        record["recovery"] = self._recover(scored, unlabelled_case, res_gen, res_ver,
                                                           classification.is_correct)
                    evaluations.append(classification)
                    scored_cases.append(scored)
                    raw_outputs.append(record)
            else:
                raise ValueError(f"Unknown arm_id: '{arm_id}'")

        except Exception as exc:
            # Retain failed run with full traceback per protocol
            failed_dir = self.config.output_dir.parent / "failed" / run_id
            failed_dir.mkdir(parents=True, exist_ok=True)
            with open(failed_dir / "error.json", "w", encoding="utf-8", newline="\n") as f:
                json.dump(
                    {
                        "run_id": run_id,
                        "arm_id": self.config.arm_id,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                        "traceback": traceback.format_exc(),
                        "timestamp": timestamp,
                    },
                    f,
                    indent=2,
                )
            raise

        # Compute Scorecard with clause-clustered bootstrap CIs
        scorecard = compute_benchmark_scorecard(
            arm_id=self.config.arm_id,
            cases=scored_cases,
            classifications=evaluations,
        )

        # Build RunManifest
        # SHA-256 of each prompt-bearing module's source (templates + shared taxonomy text)
        prompt_hashes: dict[str, str] = {
            mod.__name__.rsplit(".", 1)[-1]: hashlib.sha256(inspect.getsource(mod).encode()).hexdigest()
            for mod in PROMPT_MODULES
        }
        if arm_id == "arm3_reflect":
            prompt_hashes["arm_role"] = "compute_matched_shared_evidence_control"
        verifies = arm_id in VERIFIER_ARMS
        llm_verifies = arm_id in LLM_VERIFIER_ARMS
        reg = VERIFIER_ARMS.get(arm_id, "")
        reg_path = self.real_registry if reg in {"reg-real", "reg-real-llm"} else None

        manifest_record = RunManifest(
            run_id=run_id,
            corpus_hash=self.corpus_hash,
            benchmark_hash=self.benchmark_hash,
            model_id=self.config.model_id,
            quantisation=None,
            seed=self.config.seed,
            temperature=self.config.temperature,
            prompt_template_hashes=prompt_hashes,
            tool_versions={
                "suryabench.eval": "1.0.0",
                "corpus": self.corpus or display(self.config.corpus_dir),
                "corpus_version": self.corpus_manifest.corpus_version,
                "corpus_manifest_sha256": self.corpus_hash,
                "retriever": self.retriever.describe(),
                "completeness": "on" if self.config.completeness else "off",
                "exposure_condition": self.config.exposure_condition or "none (natural, pre-redesign)",
                "recovery": "on" if self.config.recovery else "off",
                "code_hash": code_hash(),
                "generator_model": self.config.model_id,
                "generator_provider_version": json.dumps(MODEL_INFO.get(self.config.model_id, {})),
                "verifier_model": self.verifier_model if llm_verifies else "none (deterministic)" if verifies else "n/a",
                "verifier_provider_version": json.dumps(MODEL_INFO.get(self.verifier_model, {})) if llm_verifies else "n/a",
                "prompt_variant": self.config.prompt_variant if llm_verifies else "n/a",
                "taxonomy": ("on" if self.config.taxonomy else "off") if llm_verifies else "n/a",
                "metadata_header": ("on" if self.config.metadata else "off (opaque source labels)") if llm_verifies else "n/a",
                "generator_metadata_header": "on",
                "registry": (f"{reg_path} sha256={compute_file_sha256(reg_path)}" if reg_path and reg_path.exists()
                             else reg or "n/a"),
                **({"registry_warning": self.registry_warning} if reg_path and self.registry_warning else {}),
            },
            independence_config=None,
            model_training_cutoff=self.config.model_training_cutoff,
            arm_id=self.config.arm_id,
            timestamp=timestamp,
        )

        # Save artifacts to results/runs/<run_id>/
        run_dir = self.config.output_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        save_run_manifest(manifest_record, run_dir / "run_manifest.json")
        if self.config.exposure_condition is not None:
            with open(run_dir / "exposure_skips.json", "w", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps({"condition": self.config.exposure_condition, "run": len(evaluations),
                                    "skipped": self.exposure_skips}, indent=2) + "\n")

        with open(run_dir / "scorecard.json", "w", encoding="utf-8", newline="\n") as f:
            f.write(scorecard.model_dump_json(indent=2) + "\n")

        # Each record: the classification plus the arm's complete raw output (decision,
        # citations, computed, tool traces, retrieved chunk ids, latency, token counts).
        records = []
        for ev, raw in zip(evaluations, raw_outputs, strict=True):
            assert ev.case_id == raw["case_id"]
            records.append({**ev.model_dump(mode="json"), "raw": raw})
        with open(run_dir / "evaluations.json", "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(records, indent=2, default=str) + "\n")

        return RunResult(
            run_id=run_id,
            manifest=manifest_record,
            scorecard=scorecard,
            evaluations=evaluations,
            raw_outputs=raw_outputs,
        )
