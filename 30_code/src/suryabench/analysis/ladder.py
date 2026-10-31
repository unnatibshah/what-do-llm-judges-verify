"""The information-ladder analysis (D37, T3): per model and rung, from saved verifier-probe blocks. No model is run.

Unit of evidence: the distinct replaced (planted) clause. Every rate below is first a mean within each clause, then a
mean over clauses ("clause-averaged"); pooled k/n is reported beside it.

Per model x rung:
- ``catch``: right-reason catch (D32) on the rung's fault items.
- ``false_alarm_matched``: any finding (D30: invalid counts) on the matched controls of the same blocks.
- ``false_alarm_C``: any finding on the clean correct answers (condition C) of the rung's configuration. Grouped by
  rule group, since C items plant nothing.
- ``cant_confirm_fault`` / ``cant_confirm_correct`` (E2): a ``currency_unconfirmed`` finding on faults / on
  controls and C.
- ``misnamed``: planted clause flagged, but never with the right reason, over planted clause flagged (E4).
- ``invalid``: invalid replies over all of the rung's rows.
- E5 (D48), the same replies under looser scoring: ``catch_any`` (any finding on a fault), ``catch_clause`` (the
  planted clause named, any reason) and ``false_alarm_validity`` (a validity-reason finding on a matched control).

Contrasts (D37): on clause catch rates, a difference per clause, a 95% bootstrap over clauses and a two-sided
sign-flip test over clauses (``analysis/stats.py``). Secondary: R4 - R2 and R2 - R0 (primary in v3), R3 - R2,
R4' - R1, R5 - R4, and weak-vs-capable in R4 - R2 (per clause, the capable model's R4 - R2 minus the weak model's).

Primary since D48 (PREREGISTRATION_v3_AMENDMENT_1, capable models; Holm over 8 tests, 10 with NoRec since D49):
- ``Net-<state>``: per-clause discrimination (S-both catch minus matched-control false alarm) at R4 minus at R5, with
  the registry intact, drop50 and spurious10 (drop25 is reported, not in the family). Damaged rungs pool their seeds.
- ``Defer``: on S-both faults the intact registry catches and a drop-damaged one (any drop, any seed) misses, the
  item's R2 catch minus its R4-damage catch, averaged within clause.
- ``NoRec`` (D49, amendment 2): on the same dropped-link faults as ``Defer`` (any drop, any seed), the item's
  R4n-damage catch minus its R4-damage catch, averaged within clause. R4n differs from R4 in one word: a clause the
  registry links to nothing reads "no_amendment_recorded", not "in_force". Its cost, false alarms at R4n against R4
  on the same controls, is reported beside it (``rung_metrics``), with no test.
- ``spurious``: (E3') on matched controls a spurious registry flags and the intact one does not, false alarms at
  R4-spurious10 against R2 on the same items (pooled k/n, no test).
A primary contrast with fewer than ``MIN_CLAUSES`` clauses enters the family with p = 1.
Sensitivity (D49, amendment 2): ``--sealed TEST_MANIFEST_v3.json --sensitivity S1`` drops every row of the cases whose
checked control was judged not CORRECT (``controls_flagged``); ``S2`` drops the cases v3's rule would have dropped
(``strict_dropped``: deciding clauses differ from the key). Each writes its own output folder.
Descriptive (D49, no test): ``splits``, right-reason catch k/n per model and rung by amendment wording (explicit or
implicit, from the candidate manifest) and by whether the fault changes the outcome; ``cost``, mean prompt and
completion tokens and seconds per call per model and rung.
Rungs come from ``arms/verifier_probe.rung`` (rows saved before T2 carry no rung label and are labelled here).

    python -m suryabench.analysis.ladder --blocks 50_analysis/results/probe_v2 --out 50_analysis/results/ladder_dev
"""

import argparse
import ast
import csv
import json
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np

from suryabench.analysis.stats import (
    cluster_bootstrap_ci_checked,
    cluster_permutation_test,
    holm_family,
)
from suryabench.arms.verifier_probe import DAMAGE
from suryabench.arms.verifier_probe import rung as rung_of
from suryabench.paths import resolve

Row = dict[str, Any]
CAPABLE = ("qwen2.5:14b", "gemma-4-26b-a4b-it")
WEAK = ("llama3.1:8b",)
CONTRASTS: dict[str, tuple[str, str, bool]] = {  # name -> (rung a, rung b, primary); the difference is a - b
    "R4-R2": ("R4", "R2", False), "R2-R0": ("R2", "R0", False),  # primary in v3, secondary since D48
    "R3-R2": ("R3", "R2", False), "R4'-R1": ("R4'", "R1", False), "R5-R4": ("R5", "R4", False),
}
RUNG_ORDER = ["R0", "R1", "R2", "R3", "R4", "R4'", "R5", "R0-cc", "R1-cc", "R2-cc"]
STATES = ("intact", *DAMAGE)  # registry states of Q1 (D48)
NET_PRIMARY = ("intact", "drop50", "spurious10")
MIN_CLAUSES = 10
SPLIT_RUNGS = ("R2", "R4", "R4n", "R4-drop50", "R4n-drop50")
WORDING = resolve("50_analysis/results/ladder_design/candidate_v3_manifest.json")
SENSITIVITY = {"S1": "controls_flagged", "S2": "strict_dropped"}  # D49: the seal manifest field each set drops


def load_rows(paths: Iterable[Path]) -> list[Row]:
    """Every row of every block under ``paths`` (a block file or a results folder), each with its rung."""
    rows: list[Row] = []
    for p in paths:
        files = [p] if p.is_file() else sorted(p.glob("*/blocks/*.json"))
        for f in files:
            block = json.loads(f.read_text(encoding="utf-8"))
            for r in block["rows"]:
                rows.append({**r, "rung": r.get("rung") or rung_of(r["config"], r["condition"])})
    return rows


def c_rung(rung: str) -> str:
    """The condition-C label that carries a rung's clean-answer false alarms (R1 and R2 share C; R4' is R4 on C)."""
    if rung in {"R1", "R2"}:
        return "R1-R2"
    if rung in {"R1-cc", "R2-cc"}:
        return "R1-R2-cc"
    return rung.replace("R4'", "R4")


def kn(rows: list[Row], key: str) -> dict[str, int]:
    return {"k": sum(bool(r.get(key)) for r in rows), "n": len(rows)}


def by_unit(rows: list[Row], unit: str, key: str) -> dict[str, float]:
    """Mean of ``key`` within each value of ``unit`` (the planted clause, or the rule group for C)."""
    groups: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        groups[str(r[unit])].append(float(bool(r.get(key))))
    return {u: float(np.mean(v)) for u, v in sorted(groups.items())}


def averaged(rows: list[Row], unit: str, key: str) -> dict[str, Any]:
    """Clause- (or group-) averaged rate with pooled k/n and the bootstrap over units (refused below 10 units)."""
    per = by_unit(rows, unit, key)
    out: dict[str, Any] = {"mean": round(float(np.mean(list(per.values()))), 4) if per else None, "units": len(per),
                           **kn(rows, key)}
    if per:
        ci, why = cluster_bootstrap_ci_checked(rows, unit, lambda rs: float(np.mean(list(by_unit(rs, unit, key).values()))))
        out["ci95"] = [round(ci.ci_lower, 4), round(ci.ci_upper, 4)] if ci else None
        out["ci_refused"] = why
    return out


def rung_metrics(rows: list[Row], model: str, rung: str) -> dict[str, Any]:
    mine = [r for r in rows if r["model"] == model]
    cells = [r for r in mine if r["rung"] == rung and r["condition"] != "C"]
    faults = [r for r in cells if r["role"] == "fault"]
    controls = [r for r in cells if r["role"] == "control"]
    clean = [r for r in mine if r["rung"] == c_rung(rung) and r["condition"] == "C"]
    flagged = [r for r in faults if r.get("clause")]
    return {
        "configs": sorted({r["config"] for r in cells}), "conditions": sorted({r["condition"] for r in cells}),
        "catch": averaged(faults, "planted", "right"),
        "false_alarm_matched": averaged(controls, "planted", "any"),
        "false_alarm_C": averaged(clean, "cluster", "any"),
        "cant_confirm_fault": averaged(faults, "planted", "cant_confirm"),
        "cant_confirm_correct": kn(controls + clean, "cant_confirm"),
        "misnamed": {"k": sum(bool(r.get("wrong")) for r in flagged), "n": len(flagged)},
        "invalid": kn(cells + clean, "invalid"),
        "catch_any": averaged(faults, "planted", "any"),
        "catch_clause": averaged(faults, "planted", "clause"),
        "false_alarm_validity": averaged(controls, "planted", "validity_reason"),
        # D49: S-both only, so every arm's confusion counts cover the same items (R5 and R4' also run S-swap)
        "catch_sboth": kn([r for r in faults if r["condition"] == "S-both"], "right"),
        "false_alarm_sboth": kn([r for r in controls if r["condition"] == "S-both"], "any"),
    }


def clause_rates(rows: list[Row], model: str, rung: str) -> dict[str, float]:
    return by_unit([r for r in rows if r["model"] == model and r["rung"] == rung and r["role"] == "fault"],
                   "planted", "right")


def contrast(diffs: dict[str, float]) -> dict[str, Any]:
    """Mean per-clause difference, its bootstrap over clauses and the two-sided sign-flip p over clauses."""
    if not diffs:
        return {"clauses": 0}
    recs = [{"clause": c, "d": d} for c, d in diffs.items()]
    ci, why = cluster_bootstrap_ci_checked(recs, "clause", lambda rs: float(np.mean([r["d"] for r in rs])))
    perm = cluster_permutation_test({c: [d] for c, d in diffs.items()})
    return {"clauses": len(diffs), "mean_diff": round(float(np.mean(list(diffs.values()))), 4),
            "ci95": [round(ci.ci_lower, 4), round(ci.ci_upper, 4)] if ci else None, "ci_refused": why,
            "signflip_p": round(perm.p, 6), "exact": perm.exact}


def paired(rows: list[Row], model: str, a: str, b: str) -> dict[str, float]:
    ra, rb = clause_rates(rows, model, a), clause_rates(rows, model, b)
    return {c: ra[c] - rb[c] for c in sorted(set(ra) & set(rb))}


def state_rung(rung: str, state: str) -> str:
    return rung if state == "intact" else f"{rung}-{state}"


def discrimination(rows: list[Row], model: str, rung: str, fa_key: str = "any") -> dict[str, float]:
    """Per clause: S-both right-reason catch minus any-finding false alarm on the matched controls (D48, Q1). R5 is
    deterministic, so if this model has no R5 block another model's is used."""
    cells = [r for r in rows if r["rung"] == rung and r["condition"] == "S-both"]
    mine = [r for r in cells if r["model"] == model]
    if not mine and rung.startswith("R5") and cells:
        mine = [r for r in cells if r["model"] == cells[0]["model"]]
    catch = by_unit([r for r in mine if r["role"] == "fault"], "planted", "right")
    fa = by_unit([r for r in mine if r["role"] == "control"], "planted", fa_key)
    return {c: catch[c] - fa[c] for c in sorted(set(catch) & set(fa))}


def alarm_reasons(rows: list[Row], model: str, rung: str) -> dict[str, int]:
    """Post hoc (review, 2026-10-29): the reason codes of the findings raised on matched correct answers (S-both)."""
    out: dict[str, int] = defaultdict(int)
    for r in rows:
        if r["model"] == model and r["rung"] == rung and r["condition"] == "S-both" and r["role"] == "control":
            flags = r.get("flags") or []
            for f in (ast.literal_eval(flags) if isinstance(flags, str) else flags):
                out[str(f).rsplit(":", 1)[-1]] += 1
    return dict(sorted(out.items()))


def _damage_seed(config: str) -> tuple[str, int]:
    """reg-drop25-s3 / validity-regstatus-drop25-s3 -> ("drop25", 3)."""
    base, seed = config.rsplit("-s", 1)
    return base.rsplit("-", 1)[1], int(seed)


def _registry_hits(rows: list[Row], role: str, key: str) -> dict[tuple[str, int, str], bool]:
    """(damage or "intact", seed, item) -> whether the R5 lookup hit the item (any model's block; R5 is deterministic)."""
    out: dict[tuple[str, int, str], bool] = {}
    for r in rows:
        if r["role"] != role or r["condition"] != "S-both" or not str(r["rung"]).startswith("R5"):
            continue
        state = ("intact", 0) if r["rung"] == "R5" else _damage_seed(r["config"])
        out[(*state, r["item_id"])] = bool(r.get(key))
    return out


def deference_parts(rows: list[Row], model: str) -> dict[str, tuple[float, float]]:
    """Q2 (D48): per clause, over (item, drop damage, seed) where the intact registry catches the fault and the damaged
    one does not, the mean R2 catch and the mean R4-damage catch of those items."""
    hits = _registry_hits(rows, "fault", "right")
    mine = [r for r in rows if r["model"] == model and r["role"] == "fault" and r["condition"] == "S-both"]
    r2 = {r["item_id"]: bool(r["right"]) for r in mine if r["rung"] == "R2"}
    pairs: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for r in mine:
        if not str(r["rung"]).startswith("R4-drop"):
            continue
        damage, seed = _damage_seed(r["config"])
        item = r["item_id"]
        if hits.get(("intact", 0, item)) and (damage, seed, item) in hits and not hits[(damage, seed, item)] and item in r2:
            pairs[str(r["planted"])].append((float(r2[item]), float(bool(r["right"]))))
    return {c: (float(np.mean([a for a, _ in v])), float(np.mean([b for _, b in v]))) for c, v in sorted(pairs.items())}


def no_record_parts(rows: list[Row], model: str) -> dict[str, tuple[float, float]]:
    """NoRec (D49): per clause, over (item, drop damage, seed) where the intact registry catches the fault and the
    damaged one does not, the mean R4-damage catch and the mean R4n-damage catch of the same items and seeds."""
    hits = _registry_hits(rows, "fault", "right")
    mine = [r for r in rows if r["model"] == model and r["role"] == "fault" and r["condition"] == "S-both"]
    by: dict[tuple[str, str, int, str], bool] = {}
    for r in mine:
        g = str(r["rung"])
        if g.startswith(("R4-drop", "R4n-drop")):
            damage, seed = _damage_seed(r["config"])
            by[(g.split("-")[0], damage, seed, r["item_id"])] = bool(r["right"])
    pairs: dict[str, list[tuple[float, float]]] = defaultdict(list)
    planted = {r["item_id"]: str(r["planted"]) for r in mine}
    for (arm, damage, seed, item), right in by.items():
        if arm != "R4" or ("R4n", damage, seed, item) not in by:
            continue
        if hits.get(("intact", 0, item)) and (damage, seed, item) in hits and not hits[(damage, seed, item)]:
            pairs[planted[item]].append((float(right), float(by[("R4n", damage, seed, item)])))
    return {c: (float(np.mean([a for a, _ in v])), float(np.mean([b for _, b in v]))) for c, v in sorted(pairs.items())}


def deference(rows: list[Row], model: str) -> dict[str, float]:
    """Per clause, R2 catch minus R4-damage catch on the dropped links. Positive = the wrong line cost catches."""
    return {c: a - b for c, (a, b) in deference_parts(rows, model).items()}


def spurious_alarms(rows: list[Row], model: str) -> dict[str, int]:
    """E3' (D48): matched controls a spurious registry flags and the intact one does not; false alarms on those
    items at R4-spurious10 and at R2 (pooled over seeds)."""
    hits = _registry_hits(rows, "control", "any")
    mine = [r for r in rows if r["model"] == model and r["role"] == "control" and r["condition"] == "S-both"]
    r2 = {r["item_id"]: bool(r["any"]) for r in mine if r["rung"] == "R2"}
    out = {"n": 0, "r4": 0, "r2": 0}
    items, clauses = set(), set()
    for r in mine:
        if r["rung"] != "R4-spurious10":
            continue
        damage, seed = _damage_seed(r["config"])
        item = r["item_id"]
        if hits.get((damage, seed, item)) and ("intact", 0, item) in hits and not hits[("intact", 0, item)] and item in r2:
            out["n"] += 1
            out["r4"] += bool(r["any"])
            out["r2"] += r2[item]
            items.add(item)
            clauses.add(str(r["planted"]))
    return {**out, "items": len(items), "clauses": len(clauses)}


def recovery(rows: list[Row], model: str, state: str) -> dict[str, int]:
    """Post hoc (review, 2026-10-29): on S-both faults, per (item, seed), right-reason catches the reviewer with the
    damaged status line made that the damaged lookup missed ("gained"), and the reverse ("lost")."""
    r5 = {(r["config"].rsplit("-s", 1)[-1], r["item_id"]): bool(r["right"]) for r in rows
          if r["rung"] == state_rung("R5", state) and r["condition"] == "S-both" and r["role"] == "fault"}
    if state == "intact":
        r5 = {("0", k[1]): v for k, v in r5.items()}
    out = {"gained": 0, "lost": 0, "both": 0, "pairs": 0}
    for r in rows:
        if r["model"] != model or r["rung"] != state_rung("R4", state) or r["condition"] != "S-both" or r["role"] != "fault":
            continue
        key = ("0" if state == "intact" else r["config"].rsplit("-s", 1)[-1], r["item_id"])
        if key not in r5:
            continue
        a, b = bool(r["right"]), r5[key]
        out["pairs"] += 1
        out["gained"] += a and not b
        out["lost"] += b and not a
        out["both"] += a and b
    return out


def analyse(rows: list[Row]) -> dict[str, Any]:
    models = sorted({r["model"] for r in rows})
    rungs = [g for g in RUNG_ORDER if any(r["rung"] == g for r in rows)]
    rungs += sorted({str(r["rung"]) for r in rows if r["rung"] and r["rung"] not in rungs and r["condition"] != "C"})
    out: dict[str, Any] = {"models": {m: {g: rung_metrics(rows, m, g) for g in rungs
                                          if any(r["model"] == m and r["rung"] == g for r in rows)} for m in models}}
    contrasts: dict[str, Any] = {}
    for name, (a, b, primary) in CONTRASTS.items():
        for m in models:
            d = paired(rows, m, a, b)
            if d:
                contrasts[f"{name} @ {m}"] = {"primary": primary and m in CAPABLE, "model": m, **contrast(d)}
    for cap in (m for m in models if m in CAPABLE):
        for weak in (m for m in models if m in WEAK):
            dc, dw = paired(rows, cap, "R4", "R2"), paired(rows, weak, "R4", "R2")
            d = {c: dc[c] - dw[c] for c in sorted(set(dc) & set(dw))}
            if d:
                contrasts[f"(R4-R2) {cap} - {weak}"] = {"primary": False, "model": f"{cap} vs {weak}", **contrast(d)}
    discrim: dict[str, Any] = {}
    for m in models:
        r2 = discrimination(rows, m, "R2")
        if r2:
            discrim[f"R2 @ {m}"] = contrast(r2)  # the reviewer with no registry: the flat reference in the D48 figure
        for state in STATES:
            r4, r5 = discrimination(rows, m, state_rung("R4", state)), discrimination(rows, m, state_rung("R5", state))
            if r4:
                discrim[f"R4 {state} @ {m}"] = contrast(r4)
            if r5:
                discrim[f"R5 {state} @ {m}"] = contrast(r5)
            d = {c: r4[c] - r5[c] for c in sorted(set(r4) & set(r5))}
            if d:
                contrasts[f"Net-{state} @ {m}"] = {"primary": state in NET_PRIMARY and m in CAPABLE, "model": m,
                                                   **contrast(d)}
        d = deference(rows, m)
        if d:
            contrasts[f"Defer @ {m}"] = {"primary": m in CAPABLE, "model": m, **contrast(d)}
        d = {c: b - a for c, (a, b) in no_record_parts(rows, m).items()}
        if d:
            contrasts[f"NoRec @ {m}"] = {"primary": m in CAPABLE, "model": m, **contrast(d)}
        for state in ("intact", "drop25", "drop50"):
            r4n = discrimination(rows, m, state_rung("R4n", state))
            if r4n:
                discrim[f"R4n {state} @ {m}"] = contrast(r4n)
    # D48 (amendment 1, section 3): Holm over Net-{intact,drop50,spurious10} and Defer (and NoRec, D49) for each
    # capable model run;
    # a contrast on fewer than MIN_CLAUSES clauses enters with p = 1
    family = {k: (v["signflip_p"] if v["clauses"] >= MIN_CLAUSES else 1.0)
              for k, v in contrasts.items() if v["primary"] and "signflip_p" in v}
    for k, h in (holm_family(family) if family else {}).items():
        contrasts[k]["p_holm"], contrasts[k]["holm_reject"] = round(float(h["p_holm"]), 6), bool(h["reject"])
    out["contrasts"] = contrasts
    out["discrimination"] = discrim
    out["spurious"] = {m: spurious_alarms(rows, m) for m in models}
    out["deference"] = {}
    for m in models:
        parts = deference_parts(rows, m)
        if parts:
            out["deference"][m] = {"clauses": len(parts), "r2_catch": round(float(np.mean([a for a, _ in parts.values()])), 4),
                                   "r4_damage_catch": round(float(np.mean([b for _, b in parts.values()])), 4)}
    # Post hoc (review, 2026-10-29), not preregistered: Q1 with false alarms counted only when the finding gives a
    # validity reason (the only kind the lookup can raise), and the reasons behind the matched-control alarms
    out["recovery"] = {f"{state} @ {m}": recovery(rows, m, state) for m in models for state in ("intact", "drop50")}
    out["q1_validity"] = {}
    out["alarm_reasons"] = {}
    for m in models:
        for state in STATES:
            r4 = discrimination(rows, m, state_rung("R4", state), "validity_reason")
            r5 = discrimination(rows, m, state_rung("R5", state), "validity_reason")
            d = {c: r4[c] - r5[c] for c in sorted(set(r4) & set(r5))}
            if d:
                out["q1_validity"][f"Net-{state} @ {m}"] = contrast(d)
        for g in ("R2", "R4", "R4n", "R5"):
            reasons = alarm_reasons(rows, m, g)
            if reasons:
                out["alarm_reasons"][f"{g} @ {m}"] = reasons
    out["no_record"] = {}
    for m in models:
        parts = no_record_parts(rows, m)
        if parts:
            out["no_record"][m] = {"clauses": len(parts), "r4_damage_catch": round(float(np.mean([a for a, _ in parts.values()])), 4),
                                   "r4n_damage_catch": round(float(np.mean([b for _, b in parts.values()])), 4)}
    return out


def per_clause_rows(rows: list[Row]) -> list[list[Any]]:
    keys = sorted({(r["model"], str(r["rung"]), str(r["planted"])) for r in rows if r["rung"] and r["planted"]})
    out = []
    for m, g, c in keys:
        cell = [r for r in rows if r["model"] == m and r["rung"] == g and r["planted"] == c]
        f = [r for r in cell if r["role"] == "fault"]
        k = [r for r in cell if r["role"] == "control"]
        out.append([m, g, c, len(f), sum(bool(r["right"]) for r in f), round(float(np.mean([bool(r["right"]) for r in f])), 4)
                    if f else "", len(k), sum(bool(r["any"]) for r in k), sum(bool(r.get("cant_confirm")) for r in f),
                    sum(bool(r.get("wrong")) for r in f), sum(bool(r["invalid"]) for r in cell)])
    return out


def _cell(d: dict[str, Any]) -> str:
    mean = "-" if d.get("mean") is None else f"{d['mean']:.2f}"
    return f"{mean} ({d['k']}/{d['n']}, {d.get('units', '-')} u)"


def markdown(res: dict[str, Any]) -> str:
    lines = ["# Information ladder", "",
             "Cells: clause-averaged rate (pooled k/n, number of clauses or rule groups). Catch = right-reason catch "
             "(D32); FA = any finding on correct answers (D30); C is grouped by rule group.", ""]
    for m, rungs in res["models"].items():
        lines += [f"## {m}", "", "| rung | catch | FA matched | FA C | can't confirm (faults) | misnamed | invalid |",
                  "|---|---|---|---|---|---|---|"]
        for g, v in rungs.items():
            lines.append(f"| {g} | {_cell(v['catch'])} | {_cell(v['false_alarm_matched'])} | {_cell(v['false_alarm_C'])} "
                         f"| {_cell(v['cant_confirm_fault'])} | {v['misnamed']['k']}/{v['misnamed']['n']} "
                         f"| {v['invalid']['k']}/{v['invalid']['n']} |")
        lines.append("")
    lines += ["## Contrasts (per-clause difference in catch; sign-flip over clauses, two-sided)", "",
              "| contrast | primary | clauses | mean diff | 95% CI | p | p (Holm) |", "|---|---|---|---|---|---|---|"]
    for name, c in res["contrasts"].items():
        ci = c.get("ci95") or f"refused: {c.get('ci_refused')}"
        lines.append(f"| {name} | {'yes' if c['primary'] else 'no'} | {c['clauses']} | {c.get('mean_diff')} | {ci} "
                     f"| {c.get('signflip_p')} | {c.get('p_holm', '')} |")
    lines += ["", "## Discrimination (D48: S-both catch minus matched false alarm, clause-averaged)", "",
              "| rung, registry, model | clauses | mean | 95% CI |", "|---|---|---|---|"]
    for name, c in res.get("discrimination", {}).items():
        lines.append(f"| {name} | {c['clauses']} | {c.get('mean_diff')} | {c.get('ci95') or c.get('ci_refused')} |")
    lines += ["", "## Spurious links (E3': controls the spurious registry flags; false alarms R4-spurious10 vs R2)", "",
              "| model | items | R4 | R2 |", "|---|---|---|---|"]
    for m, v in res.get("spurious", {}).items():
        lines.append(f"| {m} | {v['n']} | {v['r4']} | {v['r2']} |")
    return "\n".join(lines) + "\n"


def splits(rows: list[Row], wording: dict[str, str]) -> dict[str, Any]:
    """D49: right-reason catch k/n on S-both faults by amendment wording and by outcome change (descriptive)."""
    out: dict[str, Any] = {}
    for r in rows:
        if r["role"] != "fault" or r["condition"] != "S-both" or r["rung"] not in SPLIT_RUNGS:
            continue
        for split, value in (("wording", wording.get(str(r["planted"]), "UNKNOWN")),
                             ("outcome", "changing" if str(r.get("outcome_changing")) == "True" else "basis_only")):
            cell = out.setdefault(f"{r['rung']} @ {r['model']}", {}).setdefault(split, {}).setdefault(
                value, {"k": 0, "n": 0, "clauses": set()})
            cell["k"] += bool(r["right"])
            cell["n"] += 1
            cell["clauses"].add(str(r["planted"]))
    for v in out.values():
        for split in v.values():
            for cell in split.values():
                cell["clauses"] = len(cell["clauses"])
    return out


def cost(rows: list[Row]) -> dict[str, Any]:
    """D49: mean prompt tokens, completion tokens and seconds per call, per model and rung (descriptive)."""
    cells: dict[str, list[Row]] = defaultdict(list)
    for r in rows:
        if r["rung"]:
            cells[f"{r['rung']} @ {r['model']}"].append(r)
    return {k: {"calls": len(v), **{f: round(float(np.mean([float(r.get(f) or 0) for r in v])), 2)
                                    for f in ("prompt_tokens", "completion_tokens", "latency_sec")}}
            for k, v in sorted(cells.items())}


def by_instrument(contrasts: dict[str, Any], diffs: dict[str, dict[str, float]], instrument: dict[str, str]
                  ) -> dict[str, Any]:
    """Post hoc (review, 2026-10-29): a primary contrast with the amending instrument as the unit (clause differences
    averaged within instrument), since clauses changed by one instrument may not be independent."""
    out = {}
    for name, d in diffs.items():
        groups: dict[str, list[float]] = defaultdict(list)
        for clause, v in d.items():
            groups[instrument.get(clause, clause)].append(v)
        out[name] = {"instruments": len(groups), **contrast({g: float(np.mean(v)) for g, v in groups.items()})}
    return out


def without_cases(rows: list[Row], sealed: dict[str, Any], sensitivity: str) -> list[Row]:
    """D49 sensitivity sets: every row (fault, control, C) of the listed cases removed."""
    drop = set(sealed[SENSITIVITY[sensitivity]])
    return [r for r in rows if r["case_id"] not in drop]


def write(rows: list[Row], out: Path) -> dict[str, Any]:
    res = analyse(rows)
    man = json.loads(WORDING.read_text(encoding="utf-8")) if WORDING.exists() else {"replaced_clauses": []}
    res["splits"] = splits(rows, {c["clause"]: c["explicit_implicit"] for c in man["replaced_clauses"]})
    res["cost"] = cost(rows)
    instrument = {c["clause"]: c["successor"].split("#")[0] for c in man["replaced_clauses"]}
    diffs: dict[str, dict[str, float]] = {}
    for m in sorted({r["model"] for r in rows} & set(CAPABLE)):
        for state in NET_PRIMARY:
            r4, r5 = discrimination(rows, m, state_rung("R4", state)), discrimination(rows, m, state_rung("R5", state))
            diffs[f"Net-{state} @ {m}"] = {c: r4[c] - r5[c] for c in sorted(set(r4) & set(r5))}
    res["by_instrument"] = by_instrument(res["contrasts"], {k: v for k, v in diffs.items() if v}, instrument)
    out.mkdir(parents=True, exist_ok=True)
    (out / "ladder.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8", newline="\n")
    with open(out / "ladder_per_clause.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["model", "rung", "clause", "faults", "right", "catch_rate", "controls", "control_alarms",
                    "cant_confirm", "misnamed", "invalid"])
        w.writerows(per_clause_rows(rows))
    (out / "summary.md").write_text(markdown(res), encoding="utf-8", newline="\n")
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--blocks", nargs="+", required=True, help="results folders (<model>/blocks/*.json) or block files")
    ap.add_argument("--out", required=True)
    ap.add_argument("--sealed", help="TEST_MANIFEST_v3.json, for --sensitivity")
    ap.add_argument("--sensitivity", choices=sorted(SENSITIVITY))
    args = ap.parse_args()
    if bool(args.sealed) != bool(args.sensitivity):
        ap.error("--sealed and --sensitivity go together")
    rows = load_rows(resolve(b) for b in args.blocks)
    if args.sensitivity:
        rows = without_cases(rows, json.loads(resolve(args.sealed).read_text(encoding="utf-8")), args.sensitivity)
    res = write(rows, resolve(args.out))
    print(f"{len(res['models'])} models, {len(res['contrasts'])} contrasts -> {args.out}")


if __name__ == "__main__":
    main()
