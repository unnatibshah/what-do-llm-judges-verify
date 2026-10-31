"""D49: bring a remote run's results (``kaggle_results.tgz``) into ``50_analysis/results/probe_test_v3`` after checks.

Refuses the whole archive, copying nothing, if any block fails a check:
- the block ran the sealed test file (``allow_test`` and ``dataset_sha256`` equal to ``test_cases_v3.sha256``);
- a local model's ``model_digest`` equals PREREGISTRATION_v3 section 4;
- the block's ``code_hash`` equals the one this checkout gives (same probe code as the other machine);
- the model has no blocks here from another machine (each model runs on one machine).

Then it copies each model folder, the remote reply cache (as ``llm_cache_<tag>``, kept apart from this machine's) and
the machine record. The test replies are not read beyond the block headers.

    PYTHONPATH=30_code/src:30_code/scripts python 30_code/scripts/kaggle/import_remote_run.py kaggle_results.tgz --tag kaggle
"""

import argparse
import hashlib
import inspect
import json
import re
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from suryabench.arms import verifier_probe as vp
from suryabench.paths import BENCHMARK_DIR, METHOD_DIR, RESULTS_DIR

DEST = RESULTS_DIR / "probe_test_v3"
INNER = Path("50_analysis/results/probe_test_v3")


def prereg_digests() -> dict[str, str]:
    text = (METHOD_DIR / "PREREGISTRATION_v3.md").read_text(encoding="utf-8")
    return {m: d for m, d in re.findall(r"\| `([^`]+)` \| Ollama[^|]*\| `sha256:([0-9a-f]{64})` \|", text)}


def local_code_hash() -> str:
    from run_verifier_probe import (
        code_hash,  # the same expression run_verifier_probe.py writes into each block
    )
    return hashlib.sha256((code_hash() + inspect.getsource(vp)).encode()).hexdigest()[:12]


def check(src: Path, sealed: str, digests: dict[str, str], chash: str, dest: Path) -> tuple[list[str], list[Path]]:
    problems: list[str] = []
    models = [d for d in sorted(src.iterdir()) if (d / "blocks").is_dir()]
    for d in models:
        if (dest / d.name / "blocks").exists() and any((dest / d.name / "blocks").iterdir()):
            problems.append(f"{d.name}: this machine already has blocks for the model")
        for f in sorted((d / "blocks").glob("*.json")):
            h: dict[str, Any] = {k: v for k, v in json.loads(f.read_text(encoding="utf-8")).items() if k != "rows"}
            where = f"{d.name}/{f.name}"
            if not h.get("allow_test") or h.get("dataset_sha256") != sealed:
                problems.append(f"{where}: not the sealed test file")
            if h.get("model") in digests and (h.get("model_digest") or "").removeprefix("sha256:") != digests[h["model"]]:
                problems.append(f"{where}: model digest {h.get('model_digest')} is not the preregistered one")
            if h.get("code_hash") != chash:
                problems.append(f"{where}: code hash {h.get('code_hash')}, this checkout {chash}")
    if not models:
        problems.append("no model folders with blocks in the archive")
    return problems, models


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("archive")
    ap.add_argument("--tag", default="kaggle")
    a = ap.parse_args()
    sealed = (BENCHMARK_DIR / "test_cases_v3.sha256").read_text(encoding="utf-8").split()[0]
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(a.archive) as t:
            t.extractall(tmp, filter="data")
        src = Path(tmp) / INNER
        if src.is_dir():
            problems, models = check(src, sealed, prereg_digests(), local_code_hash(), DEST)
            if problems:
                raise SystemExit("refused, nothing copied:\n" + "\n".join(problems))
            for d in models:
                shutil.copytree(d, DEST / d.name, dirs_exist_ok=True)
                print(f"imported {d.name}: {len(list((d / 'blocks').glob('*.json')))} blocks")
            if (src / "llm_cache").is_dir():
                shutil.copytree(src / "llm_cache", DEST / f"llm_cache_{a.tag}", dirs_exist_ok=True)
            for f in src.glob("MACHINE_*.txt"):
                shutil.copy2(f, DEST / f.name)
        # D49 exploratory folders (determinism repeat; models added after filing): same checks, own destination
        for name in ("probe_test_v3_repeat", "probe_test_v3_exploratory"):
            extra = Path(tmp) / "50_analysis/results" / name
            if not extra.is_dir():
                continue
            bad, extra_models = check(extra, sealed, prereg_digests(), local_code_hash(), RESULTS_DIR / name)
            if bad:
                raise SystemExit(f"{name} refused:\n" + "\n".join(bad))
            shutil.copytree(extra, RESULTS_DIR / name, dirs_exist_ok=True)
            print(f"imported {name}: {', '.join(d.name for d in extra_models)}")
    print(f"done; record the machine in the paper from {DEST.relative_to(RESULTS_DIR.parent.parent)}/MACHINE_{a.tag}.txt")


if __name__ == "__main__":
    main()
