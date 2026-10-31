"""End-to-end integration smoke test for SuryaBench (Deliverable D0).

Validates the full pipeline on the minimal fixture corpus:
1. Corpus manifest loading & SHA-256 integrity verification.
2. Supersession graph loading & cycle/integrity validation.
3. Currency oracle in_force() evaluation.
4. Applicability predicate evaluation.
5. Arm 0 deterministic decision tree execution.
6. Benchmark case validation.
7. Run manifest creation & schema verification.
"""

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from suryabench.applicability.schema import ApplicabilityPredicate
from suryabench.arms.arm0_rules import Arm0DecisionTree
from suryabench.cases.schema import BenchmarkCase
from suryabench.cases.validator import validate_case
from suryabench.core.enums import CurrencyVerdict, ExpectedDecision
from suryabench.corpus.manifest import compute_file_sha256, load_manifest, verify_manifest
from suryabench.eval.manifest import RunManifest, load_run_manifest, save_run_manifest
from suryabench.graph.oracle import in_force, validate_graph
from suryabench.graph.schema import SupersessionGraph

FIXTURES_DIR = Path(__file__).parents[1] / "fixtures"
CORPUS_DIR = FIXTURES_DIR / "corpus"
CASES_FILE = FIXTURES_DIR / "cases" / "fixture_cases.json"


def test_end_to_end_pipeline_smoke() -> None:
    """Execute complete end-to-end smoke test over minimal fixture corpus."""
    # 1. Corpus Manifest & File Integrity
    manifest_path = CORPUS_DIR / "MANIFEST.json"
    manifest = load_manifest(manifest_path)
    assert manifest.corpus_version == "SuryaBench-Corpus-2026.11-fixture"
    verify_manifest(manifest, CORPUS_DIR / "raw")

    # 2. Supersession Graph & Validation
    graph_path = CORPUS_DIR / "graph" / "supersession.json"
    with open(graph_path, encoding="utf-8") as f:
        graph_data = json.load(f)
    graph = SupersessionGraph.model_validate(graph_data)
    validate_graph(graph)

    # 3. Currency Oracle Check
    # At snapshot 2026-11-01, 2019 clause MH-C3-001#cl-7.2 is superseded by 2024 clause MH-C3-002#cl-3
    assert in_force("MH-C3-001#cl-7.2", "2026-11-01", graph) == CurrencyVerdict.SUPERSEDED
    assert in_force("MH-C3-002#cl-3", "2026-11-01", graph) == CurrencyVerdict.IN_FORCE

    # 4. Applicability Predicates
    pred_path = CORPUS_DIR / "graph" / "applicability.json"
    with open(pred_path, encoding="utf-8") as f:
        pred_data = json.load(f)
    predicates = [ApplicabilityPredicate.model_validate(p) for p in pred_data]
    assert len(predicates) == 3

    # 5. Benchmark Case
    with open(CASES_FILE, encoding="utf-8") as f:
        cases_data = json.load(f)
    cases = [BenchmarkCase.model_validate(c) for c in cases_data]
    assert len(cases) == 1
    case = cases[0]
    validate_case(case)

    # 6. Arm 0 executes on the fixture case's facsimiles
    arm0 = Arm0DecisionTree(graph=graph, predicates=predicates)
    output = arm0.evaluate_case(case)
    assert output.decision in {ExpectedDecision.ANSWER, ExpectedDecision.ABSTAIN}

    # 7. Run Manifest Creation & Schema Verification
    with tempfile.TemporaryDirectory() as tmpdir:
        run_manifest_path = Path(tmpdir) / "run_manifest.json"
        corpus_hash = compute_file_sha256(manifest_path)
        benchmark_hash = compute_file_sha256(CASES_FILE)

        manifest_record = RunManifest(
            run_id="smoke-run-001",
            corpus_hash=corpus_hash,
            benchmark_hash=benchmark_hash,
            model_id="deterministic-arm0",
            quantisation=None,
            seed=42,
            temperature=0.0,
            prompt_template_hashes={},
            tool_versions={"arm0": "1.0.0"},
            independence_config=None,
            arm_id="arm0",
            timestamp=datetime.now(UTC).isoformat(),
        )

        save_run_manifest(manifest_record, run_manifest_path)
        loaded = load_run_manifest(run_manifest_path)
        assert loaded.run_id == "smoke-run-001"
        assert loaded.corpus_hash == corpus_hash
        assert loaded.benchmark_hash == benchmark_hash
