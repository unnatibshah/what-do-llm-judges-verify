"""Run manifest schema and determinism validator."""

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from suryabench.core.enums import IndependenceConfig

# Arm output contract. Bump on any change to what arms emit or what the classifier reads.
# 1.0.0 (implicit, no field): halted qwen2.5:7b pilot. Retrieved evidence passed as raw chunk text.
# 2.0.0: retrieved_chunk_ids carry chunk_id (clause ids for Arm 2-O); strict clause-level F4-R/F4-C;
#        verifier prompts request F1-F9 and see application documents + generator `computed`;
#        Arm 1 emits `computed` with field-level input provenance.
ARM_OUTPUT_SCHEMA_VERSION = "2.0.0"


class RunManifest(BaseModel):
    """Execution run manifest enforcing reproducibility per EXECUTION-PLAN §B."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(..., description="Unique run identifier")
    corpus_hash: str = Field(..., description="SHA-256 hash of the frozen corpus manifest")
    benchmark_hash: str = Field(..., description="SHA-256 hash of the benchmark cases file")
    model_id: str = Field(
        ..., description="Model identifier (e.g. 'deterministic-arm0', 'qwen2.5-7b')"
    )
    quantisation: str | None = Field(
        None, description="Model quantisation if applicable (e.g. 'q4_k_m')"
    )
    seed: int = Field(default=42, description="Random seed used for generation/inference")
    temperature: float = Field(default=0.0, description="Sampling temperature")
    prompt_template_hashes: dict[str, str] = Field(
        default_factory=dict, description="SHA-256 hashes of all prompt templates used"
    )
    tool_versions: dict[str, str] = Field(
        default_factory=dict, description="Versions or hashes of deterministic tools used"
    )
    independence_config: IndependenceConfig | None = Field(
        None, description="Verifier independence level: 000, 100, 111, or 110"
    )
    arm_id: str = Field(..., description="Identifier of the experimental arm (e.g. 'arm0', 'arm1')")
    model_training_cutoff: str | None = Field(
        default=None, description="Knowledge cutoff date of the evaluated model (e.g. '2023-12')"
    )
    timestamp: str = Field(..., description="ISO 8601 execution timestamp")
    arm_output_schema_version: str = Field(
        default=ARM_OUTPUT_SCHEMA_VERSION,
        description="Arm output contract version; runs with different versions are not comparable",
    )


def save_run_manifest(manifest: RunManifest, output_path: Path) -> None:
    """Save run manifest to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(manifest.model_dump_json(indent=2) + "\n")


def load_run_manifest(manifest_path: Path) -> RunManifest:
    """Load and validate run manifest from JSON file."""
    with open(manifest_path, encoding="utf-8") as f:
        data = json.load(f)
    return RunManifest.model_validate(data)
