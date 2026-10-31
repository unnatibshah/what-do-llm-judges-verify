"""Integration test suite for SuryaBench Benchmark Runner (WS8 / D9).

Validates:
1. End-to-end execution of Arm 0 over dev cases.
2. End-to-end execution of Arm 1 RAG generator over dev cases.
3. End-to-end execution of Arm 2-O Oracle over dev cases.
4. End-to-end execution of Arm 4 Independent Verifier.
5. Deterministic artifact emission: run_manifest.json, scorecard.json, evaluations.json.
6. Strict TestSplitGuard enforcement preventing unauthorized test split access.
7. Authorized test split execution when allow_test_split=True.
"""

import json
import tempfile
from pathlib import Path

import pytest

from suryabench.core.exceptions import TestSplitAccessViolation
from suryabench.eval.runner import BenchmarkRunConfig, BenchmarkRunner
from suryabench.paths import BENCHMARK_DIR, CORPUS_DIR

DEV_CASES_PATH = BENCHMARK_DIR / "dev_cases_60.json"
TEST_CASES_PATH = BENCHMARK_DIR / "test_cases_100.json"


def test_eval_runner_arm0_dev_cases() -> None:
    """Validate Arm 0 deterministic decision tree execution via BenchmarkRunner."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "results"
        config = BenchmarkRunConfig(
            arm_id="arm0",
            model_id="deterministic",
            cases_path=DEV_CASES_PATH,
            corpus_dir=CORPUS_DIR,
            output_dir=output_dir,
            max_cases=5,
        )

        runner = BenchmarkRunner(config)
        result = runner.run()

        assert result.scorecard.total_cases == 5
        assert result.scorecard.accuracy >= 0.0
        assert len(result.evaluations) == 5

        # Verify saved artifacts on disk
        run_dir = output_dir / result.run_id
        assert (run_dir / "run_manifest.json").exists()
        assert (run_dir / "scorecard.json").exists()
        assert (run_dir / "evaluations.json").exists()

        # Check manifest contents
        with open(run_dir / "run_manifest.json", encoding="utf-8") as f:
            manifest_data = json.load(f)
        assert manifest_data["arm_id"] == "arm0"
        assert manifest_data["corpus_hash"] == runner.corpus_hash
        assert manifest_data["benchmark_hash"] == runner.benchmark_hash


def test_eval_runner_arm1_rag_dev_cases() -> None:
    """Validate Arm 1 RAG execution via BenchmarkRunner."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "results"
        config = BenchmarkRunConfig(
            arm_id="arm1",
            model_id="mock",
            cases_path=DEV_CASES_PATH,
            corpus_dir=CORPUS_DIR,
            output_dir=output_dir,
            max_cases=2,
        )

        runner = BenchmarkRunner(config)
        result = runner.run()

        assert result.scorecard.total_cases == 2
        assert len(result.evaluations) == 2
        assert (output_dir / result.run_id / "scorecard.json").exists()

        # Dense BGE-M3 index is live: no silent lexical fallback
        assert len(runner.retriever.embeddings) == len(runner.retriever.chunks) > 0
        assert result.manifest.tool_versions["retriever"] == "dense:bge-m3:latest+bm25-rrf60"  # RD4 stack

        # Raw arm output persisted per case alongside its classification
        with open(output_dir / result.run_id / "evaluations.json", encoding="utf-8") as f:
            records = json.load(f)
        raw = records[0]["raw"]["output"]
        assert len(raw["retrieved_chunk_ids"]) == 5
        assert {"latency_sec", "prompt_tokens", "completion_tokens", "computed"} <= raw.keys()


def test_eval_runner_arm2o_oracle_dev_cases() -> None:
    """Validate Arm 2-O Oracle execution via BenchmarkRunner."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "results"
        config = BenchmarkRunConfig(
            arm_id="arm2o",
            model_id="mock",
            cases_path=DEV_CASES_PATH,
            corpus_dir=CORPUS_DIR,
            output_dir=output_dir,
            max_cases=2,
        )

        runner = BenchmarkRunner(config)
        result = runner.run()

        assert result.scorecard.total_cases == 2
        assert len(result.evaluations) == 2


def test_eval_runner_arm4_verifier_dev_cases() -> None:
    """Validate Arm 4 Independent Verifier execution via BenchmarkRunner."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "results"
        config = BenchmarkRunConfig(
            arm_id="reg_oracle",
            model_id="mock",
            cases_path=DEV_CASES_PATH,
            corpus_dir=CORPUS_DIR,
            output_dir=output_dir,
            max_cases=2,
        )

        runner = BenchmarkRunner(config)
        result = runner.run()

        assert result.scorecard.total_cases == 2
        assert result.manifest.tool_versions["verifier_model"] == "none (deterministic)"


@pytest.mark.parametrize("arm_id", ["arm3", "arm3_reflect"])
def test_shared_evidence_jaccard_is_exactly_one(arm_id: str) -> None:
    """Manipulation-check anchor: J(000) must be exactly 1.0 on every case.

    If the shared verifier ever receives a truncated, re-ranked or re-retrieved
    evidence set, J(000) drops below 1.0 and the independence ladder breaks on
    plumbing rather than on a finding.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config = BenchmarkRunConfig(
            arm_id=arm_id,
            model_id="mock",
            cases_path=DEV_CASES_PATH,
            corpus_dir=CORPUS_DIR,
            output_dir=Path(tmpdir) / "results",
            max_cases=10,
        )
        result = BenchmarkRunner(config).run()

        overlaps = [e.evidence_overlap_jaccard for e in result.evaluations]
        defined = [j for j in overlaps if j is not None]  # both-empty overlap is undefined
        assert len(defined) >= 5
        assert all(j == 1.0 for j in defined), overlaps
        label = {"arm3": "000", "arm3_reflect": "000-reflect"}[arm_id]
        assert result.scorecard.evidence_overlap_by_config == {label: 1.0}
        assert result.scorecard.evidence_overlap_n_by_config == {label: len(defined)}


def test_independence_ladder_overlap_falls() -> None:
    """Manipulation check on dev: J(000)=1 > J(100) >= J(registry) (the registries consult no generator evidence)."""
    means = {}
    for arm in ["arm3", "arm4_100", "reg_oracle"]:
        with tempfile.TemporaryDirectory() as tmpdir:
            config = BenchmarkRunConfig(
                arm_id=arm,
                model_id="mock",
                cases_path=DEV_CASES_PATH,
                corpus_dir=CORPUS_DIR,
                output_dir=Path(tmpdir) / "results",
                max_cases=10,
            )
            means[arm] = BenchmarkRunner(config).run().scorecard.mean_evidence_overlap_jaccard
    assert means["arm3"] == 1.0
    # Preregistered ordering J(000)=1 > J(100) > J(110) >= J(111); once J(100) reaches 0 the
    # later steps can only tie.
    assert means["arm3"] > means["arm4_100"], means
    assert means["arm4_100"] >= (means["reg_oracle"] or 0.0), means


def test_test_split_guard_blocks_unauthorized_access() -> None:
    """Assert that passing test_cases_100.json without authorization raises TestSplitAccessViolation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "results"
        config = BenchmarkRunConfig(
            arm_id="arm0",
            model_id="deterministic",
            cases_path=TEST_CASES_PATH,
            corpus_dir=CORPUS_DIR,
            output_dir=output_dir,
            allow_test_split=False,  # Unauthorized!
            max_cases=2,
        )

        with pytest.raises(TestSplitAccessViolation):
            BenchmarkRunner(config)


def test_test_split_authorized_execution() -> None:
    """Assert that passing test_cases_100.json with allow_test_split=True is permitted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "results"
        config = BenchmarkRunConfig(
            arm_id="arm0",
            model_id="deterministic",
            cases_path=TEST_CASES_PATH,
            corpus_dir=CORPUS_DIR,
            output_dir=output_dir,
            allow_test_split=True,  # Explicitly authorized!
            max_cases=2,
        )

        runner = BenchmarkRunner(config)
        assert len(runner.cases) == 2
        res = runner.run()
        assert res.scorecard.total_cases == 2


def test_eval_runner_noisy_registry() -> None:
    """Validate a noisy registry run (oracle graph with 25% of edges dropped), with clustered intervals."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "results"
        config = BenchmarkRunConfig(
            arm_id="reg_noisy25_s0",
            model_id="mock",
            cases_path=DEV_CASES_PATH,
            corpus_dir=CORPUS_DIR,
            output_dir=output_dir,
            model_training_cutoff="2023-12",
            max_cases=3,
        )

        runner = BenchmarkRunner(config)
        result = runner.run()

        assert result.scorecard.total_cases == 3
        assert result.manifest.tool_versions["registry"] == "reg-noisy25-s0"
        assert result.manifest.model_training_cutoff == "2023-12"
        # Evidence overlap Jaccard should be calculated
        assert result.scorecard.mean_evidence_overlap_jaccard is not None
        assert 0.0 <= result.scorecard.mean_evidence_overlap_jaccard <= 1.0

        # Verify cluster_clause_id presence and clustered bootstrap intervals
        assert result.scorecard.accuracy_ci is not None
        assert result.scorecard.accuracy_ci.n_clusters >= 1
        assert result.scorecard.accuracy_ci.total_opportunities == 3


def test_eval_runner_arm3_reflect_shared_evidence_control() -> None:
    """Validate Arm 3-Reflect labeled as compute-matched shared-evidence control."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "results"
        config = BenchmarkRunConfig(
            arm_id="arm3_reflect",
            model_id="mock",
            cases_path=DEV_CASES_PATH,
            corpus_dir=CORPUS_DIR,
            output_dir=output_dir,
            max_cases=2,
        )

        runner = BenchmarkRunner(config)
        result = runner.run()

        assert result.scorecard.total_cases == 2
        assert (
            result.manifest.prompt_template_hashes.get("arm_role")
            == "compute_matched_shared_evidence_control"
        )


def test_eval_runner_failed_run_retention() -> None:
    """Assert that failed runs are retained in results/failed/<run_id>/error.json with traceback."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "results" / "runs"
        # Configure an unknown arm to deliberately trigger an exception during run
        config = BenchmarkRunConfig(
            arm_id="arm_invalid_crash",
            model_id="mock",
            cases_path=DEV_CASES_PATH,
            corpus_dir=CORPUS_DIR,
            output_dir=output_dir,
            max_cases=1,
        )

        runner = BenchmarkRunner(config)
        with pytest.raises(ValueError, match="Unknown arm_id"):
            runner.run()

        failed_dir = output_dir.parent / "failed"
        assert failed_dir.exists()
        run_dirs = list(failed_dir.iterdir())
        assert len(run_dirs) == 1
        error_file = run_dirs[0] / "error.json"
        assert error_file.exists()

        with open(error_file, encoding="utf-8") as f:
            err_data = json.load(f)
        assert err_data["arm_id"] == "arm_invalid_crash"
        assert err_data["error_type"] == "ValueError"
        assert "Unknown arm_id" in err_data["error_message"]
        assert "traceback" in err_data



def test_generator_cache_pairs_verifier_arms() -> None:
    """With a generator cache, arm3 and reg_oracle verify the identical Arm 2 output per case."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = Path(tmpdir) / "gen.json"
        outs = {}
        for arm in ["arm3", "reg_oracle"]:
            config = BenchmarkRunConfig(arm_id=arm, model_id="mock", cases_path=DEV_CASES_PATH,
                                        corpus_dir=CORPUS_DIR, output_dir=Path(tmpdir) / "r",
                                        max_cases=3, generator_cache=cache)
            outs[arm] = BenchmarkRunner(config).run().raw_outputs
        assert cache.exists() and len(json.loads(cache.read_text(encoding="utf-8"))) == 3
        for a, b in zip(outs["arm3"], outs["reg_oracle"], strict=True):
            assert a["generator"] == b["generator"]


def test_eval_runner_on_corpus_r3_records_corpus_and_registry(tmp_path: Path) -> None:
    """A v2 run on corpus r3: the r3 graph, index and registry are used and the manifest records them."""
    from suryabench.corpus.manifest import compute_file_sha256
    from suryabench.eval.runner import default_real_registry
    from suryabench.paths import CORPUS_R3_DIR

    config = BenchmarkRunConfig(arm_id="reg_real", model_id="mock", cases_path=BENCHMARK_DIR / "dev_cases_v2.json",
                                corpus_dir=CORPUS_R3_DIR, output_dir=tmp_path, exposure_condition="C", max_cases=2)
    runner = BenchmarkRunner(config)
    assert len(runner.graph.nodes) > 140 and len(runner.retriever.embeddings) == len(runner.retriever.chunks)
    tv = runner.run().manifest.tool_versions
    reg_path, warning = default_real_registry("r3")
    assert tv["corpus"] == "r3" and tv["corpus_version"] == "SuryaBench-Corpus-2026.10-r3"
    assert tv["corpus_manifest_sha256"] == compute_file_sha256(CORPUS_R3_DIR / "MANIFEST.json")
    assert tv["registry"].endswith(f"sha256={compute_file_sha256(reg_path)}")
    assert tv.get("registry_warning") == warning
