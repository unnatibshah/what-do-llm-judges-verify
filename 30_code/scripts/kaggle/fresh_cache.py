"""Copy the v2 reply cache to the v3 run without the replies first obtained in the pilot (lead author, 2026-10-31).

    PYTHONPATH=30_code/src python 30_code/scripts/kaggle/fresh_cache.py

A pilot reply is one whose cache key is in the pilot's cache (same prompt, older proxy call for the hosted judges).
Leaving those out makes the v3 run re-ask exactly them under the current call; every other prompt hits the cache and
returns the v2 reply unchanged. The v2 cache and results are not touched.
"""

import shutil

from suryabench.paths import RESULTS_DIR

PILOT = {"kbench_claude_opus_4_5": "llm_cache_kaggle_task", "kbench_gemini_3_1_pro": "llm_cache_kaggle_task",
         "kbench_gpt_5_5": "llm_cache_kaggle_task", "gemma_4_26b_a4b_it": "llm_cache"}
src, dst = RESULTS_DIR / "evalkit_rfc_v2" / "llm_cache", RESULTS_DIR / "evalkit_rfc_v3" / "llm_cache"
for slug, pilot_dir in PILOT.items():
    pilot = {p.name for p in (RESULTS_DIR / "evalkit_rfc" / pilot_dir / slug).glob("*.json")}
    (dst / slug).mkdir(parents=True, exist_ok=True)
    kept = 0
    for p in (src / slug).glob("*.json"):
        if p.name not in pilot:
            shutil.copy2(p, dst / slug / p.name)
            kept += 1
    print(f"{slug}: kept {kept}, left out {len(pilot)} pilot replies")
