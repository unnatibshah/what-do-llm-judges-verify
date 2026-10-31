"""D49, exploratory: run_verifier_probe.py with replies from a Kaggle-hosted model (``kaggle_benchmarks``, AI quota).

Only the transport changes. The fingerprinted modules (``eval/runner.PROMPT_MODULES``, which include ``llm_client``) are
not edited: this wrapper replaces ``llm_client._call_local_ollama`` in memory, so prompts, JSON parsing, caching and
scoring are byte-identical to every other model's, and blocks carry the same code hash. The model name passed to the
probe is an alias without ``/`` (``kbench-<slug>``) so the client's routing sends it here; ``KBENCH_MODEL`` names the
real Kaggle model, recorded as ``model_version`` in every block. Temperature and seed are whatever the Kaggle proxy
applies; the paper reports that. Kaggle notebook only.

    KBENCH_MODEL=<name from the probe cell> python 30_code/scripts/kaggle/run_kbench_probe.py --model kbench-<slug> ...
"""

import os
import runpy
import sys
from pathlib import Path

from suryabench.arms import llm_client


def _kbench_call(prompt: str, system_prompt: str, model: str | None, temperature: float, timeout: float
                 ) -> tuple[str, int, int]:
    import kaggle_benchmarks as kbench  # available in Kaggle notebooks only

    real = os.environ["KBENCH_MODEL"]
    llms = getattr(kbench, "llms", None)
    llm = llms[real] if llms is not None else kbench.llm
    cap = int(os.environ.get("KBENCH_MAX_OUT", "4000"))  # the proxy reserves credit for the longest possible reply
    r = llm._call_api([{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
                      max_completion_tokens=cap)  # prompt() takes no generation options; _call_api passes them on
    meta = getattr(r, "meta", {}) or {}
    llm_client.MODEL_INFO[model or real] = {"provider": "kaggle-benchmarks", "model_version": real}
    return str(r.content), int(meta.get("input_tokens", 0)), int(meta.get("output_tokens", 0))


def main() -> None:
    model = sys.argv[sys.argv.index("--model") + 1]
    if not model.startswith("kbench-") or "/" in model:
        raise SystemExit("--model must be an alias kbench-<slug> without '/'")
    llm_client._call_local_ollama = _kbench_call  # type: ignore[assignment]
    sys.argv = ["run_verifier_probe.py", *sys.argv[1:]]
    runpy.run_path(str(Path(__file__).resolve().parents[1] / "run_verifier_probe.py"), run_name="__main__")


if __name__ == "__main__":
    main()
