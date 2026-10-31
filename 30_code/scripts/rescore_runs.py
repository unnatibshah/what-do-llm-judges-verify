"""Re-classify saved runs from their raw outputs with the current classifier (no model calls).

Every run's evaluations.json keeps the arm's complete raw output per case. This script rebuilds
the generator and verifier outputs from those records, re-runs the deterministic classifier
and completeness checklist, and writes evaluations.json and scorecard.json to ``<run>/rescored/``.

Saved results are immutable (CLAUDE.md): ``--in-place`` overwrites a run's own files and is only for runs
made with the current code. The 2026-10-01 scoring (decision-level commitment, evidence-level matching,
stage-aware completeness) changes the numbers of runs made before it; the results of record are rebuilt
byte-identically by this script at commit f6a2d60, not by the current one.

Usage: python 30_code/scripts/rescore_runs.py [--in-place] 50_analysis/results/runs [...]
"""

import json
import sys
from types import SimpleNamespace
from typing import Any

from suryabench.arms.completeness import check_rule_completeness
from suryabench.arms.tools.case_reader import parse_case_facsimiles
from suryabench.cases.schema import BenchmarkCase
from suryabench.corpus.manifest import load_manifest
from suryabench.eval.evaluators import compute_benchmark_scorecard
from suryabench.eval.failure_classifier import FailureClassifier
from suryabench.gate0.retriever import build_corpus_chunks, map_chunks_to_clauses
from suryabench.graph.schema import SupersessionGraph
from suryabench.paths import CORPUS_DIR, resolve


def main() -> None:
    graph = SupersessionGraph.model_validate(json.loads((CORPUS_DIR / "graph" / "supersession.json").read_text(encoding="utf-8")))
    chunks = build_corpus_chunks(CORPUS_DIR / "text")
    chunk_clauses = map_chunks_to_clauses(chunks, graph.nodes.values(), CORPUS_DIR / "text")
    clf = FailureClassifier(graph=graph, manifest=load_manifest(CORPUS_DIR / "MANIFEST.json"),
                            chunk_clauses=chunk_clauses)
    in_place = "--in-place" in sys.argv[1:]
    for out_dir in map(resolve, [a for a in sys.argv[1:] if a != "--in-place"]):
        for row in json.loads((out_dir / "matrix_index.json").read_text(encoding="utf-8")):
            run_dir = out_dir / row["run_id"]
            cases = {c["case_id"]: BenchmarkCase.model_validate(c) for c in json.loads(resolve(row["cases"]).read_text(encoding="utf-8"))}
            records = json.loads((run_dir / "evaluations.json").read_text(encoding="utf-8"))
            new_records, evals = [], []
            for rec in records:
                case = cases[rec["case_id"]]
                raw: dict[str, Any] = rec["raw"]
                gen = raw.get("generator") or raw["output"]
                ver = raw.get("verifier")
                comp = check_rule_completeness(
                    case_id=case.case_id, parsed=parse_case_facsimiles(case.inputs), graph=graph,
                    retrieved_chunk_ids=gen.get("retrieved_chunk_ids") or [],
                    cited_rules=gen.get("cited_rules") or [], chunk_clauses=chunk_clauses,
                ) if "retrieved_chunk_ids" in gen else None
                ev = clf.classify_case(
                    case, SimpleNamespace(**gen),
                    verifier_flags=ver["flagged_faults"] if ver else None,
                    retrieved_chunk_ids=gen.get("retrieved_chunk_ids"),
                    verifier_chunk_ids=ver.get("evidence_ids") if ver else None,
                    independence_config=rec.get("independence_config"),
                    completeness_flags=comp.flags if comp else None,
                    completeness_applied=rec.get("completeness_applied", False),
                )
                evals.append(ev)
                new_records.append({**ev.model_dump(mode="json"), "raw": raw})
            dest = run_dir if in_place else run_dir / "rescored"
            dest.mkdir(exist_ok=True)
            (dest / "evaluations.json").write_text(json.dumps(new_records, indent=2, default=str) + "\n", encoding="utf-8", newline="\n")
            sc = compute_benchmark_scorecard(arm_id=row["arm"], cases=[cases[r["case_id"]] for r in records],
                                             classifications=evals)
            (dest / "scorecard.json").write_text(sc.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")
            print(f"rescored {row['run_id']}: acc {sc.correct_cases}/{sc.total_cases}")


if __name__ == "__main__":
    main()
