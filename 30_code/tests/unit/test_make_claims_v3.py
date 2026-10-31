"""make_claims_v3.py: each PREREGISTRATION_v3 stop rule fires on a synthetic ladder.json built to trigger it (T10)."""

import importlib.util
from typing import Any

from suryabench import paths

_spec = importlib.util.spec_from_file_location("make_claims_v3", paths.CODE_DIR / "scripts" / "make_claims_v3.py")
assert _spec and _spec.loader
mc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mc)

CAP = ("qwen2.5:14b", "gemma-4-26b-a4b-it")


def ladder(catches: dict[str, dict[str, float]], clauses: int = 15, lift_reject: bool = True,
           base_reject: bool = False, cc_uses: int = 1) -> dict[str, Any]:
    models: dict[str, Any] = {}
    for m, rungs in catches.items():
        models[m] = {r: {"catch": {"mean": v, "units": clauses}} for r, v in rungs.items()}
        for r in ("R0-cc", "R1-cc", "R2-cc"):
            models[m][r] = {"cant_confirm_fault": {"k": cc_uses}, "cant_confirm_correct": {"k": 0}}
    con = {}
    for m in catches:
        if m in CAP:
            con[f"R4-R2 @ {m}"] = {"clauses": clauses, "mean_diff": catches[m]["R4"] - catches[m]["R2"],
                                   "signflip_p": 0.01 if lift_reject else 0.4}
            con[f"R2-R0 @ {m}"] = {"clauses": clauses, "signflip_p": 0.01 if base_reject else 0.6}
    return {"models": models, "contrasts": con}


GOOD = {m: {"R0": 0.1, "R2": 0.2, "R4": 0.8} for m in CAP} | {"llama3.1:8b": {"R2": 0.1, "R4": 0.5}}


def rules(lad: dict[str, Any], **kw: Any) -> dict[str, str]:
    return {r["rule"].split(":")[0]: r["wording"] for r in mc.apply_rules(lad, **kw)}


def test_sentences_come_from_the_prereg() -> None:
    s = mc.sentences()
    assert set(s) == {1, 2, 3, 4, 5, 6} and s[6] == "The option was available and unused."


def test_full_support_fires_no_stop_rule() -> None:
    r = rules(ladder(GOOD))
    assert r["6"].startswith("Supported for qwen2.5:14b, gemma-4-26b-a4b-it")
    assert not {"7.1", "7.2", "7.3", "7.4", "7.5", "7.6"} & set(r)


def test_rule_1_too_few_clauses() -> None:
    r = rules(ladder(GOOD, clauses=8))
    assert r["7.1"].startswith("With 8 distinct clauses") and r["6"].startswith("Not supported")


def test_rule_2_r2_at_least_r4() -> None:
    lad = ladder({m: {"R0": 0.5, "R2": 0.7, "R4": 0.6} for m in CAP}, lift_reject=False)
    assert "7.2" in rules(lad) and "7.3" in rules(lad)


def test_rule_3_no_lift_after_holm() -> None:
    r = rules(ladder(GOOD, lift_reject=False))
    assert "7.3" in r and r["6"].startswith("Not supported")


def test_rule_4_weak_model_ignores_status() -> None:
    assert "7.4" in rules(ladder(GOOD | {"llama3.1:8b": {"R2": 0.30, "R4": 0.35}}))


def test_rule_5_stronger_model_closes_gap() -> None:
    r = rules(ladder(GOOD | {"gemini-3.5-flash-lite": {"R2": 0.75, "R4": 0.8}}))
    assert "abstract" in r["7.5"]


def test_rule_6_cant_confirm_unused() -> None:
    assert "7.6" in rules(ladder(GOOD, cc_uses=0))


def test_rule_7_scorer_gate() -> None:
    assert "7.7" in rules(ladder(GOOD), scorer_agreement=0.9)


def test_rule_8_api_fallback_uses_qwen_alone() -> None:
    r = rules(ladder({k: v for k, v in GOOD.items() if k != "gemma-4-26b-a4b-it"}))
    assert "7.8 / section 4 API fallback (gemma-4-26b-a4b-it not in ladder)" in r and r["6"] == "Supported for qwen2.5:14b."


def test_baseline_significant_blocks_the_claim() -> None:
    assert rules(ladder(GOOD, base_reject=True))["6"].startswith("Not supported")


def test_amendment_sentences() -> None:
    s = mc.amendment_sentences()
    assert set(s) == {1, 2, 3, 4, 5} and len(s[4]) >= 2 and s[4][1] == "We found no evidence of deference"


def _d47(net: dict[str, tuple[float, bool]], defer: tuple[float, bool] | None, catch_any: float = 0.2) -> dict[str, Any]:
    lad = ladder(GOOD)
    for m in CAP:
        for state, (diff, reject) in net.items():
            lad["contrasts"][f"Net-{state} @ {m}"] = {"clauses": 15, "mean_diff": diff, "p_holm": 0.01 if reject else 0.5,
                                                      "holm_reject": reject}
        if defer:
            lad["contrasts"][f"Defer @ {m}"] = {"clauses": 12, "mean_diff": defer[0], "holm_reject": defer[1]}
        lad["models"][m]["R2"]["catch_any"] = {"mean": catch_any}
    return lad


def test_a1_and_a3_reviewer_worse_than_registry() -> None:
    r = rules(_d47({"intact": (-0.3, True), "drop50": (0.0, False), "spurious10": (-0.1, False)}, (0.4, True)))
    assert r["A4.1"].startswith("For this model") and r["A4.3"].startswith("Adding the reviewer")
    assert r["A4.4"].startswith("A wrong 'in force' line") and "A4.2" not in r


def test_a2_value_only_under_damage_and_no_deference() -> None:
    r = rules(_d47({"intact": (0.0, False), "drop50": (0.3, True), "spurious10": (0.0, False)}, (0.1, False)))
    assert r["A4.2"].endswith("from drop50.") and "A4.1" not in r
    assert r["A4.4"] == "We found no evidence of deference"


def test_a5_flag_scoring_gap() -> None:
    r = rules(_d47({"intact": (0.0, False), "drop50": (0.0, False), "spurious10": (0.0, False)}, None, catch_any=0.6))
    assert "with 40 points of catches" in r["A4.5"]


def test_d47_readings_silent_below_min_clauses() -> None:
    lad = _d47({"intact": (-0.3, True), "drop50": (0.0, False), "spurious10": (0.0, False)}, None)
    for rungs in lad["models"].values():
        for cell in rungs.values():
            if "catch" in cell:
                cell["catch"]["units"] = 8
    for c in lad["contrasts"].values():
        c["clauses"] = 8
    assert not {"A4.1", "A4.3"} & set(rules(lad))
