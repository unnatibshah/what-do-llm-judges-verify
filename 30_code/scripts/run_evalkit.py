"""D51: run one reviewer over the evalkit RFC items, one block per context (cached replies; resumable).

    PYTHONPATH=30_code/src:30_code/scripts python 30_code/scripts/run_evalkit.py --model gemini-3.5-flash-lite \\
        [--contexts cite-only both-texts ...] [--links 48] [--out 50_analysis/results/evalkit_rfc]

A model alias ``kbench-<slug>`` routes through the Kaggle-hosted transport (KBENCH_MODEL names the real model), as in
``kaggle/run_kbench_probe.py``. Damaged contexts use half the links dropped with --damage-seed (default 0).
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from suryabench import evalkit as ek
from suryabench.arms import llm_client
from suryabench.core.exceptions import InvalidModelOutput, SuryaBenchError
from suryabench.paths import RESULTS_DIR, resolve


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", required=True)
    ap.add_argument("--contexts", nargs="+", default=list(ek.CONTEXTS))
    ap.add_argument("--links", type=int, default=48)
    ap.add_argument("--decoys", action="store_true", help="add one update-not-replace decoy per link (rfc_decoys)")
    ap.add_argument("--damage-seed", type=int, default=0, help="which half of the links the damaged record drops")
    ap.add_argument("--out", default=str(RESULTS_DIR / "evalkit_rfc"))
    a = ap.parse_args()
    if a.model.startswith("kbench-"):
        sys.path.insert(0, str(Path(__file__).resolve().parent / "kaggle"))
        from run_kbench_probe import _kbench_call
        llm_client._call_local_ollama = _kbench_call  # type: ignore[assignment]
    out = Path(resolve(a.out))
    os.environ.setdefault("SURYABENCH_LLM_CACHE", str(out / "llm_cache"))
    docs, links, shots = ek.rfc_links(n=a.links)
    record = {(lk.old, lk.new) for lk in links}
    record_damaged = ek.damaged(record, 0.5, a.damage_seed)
    shot_items = ek.items(shots, docs)
    examples = [(ek.render(shot_items[0], "both-texts", docs, {(lk.old, lk.new) for lk in shots}),
                 json.dumps({"verdict": "FLAG", "findings": [{"doc_id": shot_items[0].cited, "reason": "superseded",
                             "rationale": f"replaced by {shots[0].new} before the date asked about"}]})),
                (ek.render(shot_items[4], "both-texts", docs, {(lk.old, lk.new) for lk in shots}),
                 json.dumps({"verdict": "PASS", "findings": []}))]
    test = ek.items(links, docs) + (ek.decoy_items(ek.rfc_decoys(links, docs), docs) if a.decoys else [])
    mdir = out / a.model.replace(":", "_").replace("/", "_")
    (mdir).mkdir(parents=True, exist_ok=True)
    for context in a.contexts:
        f = mdir / f"{context}.json"
        if f.exists():
            print(f"skip {context}: done")
            continue
        rec = record_damaged if context.endswith("damaged") else record
        rows, t0 = [], time.time()
        for it in test:
            prompt = ek.render(it, context, docs, rec, examples)
            try:
                reply, p_tok, c_tok = llm_client.call_llm_json(prompt, system_prompt=ek.SYSTEM, model=a.model, temperature=0.0)
            except InvalidModelOutput:
                reply, p_tok, c_tok = None, 0, 0
            except SuryaBenchError as e:  # a server that rejects one request: that reply is invalid (scored against
                if "Connection refused" in str(e) or "Remote end closed" in str(e):  # the model); a dead server stops the run
                    raise
                print("server error, scored invalid:", it.item_id, str(e)[-80:], flush=True)
                reply, p_tok, c_tok = None, 0, 0
            s = ek.score(it, reply, ek.masked_ids(it) if context == "both-masked" else None)
            rows.append({**ek.asdict(it), **s, "reply": reply, "prompt_tokens": p_tok, "completion_tokens": c_tok,
                         "dropped": context.endswith("damaged") and (it.link.split(">")[0], it.link.split(">")[1]) not in rec})
        f.write_text(json.dumps({"model": a.model, "context": context, "code_hash": ek.code_hash(), "links": a.links,
                                 "decoys": a.decoys, "damage_seed": a.damage_seed,
                                 "model_info": llm_client.MODEL_INFO.get(a.model, {}), "seconds": round(time.time() - t0, 1),
                                 "rows": rows}, indent=1) + "\n", encoding="utf-8", newline="\n")
        v = ek.summarise(rows)
        print(f"{context}: catch {v['fault']['right']['k']}/{v['fault']['right']['n']}  FA {v['control']['any']['k']}  "
              f"date-FA {v['date-control']['validity']['k']}  invalid {sum(r['invalid'] for r in rows)}  {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
