"""D33 verifier-probe summary: sensitivity, matched-control FPR, paired discrimination and the P2-P5 contrasts.

Input: the rows written by ``scripts/run_verifier_probe.py`` (``arms/verifier_probe.record``), one per (item,
configuration, verifier model). Unit of inference: the cluster. Every cell is printed as k/n with its cluster
count; dev numbers are engineering evidence only.
"""

import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from suryabench.analysis.stats import (
    _perm_p,
    cluster_means,
    cluster_permutation_test,
    tost_equivalence,
)
from suryabench.arms.verifier_probe import CONFIGS, PLANT_CONDITIONS, PRIMARY

Row = dict[str, Any]

# name -> (configuration a, comparator b, conditions); the difference is a - b on fault right-reason catches
CONTRASTS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "P2 validity - support": ("validity", "support", PRIMARY),
    "P3 meta on - off (support)": ("support", "support-metaoff", PRIMARY),
    "P4 100-neutral - support": ("100-neutral", "support", PRIMARY),
    "P5 reg-real - support": ("reg-real", "support", ("S-both", "J")),
}
P4_MARGIN = 0.10


def kn(rows: list[Row], key: str) -> dict[str, Any]:
    """k/n of ``key`` over rows, with the number of clusters the n rows come from."""
    # rows saved before a key existed (e.g. cant_confirm, T2) count it as False
    return {"k": sum(bool(r.get(key)) for r in rows), "n": len(rows), "clusters": len({r["cluster"] for r in rows})}


def fmt(c: dict[str, Any]) -> str:
    return f"{c['k']}/{c['n']} ({c['clusters']}cl)" if c["n"] else "-"


def load_rows(out: Path) -> list[Row]:
    """Every saved block under ``out/<model>/blocks/<config>__<condition>.json``."""
    rows: list[Row] = []
    for f in sorted(out.glob("*/blocks/*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        rows += data["rows"] if isinstance(data, dict) else data
    return rows


def config_metrics(rows: list[Row]) -> dict[str, Any]:
    """One (model, configuration): per condition and pooled."""
    out: dict[str, Any] = {"invalid": kn(rows, "invalid")}
    by_cond: dict[str, Any] = {}
    for cond in PLANT_CONDITIONS:
        fault = [r for r in rows if r["condition"] == cond and r["role"] == "fault"]
        ctrl = {r["pair_id"]: r for r in rows if r["condition"] == cond and r["role"] == "control"}
        if not fault and not ctrl:
            continue
        pairs = [(f, ctrl[f["pair_id"]]) for f in fault if f["pair_id"] in ctrl]
        by_cond[cond] = {
            "right": kn(fault, "right"), "clause": kn(fault, "clause"), "wrong": kn(fault, "wrong"), "any": kn(fault, "any"),
            "right_outcome_changing": kn([r for r in fault if r["outcome_changing"]], "right"),
            "right_basis_only": kn([r for r in fault if not r["outcome_changing"]], "right"),
            "fpr": kn(list(ctrl.values()), "any"), "fpr_validity": kn(list(ctrl.values()), "validity_reason"),
            "cant_confirm_fault": kn(fault, "cant_confirm"), "cant_confirm_control": kn(list(ctrl.values()), "cant_confirm"),
            "discrimination": round(sum(int(f["right"]) - int(c["validity_reason"]) for f, c in pairs) / len(pairs), 4)
            if pairs else None, "pairs": len(pairs)}
    out["conditions"] = by_cond
    plant_fault = [r for r in rows if r["role"] == "fault"]
    plant_ctrl = [r for r in rows if r["role"] == "control"]
    prim = [r for r in plant_fault if r["condition"] in PRIMARY]
    c_ctrl = [r for r in rows if r["role"] == "c-control"]
    out["pooled"] = {"right_primary": kn(prim, "right"), "clause": kn(plant_fault, "clause"),
                     "wrong": kn(plant_fault, "wrong"), "fpr_controls": kn(plant_ctrl, "any"),
                     "fpr_validity_controls": kn(plant_ctrl, "validity_reason"),
                     "fpr_C": kn(c_ctrl, "any"), "fpr_validity_C": kn(c_ctrl, "validity_reason"),
                     "cant_confirm_C": kn(c_ctrl, "cant_confirm")}
    return out


def contrast(rows: list[Row], a: str, b: str, conds: tuple[str, ...], tost: bool = False) -> dict[str, Any]:
    """Cluster sign-flip test of right-reason sensitivity a - b, paired by (model, item) within cluster."""
    idx = {(r["model"], r["item_id"], r["config"]): r for r in rows}
    diffs: dict[str, list[float]] = defaultdict(list)
    fpr: dict[str, list[float]] = defaultdict(list)
    for (m, item, cfg), ra in idx.items():
        rb = idx.get((m, item, b))
        if cfg != a or rb is None or ra["condition"] not in conds:
            continue
        if ra["role"] == "fault":
            diffs[ra["cluster"]].append(float(ra["right"]) - float(rb["right"]))
        elif ra["role"] == "control":
            fpr[ra["cluster"]].append(float(ra["any"]) - float(rb["any"]))
    if not diffs:
        return {"n_items": 0, "p": None}
    res = cluster_permutation_test(dict(diffs))
    out: dict[str, Any] = {"n_items": sum(map(len, diffs.values())), "n_clusters": res.n_clusters,
                           "diff": round(res.observed, 4), "p": round(res.p, 4), "exact": res.exact,
                           "fpr_diff": round(float(cluster_means(dict(fpr)).mean()), 4) if fpr else None}
    if tost:
        means = cluster_means(dict(diffs))
        t = tost_equivalence(dict(diffs), P4_MARGIN)
        out.update({"p_noninferior_h0_ge_margin": round(_perm_p(means - P4_MARGIN, "less", 10000, 42)[0], 4),
                    "tost_p": round(t.p, 4), "equivalent": t.equivalent})
    return out


def summarise(rows: list[Row], timings: dict[str, Any] | None = None) -> dict[str, Any]:
    models = sorted({r["model"] for r in rows})
    per: dict[str, dict[str, Any]] = {}
    for m in models:
        per[m] = {c: config_metrics([r for r in rows if r["model"] == m and r["config"] == c])
                  for c in CONFIGS if any(r["model"] == m and r["config"] == c for r in rows)}
    contrasts = {"pooled": {k: contrast(rows, a, b, cs, k.startswith("P4")) for k, (a, b, cs) in CONTRASTS.items()}}
    for m in models:
        mr = [r for r in rows if r["model"] == m]
        contrasts[m] = {k: contrast(mr, a, b, cs, k.startswith("P4")) for k, (a, b, cs) in CONTRASTS.items()}
    return {"note": "D33 verifier probe, dev split: engineering evidence only, not a result.",
            "models": per, "contrasts": contrasts, "timings": timings or {}}


def markdown(s: dict[str, Any]) -> str:
    lines = ["# Verifier probe (D33), dev split", "", s["note"], "",
             "Cells: k/n (clusters). Right = planted clause named with the reason of its class (D32); clause = named, "
             "any reason; wrong = named, never with the right reason; FPR = any finding (D30: invalid counts) on the "
             "matched controls of S-both/S-swap/J/A, and on condition C.", ""]
    for m, cfgs in s["models"].items():
        lines += [f"## {m}", "", "| config | right S-both | right S-swap | right J | right A | clause (all) | wrong (all) "
                  "| FPR controls | FPR-validity controls | FPR C | FPR-validity C | invalid |", "|" + "---|" * 12]
        for c, v in cfgs.items():
            cell = [fmt(v["conditions"][k]["right"]) if k in v["conditions"] else "-" for k in PLANT_CONDITIONS]
            p = v["pooled"]
            lines.append(f"| {c} | " + " | ".join(cell + [fmt(p["clause"]), fmt(p["wrong"]), fmt(p["fpr_controls"]),
                                                          fmt(p["fpr_validity_controls"]), fmt(p["fpr_C"]),
                                                          fmt(p["fpr_validity_C"]), fmt(v["invalid"])]) + " |")
        lines += ["", "Right-reason catches split by outcome (outcome-changing / basis-only), and paired discrimination "
                  "(fault right-reason minus control validity-reason false alarm, mean per pair):", "",
                  "| config | condition | outcome-changing | basis-only | discrimination |", "|---|---|---|---|---|"]
        for c, v in cfgs.items():
            for k, d in v["conditions"].items():
                lines.append(f"| {c} | {k} | {fmt(d['right_outcome_changing'])} | {fmt(d['right_basis_only'])} | {d['discrimination']} |")
        lines.append("")
    lines += ["## Contrasts (right-reason sensitivity, cluster sign-flip; dev has 3 clusters, so p >= 0.25)", "",
              "| scope | contrast | items | clusters | diff | p | FPR diff | P4 non-inferiority p / TOST p |",
              "|---|---|---|---|---|---|---|---|"]
    for scope, cs in s["contrasts"].items():
        for k, v in cs.items():
            extra = f"{v.get('p_noninferior_h0_ge_margin')} / {v.get('tost_p')}" if "tost_p" in v else ""
            lines.append(f"| {scope} | {k} | {v['n_items']} | {v.get('n_clusters', '-')} | {v.get('diff', '-')} | "
                         f"{v['p']} | {v.get('fpr_diff', '-')} | {extra} |")
    if s["timings"]:
        lines += ["", "## Wall-clock per block", "", "| model | block | items | calls | seconds | calls/min |",
                  "|---|---|---|---|---|---|"]
        for m, blocks in s["timings"].items():
            for b, t in blocks.items():
                lines.append(f"| {m} | {b} | {t['items']} | {t['calls']} | {t['seconds']} | {t['calls_per_min']} |")
    return "\n".join(lines) + "\n"


def write_summary(out: Path) -> dict[str, Any]:
    """Recompute summary.json and summary.md from every saved block (atomic writes: two runs share ``out``)."""
    timings = {}
    for f in sorted(out.glob("*/timings.json")):
        timings[f.parent.name] = json.loads(f.read_text(encoding="utf-8"))
    s = summarise(load_rows(out), timings)
    for name, text in (("summary.json", json.dumps(s, indent=2) + "\n"), ("summary.md", markdown(s))):
        tmp = out / f".{name}.{os.getpid()}.tmp"
        tmp.write_text(text, encoding="utf-8", newline="\n")
        tmp.replace(out / name)
    return s
