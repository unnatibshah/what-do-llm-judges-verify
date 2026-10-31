"""Determinism checks.

1. Arm 2: agreement between two runs that differ only in seed (temperature 0).
   python 30_code/scripts/determinism_check.py 50_analysis/results/runs 50_analysis/results/runs_determinism [--model qwen2.5:7b]
   Writes 50_analysis/results/paper/determinism.json.
2. Verifier probe (T3): ``determinism_check.py probe``. On a copy of the dev reply cache (the saved results are never
   written to), it (a) runs the probe, kills it once the first block is saved and resumes it; (b) runs it again from
   scratch, a pure cache replay; then checks that every block holds exactly the expected items (no duplicate, none
   missing), that the resumed and the replayed run score every row identically, and that both equal the saved dev
   blocks on the same items. (c) It checks that no reply cache anywhere under 50_analysis/results holds an invalid
   reply (they must never be cached). Writes 50_analysis/results/determinism_probe/determinism_probe.json.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from suryabench.arms.llm_client import parse_json_reply
from suryabench.core.exceptions import InvalidModelOutput
from suryabench.paths import CODE_DIR, RESULTS_DIR, ROOT, resolve

PROBE_MODEL = "qwen2.5:7b"
PROBE_CONFIGS = ["validity", "validity-metaoff", "reg-real"]
PROBE_CONDITIONS = ["S-both", "C"]
PROBE_MAX_ITEMS = 8
SCORE_KEYS = ("invalid", "any", "clause", "right", "wrong", "validity_reason", "verdict", "flags")


def arm2_records(out_dir: Path, model: str) -> tuple[int, dict[str, dict[str, Any]]]:
    rows = [r for r in json.loads((out_dir / "matrix_index.json").read_text(encoding="utf-8")) if r["arm"] == "arm2" and r["model"] == model]
    assert len(rows) == 1, f"expected one arm2 run for {model} in {out_dir}, found {len(rows)}"
    recs = json.loads((out_dir / rows[0]["run_id"] / "evaluations.json").read_text(encoding="utf-8"))
    return rows[0]["seed"], {r["case_id"]: r for r in recs}


def agreement(a: dict[str, dict[str, Any]], b: dict[str, dict[str, Any]]) -> dict[str, Any]:
    common = sorted(set(a) & set(b))

    def out(r: dict[str, Any]) -> dict[str, Any]:
        o = dict(r["raw"].get("generator") or r["raw"]["output"])
        for k in ("latency_sec", "prompt_tokens", "completion_tokens"):  # timing is not output
            o.pop(k, None)
        return o

    def same(f: Any) -> int:
        return sum(f(a[c]) == f(b[c]) for c in common)

    return {"n": len(common),
            "identical_output": same(out),
            "same_decision": same(lambda r: out(r).get("decision")),
            "same_correctness": same(lambda r: r["is_correct"]),
            "same_citations": same(lambda r: sorted(out(r).get("cited_rules") or [])),
            "accuracy": [sum(a[c]["is_correct"] for c in common), sum(b[c]["is_correct"] for c in common)]}


def _run_probe(out: Path, cache: Path, kill_after_first_block: bool = False) -> None:
    cmd = [sys.executable, str(CODE_DIR / "scripts" / "run_verifier_probe.py"), "--model", PROBE_MODEL, "--configs",
           *PROBE_CONFIGS, "--conditions", *PROBE_CONDITIONS, "--max-items", str(PROBE_MAX_ITEMS), "--out", str(out)]
    env = {**os.environ, "SURYABENCH_LLM_CACHE": str(cache),
           "PYTHONPATH": os.pathsep.join([str(CODE_DIR / "src"), str(CODE_DIR / "scripts")])}
    proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if kill_after_first_block:
        blocks = out / PROBE_MODEL.replace(":", "_") / "blocks"
        while proc.poll() is None and not (blocks.exists() and any(blocks.glob("*.json"))):
            time.sleep(0.2)
        proc.kill()
        proc.wait()
        return
    _, err = proc.communicate()
    if proc.returncode:
        raise RuntimeError(f"probe run failed: {err.decode()[-2000:]}")


def _blocks(out: Path) -> dict[str, list[dict[str, Any]]]:
    return {f.stem: json.loads(f.read_text(encoding="utf-8"))["rows"]
            for f in sorted((out / PROBE_MODEL.replace(":", "_") / "blocks").glob("*.json"))}


def invalid_cached(root: Path) -> dict[str, int]:
    """Cache entries under ``root`` whose reply is not a valid JSON object (must be 0), and the number checked."""
    bad = n = 0
    for f in root.rglob("llm_cache/*/*.json"):
        n += 1
        try:
            parse_json_reply(json.loads(f.read_text(encoding="utf-8"))["raw"])
        except (InvalidModelOutput, KeyError, ValueError):
            bad += 1
    return {"cache_entries": n, "invalid_cached": bad}


def probe_check() -> dict[str, Any]:
    saved = RESULTS_DIR / "probe_v2"
    with tempfile.TemporaryDirectory() as tmp:
        cache = Path(tmp) / "cache"
        shutil.copytree(saved / "llm_cache", cache)
        resumed, replay = Path(tmp) / "resumed", Path(tmp) / "replay"
        _run_probe(resumed, cache, kill_after_first_block=True)
        after_kill = sorted(_blocks(resumed))
        _run_probe(resumed, cache)
        _run_probe(replay, cache)
        a, b = _blocks(resumed), _blocks(replay)
        expected = json.loads((replay / "items.json").read_text(encoding="utf-8"))["items"]
    want = {k: [i["item_id"] for i in expected if i["condition"] == k.split("__")[1]][:PROBE_MAX_ITEMS] for k in b}
    complete = {k: [r["item_id"] for r in rows] == want[k] for k, rows in a.items()}
    same = {k: [[r[x] for x in SCORE_KEYS] for r in a[k]] == [[r[x] for x in SCORE_KEYS] for r in b[k]] for k in b}
    vs_saved: dict[str, Any] = {}
    for k, rows in b.items():
        f = saved / PROBE_MODEL.replace(":", "_") / "blocks" / f"{k}.json"
        old = {r["item_id"]: r for r in json.loads(f.read_text(encoding="utf-8"))["rows"]}
        shared = [r for r in rows if r["item_id"] in old]
        vs_saved[k] = {"shared": len(shared),
                       "identical": sum(all(r[x] == old[r["item_id"]][x] for x in SCORE_KEYS) for r in shared)}
    res = {"model": PROBE_MODEL, "configs": PROBE_CONFIGS, "conditions": PROBE_CONDITIONS, "max_items": PROBE_MAX_ITEMS,
           "blocks_saved_before_kill": after_kill, "blocks": sorted(b), "resumed_blocks_complete_no_duplicates": complete,
           "resumed_equals_replay": same, "replay_vs_saved_dev_blocks": vs_saved, **invalid_cached(RESULTS_DIR)}
    res["passed"] = (bool(after_kill) and len(after_kill) < len(b) and set(a) == set(b) and all(complete.values())
                     and all(same.values()) and all(v["shared"] == v["identical"] for v in vs_saved.values())
                     and res["invalid_cached"] == 0)
    out = RESULTS_DIR / "determinism_probe" / "determinism_probe.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8", newline="\n")
    return res


def main() -> None:
    if sys.argv[1:2] == ["probe"]:
        res = probe_check()
        print(json.dumps({k: res[k] for k in ("passed", "blocks_saved_before_kill", "cache_entries", "invalid_cached")}))
        sys.exit(0 if res["passed"] else 1)
    ap = argparse.ArgumentParser()
    ap.add_argument("primary", type=resolve)
    ap.add_argument("repeat", type=resolve)
    ap.add_argument("--model", default="qwen2.5:7b")
    ap.add_argument("--out", type=resolve, default=RESULTS_DIR / "paper" / "determinism.json")
    args = ap.parse_args()
    s1, a = arm2_records(args.primary, args.model)
    s2, b = arm2_records(args.repeat, args.model)
    res = {"model": args.model, "seeds": [s1, s2], **agreement(a, b)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(res)


if __name__ == "__main__":
    main()
