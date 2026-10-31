"""T3: the ladder analysis reproduces the dev pilot (00_tracking/status/PROBE-REPORT.md) for every rung the pilot
ran (R0, R1, R2, R5), from the saved blocks alone. No model is run."""

from typing import Any

import pytest

from suryabench.analysis import ladder
from suryabench.paths import RESULTS_DIR

PROBE_V2 = RESULTS_DIR / "probe_v2"
Q7, Q14, GEMMA, LLAMA = "qwen2.5:7b", "qwen2.5:14b", "gemma-4-26b-a4b-it", "llama3.1:8b"
# PROBE-REPORT tables: right S-both = R2 (validity), right S-swap = R1 (validity) and R0 (validity-metaoff),
# reg-real S-both + S-swap = R5; FPR C of validity = R1-R2 and of validity-metaoff = R0.
REPORT = {
    (Q7, "R2"): (7, 20), (Q7, "R1"): (0, 20), (Q7, "R0"): (0, 20), (Q7, "R5"): (40, 40),
    (GEMMA, "R2"): (8, 20), (GEMMA, "R1"): (0, 20), (GEMMA, "R0"): (0, 20), (GEMMA, "R5"): (40, 40),
    (LLAMA, "R2"): (0, 20), (LLAMA, "R1"): (0, 20), (LLAMA, "R0"): (0, 20),
    (Q14, "R2"): (8, 20), (Q14, "R1"): (0, 20), (Q14, "R0"): (0, 20),
}
REPORT_C = {(Q7, "R1"): (12, 54), (Q7, "R0"): (12, 54), (Q7, "R5"): (2, 54), (GEMMA, "R1"): (25, 54),
            (GEMMA, "R0"): (29, 54), (LLAMA, "R1"): (24, 54), (LLAMA, "R0"): (24, 54), (Q14, "R1"): (14, 54),
            (Q14, "R0"): (18, 54)}


@pytest.fixture(scope="module")
def res() -> dict[str, Any]:
    if not PROBE_V2.exists():
        pytest.skip("dev probe results not present")
    return ladder.analyse(ladder.load_rows([PROBE_V2]))


def test_reproduces_probe_report(res: dict[str, Any]) -> None:
    for (model, rung), (k, n) in REPORT.items():
        c = res["models"][model][rung]["catch"]
        assert (c["k"], c["n"]) == (k, n), (model, rung)
    for (model, rung), (k, n) in REPORT_C.items():
        c = res["models"][model][rung]["false_alarm_C"]
        assert (c["k"], c["n"]) == (k, n), (model, rung)


def test_clause_average_and_contrasts(res: dict[str, Any]) -> None:
    # D37: every capable model caught all 8 RJ items and none of the 12 IN items at R2 -> 0.5 averaged over 2 clauses
    for m in (Q14, GEMMA):
        c = res["models"][m]["R2"]["catch"]
        assert c["mean"] == 0.5 and c["units"] == 2 and c["ci95"] is None and "only 2" in c["ci_refused"]
        d = res["contrasts"][f"R2-R0 @ {m}"]
        assert not d["primary"] and d["clauses"] == 2 and d["mean_diff"] == 0.5 and d["signflip_p"] == 1.0  # D48
    assert res["models"][Q7]["R2"]["catch"]["mean"] == 0.4375  # (0/12 + 7/8) / 2
    assert not res["contrasts"][f"R2-R0 @ {Q7}"]["primary"]  # qwen2.5:7b is not one of the capable models


def test_rung_labels_for_unlabelled_rows() -> None:
    assert ladder.c_rung("R2") == ladder.c_rung("R1") == "R1-R2" and ladder.c_rung("R4'") == "R4"
    assert ladder.c_rung("R4'-drop25") == "R4-drop25" and ladder.c_rung("R5-drop50") == "R5-drop50"


def _rows(model: str, rung: str, config: str, cond: str, hits: dict[str, list[bool]]) -> list[dict[str, Any]]:
    out = []
    for clause, rs in hits.items():
        for k, right in enumerate(rs):
            base = {"model": model, "rung": rung, "config": config, "condition": cond, "planted": clause,
                    "cluster": clause, "pair_id": f"{clause}-{k}#{cond}", "invalid": False, "cant_confirm": False}
            out.append({**base, "role": "fault", "item_id": f"{clause}-{k}#{cond}#fault", "right": right, "clause": right,
                        "wrong": False, "any": right})
            out.append({**base, "role": "control", "item_id": f"{clause}-{k}#{cond}#control", "right": False,
                        "clause": False, "wrong": False, "any": k == 0})
    return out


def test_contrasts_on_twelve_clauses() -> None:
    clauses = [f"XX-C3-{i:03d}#cl-1" for i in range(12)]
    rows: list[dict[str, Any]] = []
    for m, r4 in ((Q14, [True, True, True, False]), (LLAMA, [False, False, False, False])):
        rows += _rows(m, "R2", "validity", "S-both", {c: [False, False, True, False] for c in clauses})
        rows += _rows(m, "R4", "validity-regstatus", "S-both", {c: r4 for c in clauses})
        rows += _rows(m, "R0", "validity-metaoff", "S-swap", {c: [False] * 4 for c in clauses})
    res = ladder.analyse(rows)
    r4 = res["models"][Q14]["R4"]
    assert r4["catch"]["mean"] == 0.75 and r4["catch"]["units"] == 12 and r4["catch"]["ci95"] is None  # zero width
    assert r4["false_alarm_matched"]["mean"] == 0.25 and r4["misnamed"] == {"k": 0, "n": 36}
    d = res["contrasts"][f"R4-R2 @ {Q14}"]
    assert d["clauses"] == 12 and d["mean_diff"] == 0.5 and d["signflip_p"] == pytest.approx(2 / 4096, abs=1e-6)
    assert not d["primary"] and "p_holm" not in d  # secondary since D48
    assert not res["contrasts"][f"R4-R2 @ {LLAMA}"]["primary"] and "p_holm" not in res["contrasts"][f"R4-R2 @ {LLAMA}"]
    w = res["contrasts"][f"(R4-R2) {Q14} - {LLAMA}"]
    assert w["mean_diff"] == 0.75 and w["clauses"] == 12  # 0.5 - (0 - 0.25)


def _item_rows(model: str, rung: str, config: str, role: str, hits: dict[str, bool], key: str) -> list[dict[str, Any]]:
    """One S-both row per item id (item -> hit), planted clause = the item id's prefix."""
    return [{"model": model, "rung": rung, "config": config, "condition": "S-both", "role": role, "item_id": i,
             "planted": i.split("/")[0], "cluster": i.split("/")[0], "invalid": False, "cant_confirm": False,
             "right": key == "right" and h, "clause": key == "right" and h, "wrong": False, "any": h,
             "validity_reason": h} for i, h in hits.items()]


def test_deference_counts_only_links_the_damage_dropped() -> None:
    # clause A: intact R5 catches, drop25-s0 misses -> in the set; R2 catches, R4-drop catches neither item -> 1.0
    # clause B: the damaged registry still catches -> out of the set
    # clause C: the intact registry misses -> out of the set
    items = ["A/1", "A/2", "B/1", "C/1"]
    rows = _item_rows(Q14, "R5", "reg-real", "fault", {"A/1": True, "A/2": True, "B/1": True, "C/1": False}, "right")
    rows += _item_rows(Q14, "R5-drop25", "reg-drop25-s0", "fault", {"A/1": False, "A/2": False, "B/1": True, "C/1": False}, "right")
    rows += _item_rows(Q14, "R2", "validity", "fault", dict.fromkeys(items, True), "right")
    rows += _item_rows(Q14, "R4-drop25", "validity-regstatus-drop25-s0", "fault", dict.fromkeys(items, False), "right")
    assert ladder.deference(rows, Q14) == {"A": 1.0}
    assert ladder.deference(rows, GEMMA) == {}


def test_discrimination_and_net_contrast_family() -> None:
    clauses = [f"XX-C3-{i:03d}#cl-1" for i in range(12)]
    rows: list[dict[str, Any]] = []
    for state in ladder.STATES:
        r4, r5 = ladder.state_rung("R4", state), ladder.state_rung("R5", state)
        cfg = "" if state == "intact" else f"-{state}-s0"
        rows += _rows(Q14, r4, "validity-regstatus" + cfg, "S-both", {c: [True, True, True, False] for c in clauses})
        rows += _rows(Q14, r5, ("reg-real" if state == "intact" else "reg" + cfg), "S-both", {c: [True] * 4 for c in clauses})
    res = ladder.analyse(rows)
    # R4: catch 0.75, false alarm 0.25 -> 0.5; R5 rows from _rows also alarm on control 0 -> catch 1 - fa 0.25 = 0.75
    assert ladder.discrimination(rows, Q14, "R4") == dict.fromkeys(clauses, 0.5)
    assert res["discrimination"][f"R5 intact @ {Q14}"]["mean_diff"] == 0.75
    fam = {k for k, v in res["contrasts"].items() if v["primary"]}
    assert fam == {f"Net-{s} @ {Q14}" for s in ladder.NET_PRIMARY}  # drop25 reported, not in the family
    assert all("p_holm" in res["contrasts"][k] for k in fam)
    assert res["contrasts"][f"Net-drop25 @ {Q14}"]["mean_diff"] == -0.25


def test_spurious_alarms_on_newly_flagged_controls() -> None:
    rows = _item_rows(Q14, "R5", "reg-real", "control", {"A/1": False, "A/2": False}, "any")
    rows += _item_rows(Q14, "R5-spurious10", "reg-spurious10-s0", "control", {"A/1": True, "A/2": False}, "any")
    rows += _item_rows(Q14, "R2", "validity", "control", {"A/1": False, "A/2": False}, "any")
    rows += _item_rows(Q14, "R4-spurious10", "validity-regstatus-spurious10-s0", "control", {"A/1": True, "A/2": True}, "any")
    assert ladder.spurious_alarms(rows, Q14) == {"n": 1, "r4": 1, "r2": 0, "items": 1, "clauses": 1}


def test_scoring_rules_e5() -> None:
    rows = _item_rows(Q14, "R2", "validity", "fault", {"A/1": True, "A/2": False}, "right")
    rows[1].update({"any": True, "clause": True})  # flagged the clause for the wrong reason
    m = ladder.rung_metrics(rows, Q14, "R2")
    assert (m["catch"]["mean"], m["catch_clause"]["mean"], m["catch_any"]["mean"]) == (0.5, 1.0, 1.0)


def test_sensitivity_sets_drop_the_listed_cases() -> None:  # D49
    rows = [{"case_id": c, "role": r} for c in ("A", "B", "C") for r in ("fault", "control")]
    sealed = {"controls_flagged": {"B": "INCOMPLETE"}, "strict_dropped": ["A", "B"]}
    assert {r["case_id"] for r in ladder.without_cases(rows, sealed, "S1")} == {"A", "C"}
    assert {r["case_id"] for r in ladder.without_cases(rows, sealed, "S2")} == {"C"}


def test_no_record_pairs_r4_and_r4n_on_the_dropped_links() -> None:  # D49
    items = ["A/1", "A/2", "B/1"]
    rows = _item_rows(Q14, "R5", "reg-real", "fault", {"A/1": True, "A/2": True, "B/1": True}, "right")
    rows += _item_rows(Q14, "R5-drop50", "reg-drop50-s0", "fault", {"A/1": False, "A/2": False, "B/1": True}, "right")
    rows += _item_rows(Q14, "R4-drop50", "validity-regstatus-drop50-s0", "fault", dict.fromkeys(items, False), "right")
    rows += _item_rows(Q14, "R4n-drop50", "validity-regnorec-drop50-s0", "fault", {"A/1": True, "A/2": False, "B/1": True},
                       "right")
    assert ladder.no_record_parts(rows, Q14) == {"A": (0.0, 0.5)}  # B: the damaged registry still catches it
    assert ladder.analyse(rows)["contrasts"][f"NoRec @ {Q14}"]["mean_diff"] == 0.5


def test_validity_discrimination_and_alarm_reasons() -> None:  # post hoc, review 2026-10-29
    rows = [{"model": Q14, "rung": "R4", "condition": "S-both", "role": "control", "planted": "A",
             "any": True, "validity_reason": False, "flags": "['ANY:A#cl-1:content_or_arithmetic']"},
            {"model": Q14, "rung": "R4", "condition": "S-both", "role": "fault", "planted": "A", "right": True}]
    assert ladder.discrimination(rows, Q14, "R4") == {"A": 0.0}
    assert ladder.discrimination(rows, Q14, "R4", "validity_reason") == {"A": 1.0}
    assert ladder.alarm_reasons(rows, Q14, "R4") == {"content_or_arithmetic": 1}


def test_recovery_counts_gains_and_losses_per_item_seed() -> None:  # post hoc, review 2026-10-29
    def row(rung: str, config: str, item: str, right: bool) -> dict[str, Any]:
        return {"model": Q14, "rung": rung, "config": config, "condition": "S-both", "role": "fault", "item_id": item,
                "right": right, "planted": "A"}
    rows = [row("R5-drop50", "reg-drop50-s0", "i1", False), row("R4-drop50", "validity-regstatus-drop50-s0", "i1", True),
            row("R5-drop50", "reg-drop50-s0", "i2", True), row("R4-drop50", "validity-regstatus-drop50-s0", "i2", False),
            row("R5-drop50", "reg-drop50-s0", "i3", True), row("R4-drop50", "validity-regstatus-drop50-s0", "i3", True)]
    assert ladder.recovery(rows, Q14, "drop50") == {"gained": 1, "lost": 1, "both": 1, "pairs": 3}
