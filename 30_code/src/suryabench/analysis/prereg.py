"""Preregistered confirmatory analysis of Paper A v2 (PREREGISTRATION_v2.md sections 3 and 4).

    python -m suryabench.analysis.prereg --index <exposure_index.json> [--index ...] \\
        --cases <cases.json> --out <dir> [--spec numbers_spec.json]
    python -m suryabench.analysis.prereg --write-spec <dir>     # regenerate the macro specs

Writes ``<out>/results_v2.json``. Unit of inference: the cluster (``cluster_id``). The pooled analysis
pairs by (model, case) within cluster; every test is also run per model (secondary, uncorrected).

Primary metric: evidence-level sensitivity over decision-committed planted faults in J (F2), S-both
(F3; D28, S-swap is secondary) and A (F5), pooled. A catch is a finding that names the planted clause AND gives
the reason of the event's class (D32: F2 wrong_jurisdiction, F3 not_in_force, F5 not_applicable). Exploratory
beside it: clause-only sensitivity (the D26 catch, any reason), wrong-reason catches (clause named, reason
not matching) and validity-reason false alarms on C (a finding with a validity reason on a clean case).
Co-primary: case-level false-positive rate on condition C (any finding). D30: an invalid verifier reply is a
miss for sensitivity AND a false alarm for FPR. A paired contrast pairs the events committed under both
configurations (committed = the generator cited the planted clause and its approve/block outcome flipped).
D27: the generator runs once per condition with metadata on and every verifier configuration checks that
same output, so both sides of every contrast, P3 included, have the same committed events.

Family (Holm over exactly five tests, all at metadata on except P3, D29; a test that cannot be computed
enters with p = 1 so the family size never shrinks):
  P1  one-sided: pooled sensitivity at 000 (support prompt, metadata on) < 0.30.
  P2  000-validity vs 000.            P3  verifier metadata on vs off at 000 (generator fixed).
  P4  100-neutral vs 000: TOST with a +-10-point margin.   P5  reg-real vs 000 on F2+F3 (J, S-both).
  P2, P3, P5 follow the co-primary improvement rule: sensitivity rises (two-sided cluster sign-flip
  permutation, Holm-adjusted p < 0.05) AND the false-positive rate on C does not rise by 10 points
  or more (one-sided non-inferiority, alpha 0.05, not Holm-adjusted).

P1 test choice. A cluster-level sign-flip permutation test on cluster mean sensitivities centred at
0.30 (``stats.cluster_one_sample_test``), not a one-sample cluster bootstrap. Reasons: it is the same
machinery as every other preregistered test (D15), it is exact for up to 13 clusters, and a bootstrap
interval is refused below 10 clusters and degenerate at 0, so a bootstrap test would give no verdict
exactly where H1 predicts the data (sensitivity near 0). Costs: it assumes the cluster means are
symmetric about 0.30 under H0 (approximate for bounded proportions), its smallest attainable p is
2^-k (k clusters; with Holm over five tests, k >= 7 is needed to reach 0.05), and the statistic is the
mean of cluster means, so ``P1.observed`` can differ from the event-weighted pooled sensitivity (both
are reported). With fewer than 10 clusters the test is reported and the CI is suppressed with an
explicit ``ci_note``.

P4. "Supported if equivalent or lower" is the claim that 100-neutral does not raise sensitivity by
the margin, i.e. H0: difference >= +10 points. The family p-value is that one-sided p (``p_upper``);
the TOST p (``tost.p``) and whether equivalence in both directions holds are reported beside it.

Everything not in the family (cross-model, reflect, registry noise curve, paraphrase spread, the taxonomy
ablation, S-swap, Arm 5, per-class cells, F4 completeness, generator accuracy on N, commitment rates,
McNemar) is exploratory and labelled so. Dev numbers from a pilot are engineering checks, never results.
"""

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from suryabench.analysis.paper import (
    EXPOSURE_CLASS,
    NOISE_LEVELS,
    PRIMARY_CONDITIONS,
    _flagged,
    _validity_flagged,
    analyse_exposure,
    exposure_events,
    load_exposure,
)
from suryabench.analysis.stats import (
    cluster_bootstrap_ci_checked,
    cluster_one_sample_test,
    cluster_permutation_test,
    coprimary_improvement,
    holm_family,
    tost_equivalence,
)
from suryabench.paths import display, resolve

ALPHA = 0.05
P1_NULL = 0.30
FPR_MARGIN = 0.10
TOST_MARGIN = 0.10
N_PERM = 10000
SEED = 42
Key = tuple[str, bool]  # (verifier label, metadata)
Runs = dict[tuple[str, str, bool], list[dict[str, Any]]]  # (label, condition, metadata) -> records

NOISE_SEEDS = 5
ZZZ: Key = ("arm3", True)  # D29: the family is keyed at metadata on
ZZZ_OFF: Key = ("arm3", False)
VALID: Key = ("arm3@validity", True)
# Expected configurations (all at metadata on, plus EXPECTED_META_OFF): a missing one is reported, never skipped.
# 30_code/scripts/run_dev_pilot_v2.sh runs exactly these; tests/unit/test_prereg.py checks the two agree.
EXPECTED_LABELS = ["arm3", "arm3@validity", "arm3@tax", "arm3@validity@tax", "arm3@support-p1", "arm3@support-p2",
                   "arm3_reflect", "arm4_100n", "arm3@x", "reg_oracle", "reg_real", "reg_real_llm",
                   *[f"{lev}_s{k}" for lev in NOISE_LEVELS for k in range(NOISE_SEEDS)]]
EXPECTED_CONDS = ["C", "S-swap", "S-both", "J", "A", "O"]
EXPECTED_META_OFF = [(lab, c) for lab in ("arm3", "arm3@validity") for c in ("C", "S-swap", "S-both", "J", "A")]
EXPLORATORY_CONTRASTS: dict[str, tuple[Key, Key]] = {
    "cross_model": (ZZZ, ("arm3@x", True)),
    "reflect": (ZZZ, ("arm3_reflect", True)),
    "taxonomy_on_support": (ZZZ, ("arm3@tax", True)),
    "taxonomy_on_validity": (VALID, ("arm3@validity@tax", True)),
    "metadata_validity": (("arm3@validity", False), VALID),
    "reg_oracle": (ZZZ, ("reg_oracle", True)),
    **{lev: (ZZZ, (lev, True)) for lev in NOISE_LEVELS},  # seed-averaged (D31)
    "reg_real_llm": (ZZZ, ("reg_real_llm", True)),
    "reg_real_vs_oracle": (("reg_oracle", True), ("reg_real", True)),
}
PARAPHRASES = ["arm3", "arm3@support-p1", "arm3@support-p2"]


def safe(model: str) -> str:
    """Model id -> JSON key without dots (numbers.py splits paths on dots)."""
    return re.sub(r"[^A-Za-z0-9-]", "_", model)


def ckey(c: str, m: bool) -> str:
    return f"{c}{'+meta' if m else ''}"


def canon(label: str) -> str:
    """Cross-model verifier labels carry the other model's id; one key for all."""
    return re.sub(r"@x:.*$", "@x", label)


# ---------------------------------------------------------------------------------------------
# Rates with checked cluster-bootstrap intervals
# ---------------------------------------------------------------------------------------------
def rate(rows: list[tuple[str, float]]) -> dict[str, Any]:
    """Share of 1s with a cluster-bootstrap CI only when allowed (>= 10 clusters, not degenerate).

    ``display`` is what the manuscript prints: a whole percentage, or k/n with a dagger for a sparse
    cell (n < 5, < 3 clusters, or a degenerate interval).
    """
    n, k = len(rows), sum(v for _, v in rows)  # k is fractional for seed-averaged registry cells
    clusters = len({c for c, _ in rows})
    if n == 0:
        return {"point_estimate": None, "ci_lower": None, "ci_upper": None, "ci_note": "no events",
                "event_count": 0, "total_opportunities": 0, "n_clusters": 0, "is_sparse": True, "display": None}
    p = k / n
    ci, note = cluster_bootstrap_ci_checked([{"c": c, "v": v} for c, v in rows], "c",
                                            lambda rs: sum(r["v"] for r in rs) / len(rs))
    degenerate = (ci is None and note is not None and "degenerate" in note) or (ci is None and p in (0.0, 1.0))
    sparse = n < 5 or clusters < 3 or degenerate
    return {"point_estimate": p, "ci_lower": ci.ci_lower if ci else None, "ci_upper": ci.ci_upper if ci else None,
            "ci_note": (f"CI suppressed: {note}" if ci is None else None), "event_count": k,
            "total_opportunities": n, "n_clusters": clusters, "is_sparse": sparse,
            "display": f"{k:g}/{n}†" if sparse else f"{round(100 * p)}%"}


# ---------------------------------------------------------------------------------------------
# Per-case records
# ---------------------------------------------------------------------------------------------
class Data:
    """Events and clean-condition flags, indexed by model."""

    def __init__(self) -> None:
        self.ev: dict[tuple[str, str, str, bool], list[dict[str, Any]]] = {}  # (model,label,cond,meta)
        self.fp: dict[tuple[str, str, bool], list[dict[str, Any]]] = {}  # (model,label,meta) on C
        self.commit_src: dict[tuple[str, str, bool], list[dict[str, Any]]] = {}  # (model,cond,meta)
        self.gen_n: dict[str, list[dict[str, Any]]] = {}  # model -> N records
        self.n_records: dict[tuple[str, str, str, bool], int] = {}
        self.invalid: dict[tuple[str, str, str, bool], dict[str, int]] = {}  # D30, per model x config x cond
        self.models: list[str] = []

    @classmethod
    def build(cls, runs_by_model: dict[str, Runs]) -> "Data":
        d = cls()
        d.models = sorted(runs_by_model)
        for m in d.models:
            for (lab, cond, meta), recs in sorted(runs_by_model[m].items()):
                d.n_records[(m, lab, cond, meta)] = len(recs)
                d.invalid[(m, lab, cond, meta)] = {
                    "n": len(recs),
                    "verifier_invalid": sum((r.get("raw", {}).get("verifier") or {}).get("verdict") == "INVALID" for r in recs),
                    "generator_invalid": sum(bool(r.get("invalid_output")) for r in recs)}
                if cond == "C":
                    d.fp[(m, lab, meta)] = [{"cluster": r["cluster_clause_id"], "case": r["case_id"],
                                             "flag": float(_flagged(r)), "vflag": float(_validity_flagged(r))}
                                            for r in recs]
                if cond == "N" and m not in d.gen_n:  # one generator pass per condition (D27)
                    d.gen_n[m] = recs
                if cond in EXPOSURE_CLASS:
                    d.ev[(m, lab, cond, meta)] = exposure_events(recs, cond)
                    d.commit_src.setdefault((m, cond, meta), d.ev[(m, lab, cond, meta)])
            d._average_seeds(m)
        return d

    def _average_seeds(self, m: str) -> None:
        """D31: each registry-noise level is the mean over its seeds (``<level>_s<k>``), per event and per
        condition-C case; the generator output is shared, so the seeds have the same events."""
        for lev in NOISE_LEVELS:
            for (_m, _lab, cond, meta) in sorted({k for k in self.ev if k[0] == m and k[1].startswith(f"{lev}_s")}):
                if (m, lev, cond, meta) in self.ev:
                    continue
                runs = [self.ev[k] for k in self.ev if k[0] == m and k[1].startswith(f"{lev}_s") and k[2:] == (cond, meta)]
                rows = []
                for e in runs[0]:
                    same = [next((x for x in r if x["event"] == e["event"]), None) for r in runs]
                    vals = [x for x in same if x is not None]
                    rows.append({**e, "caught": sum(float(x["caught"]) for x in vals) / len(vals),
                                 "caught_class": sum(float(x["caught_class"]) for x in vals) / len(vals),
                                 "caught_clause": sum(float(x["caught_clause"]) for x in vals) / len(vals),
                                 "n_seeds": len(vals)})
                self.ev[(m, lev, cond, meta)] = rows
            for meta in (False, True):
                fps = [v for (mm, lab, mt), v in self.fp.items() if mm == m and mt == meta and lab.startswith(f"{lev}_s")]
                if fps and (m, lev, meta) not in self.fp:
                    by_case: dict[str, list[tuple[float, float]]] = defaultdict(list)
                    for recs in fps:
                        for r in recs:
                            by_case[r["case"]].append((float(r["flag"]), float(r["vflag"])))
                    self.fp[(m, lev, meta)] = [{**r, "flag": sum(f for f, _ in by_case[r["case"]]) / len(by_case[r["case"]]),
                                                "vflag": sum(v for _, v in by_case[r["case"]]) / len(by_case[r["case"]])}
                                               for r in fps[0]]


def _sens_rows(evs: list[dict[str, Any]], key: str = "caught") -> list[tuple[str, float]]:
    return [(e["cluster"], float(e[key])) for e in evs if e["committed"]]


def _reason_metrics(evs: list[dict[str, Any]]) -> dict[str, Any]:
    """D32 secondaries beside the primary (right clause and right reason): clause-only sensitivity (the D26 catch)
    and wrong-reason catches (committed events whose clause was named with another reason; seed means for noise)."""
    return {"sensitivity_class_only": rate(_sens_rows(evs, "caught_class")),
            "sensitivity_clause_only": rate(_sens_rows(evs, "caught_clause")),
            "wrong_reason_catches": sum(max(0.0, float(e["caught_clause"]) - float(e["caught"]))
                                        for e in evs if e["committed"])}


def _gather(d: Data, models: list[str], label: str, conds: list[str], meta: bool = True) -> list[dict[str, Any]]:
    return [e for m in models for c in conds for e in d.ev.get((m, label, c, meta), [])]


# ---------------------------------------------------------------------------------------------
# Paired contrasts and the family
# ---------------------------------------------------------------------------------------------
def _sens_diffs(d: Data, a: Key, b: Key, models: list[str], conds: list[str]) -> tuple[dict[str, list[float]], list[str]]:
    diffs: dict[str, list[float]] = defaultdict(list)
    missing: list[str] = []
    for m in models:
        for c in conds:
            ea, eb = d.ev.get((m, a[0], c, a[1])), d.ev.get((m, b[0], c, b[1]))
            if ea is None or eb is None:
                missing.append(f"{m}:{c}")
                continue
            amap = {e["event"]: float(e["caught"]) for e in ea if e["committed"]}
            for e in eb:
                if e["committed"] and e["event"] in amap:
                    diffs[e["cluster"]].append(float(e["caught"]) - amap[e["event"]])
    return dict(diffs), missing


def _fpr_diffs(d: Data, a: Key, b: Key, models: list[str]) -> tuple[dict[str, list[float]], list[str]]:
    diffs: dict[str, list[float]] = defaultdict(list)
    missing: list[str] = []
    for m in models:
        fa, fb = d.fp.get((m, a[0], a[1])), d.fp.get((m, b[0], b[1]))
        if fa is None or fb is None:
            missing.append(f"{m}:C")
            continue
        amap = {r["case"]: float(r["flag"]) for r in fa}
        for r in fb:
            if r["case"] in amap:
                diffs[r["cluster"]].append(float(r["flag"]) - amap[r["case"]])
    return dict(diffs), missing


def contrast(d: Data, a: Key, b: Key, models: list[str], conds: list[str]) -> dict[str, Any]:
    """b minus a on committed events (sensitivity) and on condition-C cases (FPR), by cluster."""
    sd, miss = _sens_diffs(d, a, b, models, conds)
    fd, fmiss = _fpr_diffs(d, a, b, models)
    out: dict[str, Any] = {"baseline": a[0] + ("+meta" if a[1] else ""), "config": b[0] + ("+meta" if b[1] else ""),
                           "conds": conds, "models_requested": models, "missing": miss + fmiss,
                           "status": "ok" if not (miss or fmiss) else "partial"}
    out["models_used"] = sorted({m for m in models if f"{m}:C" not in fmiss or any(
        f"{m}:{c}" not in miss for c in conds)})
    if not sd:
        out.update(status="not_available", reason="no paired committed events for this contrast")
        return out
    out["n_events"] = sum(len(v) for v in sd.values())
    out["n_clusters"] = len(sd)
    if fd:
        cp = coprimary_improvement(sd, fd, sens_alpha=1.0, fpr_margin=FPR_MARGIN, alpha=ALPHA,
                                   n_perm=N_PERM, seed=SEED)
        out.update(sens_diff=cp.sens_diff, sens_p=cp.sens_p, fpr_diff=cp.fpr_diff,
                   fpr_noninferior_p=cp.fpr_noninferior_p, fpr_noninferior=cp.fpr_noninferior,
                   n_clusters_fpr=len(fd))
    else:
        perm = cluster_permutation_test(sd, N_PERM, SEED)
        out.update(sens_diff=perm.observed, sens_p=perm.p, fpr_noninferior=None,
                   fpr_note="no paired condition-C cases: co-primary FPR rule not assessable")
    return out


def _p1(d: Data, models: list[str]) -> dict[str, Any]:
    evs = _gather(d, models, ZZZ[0], PRIMARY_CONDITIONS, ZZZ[1])
    rows = _sens_rows(evs)
    miss = [f"{m}:{c}" for m in models for c in PRIMARY_CONDITIONS if (m, *ZZZ[:1], c, ZZZ[1]) not in d.ev]
    if not rows:
        return {"status": "not_available", "reason": "no committed events for 000", "missing": miss}
    by_cluster: dict[str, list[float]] = defaultdict(list)
    for c, v in rows:
        by_cluster[c].append(v)
    t = cluster_one_sample_test(dict(by_cluster), P1_NULL, "less", N_PERM, SEED)
    ci, note = cluster_bootstrap_ci_checked([{"c": c, "v": v} for c, v in rows], "c",
                                            lambda rs: sum(r["v"] for r in rs) / len(rs))
    return {"status": "ok" if not miss else "partial", "missing": miss, "null": P1_NULL, "alternative": "less",
            "observed": t.observed, "p": t.p, "exact": t.exact, "n_clusters": t.n_clusters, "n_events": len(rows),
            "sensitivity_event_weighted": rate(rows), "ci_lower": ci.ci_lower if ci else None,
            "ci_upper": ci.ci_upper if ci else None, "ci_note": f"CI suppressed: {note}" if ci is None else None}


def _p4_extra(d: Data, models: list[str]) -> dict[str, Any]:
    sd, _ = _sens_diffs(d, ZZZ, ("arm4_100n", True), models, PRIMARY_CONDITIONS)
    if not sd:
        return {}
    t = tost_equivalence(sd, TOST_MARGIN, ALPHA, N_PERM, SEED)
    up = cluster_one_sample_test(sd, TOST_MARGIN, "less", N_PERM, SEED)
    return {"tost": {"p": t.p, "equivalent": t.equivalent, "margin": t.margin, "observed": t.observed,
                     "conclusion": t.conclusion}, "p_upper": up.p}


def family(d: Data, models: list[str], correct: bool = True) -> dict[str, Any]:
    """P1-P5. ``correct``: Holm over five (pooled, confirmatory) or raw p per model (secondary)."""
    tests: dict[str, dict[str, Any]] = {
        "P1": _p1(d, models),
        "P2": contrast(d, ZZZ, VALID, models, PRIMARY_CONDITIONS),
        "P3": contrast(d, ZZZ_OFF, ZZZ, models, PRIMARY_CONDITIONS),
        "P4": contrast(d, ZZZ, ("arm4_100n", True), models, PRIMARY_CONDITIONS),
        "P5": contrast(d, ZZZ, ("reg_real", True), models, ["J", "S-both"]),
    }
    tests["P4"].update(_p4_extra(d, models))
    names = {"P1": "000 sensitivity < 0.30 (metadata on)", "P2": "000-validity vs 000",
             "P3": "verifier metadata on vs off (000, generator fixed)", "P4": "100-neutral vs 000 (TOST +-10 points)",
             "P5": "reg-real vs 000 on F2+F3 (J, S-both)"}
    raw: dict[str, float] = {}
    for k, t in tests.items():
        t["hypothesis"] = names[k]
        p = t.get("p") if k == "P1" else t.get("p_upper") if k == "P4" else t.get("sens_p")
        raw[k] = float(p) if p is not None and t["status"] != "not_available" else 1.0
        t["p_for_family"] = raw[k]
    holm = holm_family(raw, ALPHA)
    for k, t in tests.items():
        t["p_holm"] = holm[k]["p_holm"] if correct else raw[k]
        sig = t["status"] != "not_available" and t["p_holm"] < ALPHA
        if t["status"] == "not_available":  # in the family at p = 1, but nothing to print
            t["p_holm"], t["decision"], t["decision_note"] = None, None, "not available"
        elif k in ("P1", "P4"):
            t["decision"] = "supported" if sig else "not supported"
        else:
            t["sens_significant"] = bool(sig and t["sens_diff"] > 0)
            ni = t.get("fpr_noninferior")
            t["improves"] = bool(t["sens_significant"] and ni) if ni is not None else None
            t["decision"] = ("supported" if t["improves"] else "not supported") if ni is not None else "not assessable"
    clusters: set[str] = set()
    for m in models:
        clusters |= {e["cluster"] for key, evs in d.ev.items() if key[0] == m for e in evs}
    return {"correction": "Holm over 5 (pooled)" if correct else "none (secondary, per model)", "alpha": ALPHA,
            "n_clusters": len(clusters) or None, **tests}


# ---------------------------------------------------------------------------------------------
# One block (a model, or all models pooled)
# ---------------------------------------------------------------------------------------------
def block(d: Data, models: list[str]) -> dict[str, Any]:
    sub = {k: v for k, v in d.ev.items() if k[0] in models}
    grouped: dict[tuple[str, str, bool], list[dict[str, Any]]] = defaultdict(list)
    for (_, lab, cond, meta), evs in sorted(sub.items()):
        grouped[(lab, cond, meta)].extend(evs)
    out: dict[str, Any] = {"models": models, "commit": {}, "cells": {}, "pooled": {}, "fpr_clean": {},
                           "fpr_validity_reason_clean": {},
                           "registry_curve": {}, "exploratory": {"label": "EXPLORATORY: no confirmatory language"}}
    commit_src: dict[tuple[str, bool], list[dict[str, Any]]] = defaultdict(list)
    for (m, cond, meta), evs in sorted(d.commit_src.items()):
        if m in models:
            commit_src[(cond, meta)].extend(evs)
    for (cond, meta), evs in commit_src.items():
        out["commit"][ckey(cond, meta)] = {
            "class": EXPOSURE_CLASS[cond], "label": "EXPLORATORY",
            "primary": rate([(e["cluster"], float(e["committed"])) for e in evs]),
            "citation": rate([(e["cluster"], float(e["cited"])) for e in evs])}
    for (lab, cond, meta), evs in grouped.items():
        cell: dict[str, Any] = {"class": EXPOSURE_CLASS[cond], "sensitivity": rate(_sens_rows(evs)),
                                **_reason_metrics(evs),
                                "survival": rate([(e["cluster"], float(e["committed"] and not e["caught"]))
                                                  for e in evs])}
        if cond == "O":  # F4 completeness: caught by the verifier or by the checklist
            cell["sensitivity_with_completeness"] = rate(
                [(e["cluster"], float(e["caught"] or e["comp"])) for e in evs if e["committed"]])
        out["cells"][f"{lab}|{ckey(cond, meta)}"] = cell
    labels = sorted({(lab, meta) for (lab, _, meta) in grouped})
    for lab, meta in labels:
        have = [c for c in PRIMARY_CONDITIONS if (lab, c, meta) in grouped]
        if have:
            evs = [e for c in have for e in grouped[(lab, c, meta)]]
            out["pooled"][lab + ("+meta" if meta else "")] = {
                "conditions": have, "missing_conditions": [c for c in PRIMARY_CONDITIONS if c not in have],
                "sensitivity": rate(_sens_rows(evs)), **_reason_metrics(evs)}
    fgrouped: dict[tuple[str, bool], list[dict[str, Any]]] = defaultdict(list)
    for (m, lab, meta), recs in sorted(d.fp.items()):
        if m in models:
            fgrouped[(lab, meta)].extend(recs)
    for (lab, meta), recs in fgrouped.items():
        out["fpr_clean"][f"{lab}|{ckey('C', meta)}"] = rate([(r["cluster"], float(r["flag"])) for r in recs])
        out["fpr_validity_reason_clean"][f"{lab}|{ckey('C', meta)}"] = rate([(r["cluster"], r["vflag"]) for r in recs])
    for cond in ("S-swap", "S-both", "J"):
        key = ckey(cond, True)
        row = {lab: out["cells"][f"{lab}|{key}"]["sensitivity"] for lab in
               ("reg_oracle", "reg_real", *NOISE_LEVELS, "reg_real_llm") if f"{lab}|{key}" in out["cells"]}
        if row:
            out["registry_curve"][cond] = row
        for lev in NOISE_LEVELS:  # per-seed spread of each noise level (D31)
            seed_pts = [out["cells"][f"{lev}_s{k}|{key}"]["sensitivity"]["point_estimate"] for k in range(NOISE_SEEDS)
                        if f"{lev}_s{k}|{key}" in out["cells"]]
            seed_pts = [p for p in seed_pts if p is not None]
            if seed_pts:
                out["registry_curve"].setdefault(f"{cond}_seeds", {})[lev] = {
                    "min": min(seed_pts), "max": max(seed_pts), "n_seeds": len(seed_pts)}
    out["invalid_outputs"] = {"label": "D30: invalid replies per model x configuration (verifier invalid = miss and false alarm)",
                              "rows": {f"{m}|{lab}|{ckey(c, mt)}": v for (m, lab, c, mt), v in sorted(d.invalid.items())
                                       if m in models and (v["verifier_invalid"] or v["generator_invalid"])},
                              "verifier_invalid": sum(v["verifier_invalid"] for (m, *_), v in d.invalid.items() if m in models),
                              "generator_invalid_records": sum(v["generator_invalid"] for (m, *_), v in d.invalid.items() if m in models),
                              "records": sum(v["n"] for (m, *_), v in d.invalid.items() if m in models)}
    spread: dict[str, Any] = {}
    for cond in EXPOSURE_CLASS:
        key = ckey(cond, True)
        pts = {lab: out["cells"][f"{lab}|{key}"]["sensitivity"]["point_estimate"] for lab in PARAPHRASES
               if f"{lab}|{key}" in out["cells"] and out["cells"][f"{lab}|{key}"]["sensitivity"]["point_estimate"] is not None}
        if len(pts) > 1:
            spread[cond] = {"points": pts, "range": max(pts.values()) - min(pts.values())}
    out["paraphrase_spread"] = {"label": "EXPLORATORY", "by_condition": spread,
                                "max_range": max((v["range"] for v in spread.values()), default=None)}
    gen = [r for m in models for r in d.gen_n.get(m, [])]
    out["generator_accuracy_N"] = {"label": "EXPLORATORY", **rate([(r["cluster_clause_id"], float(r["is_correct"]))
                                                                     for r in gen])}
    out["exploratory"]["contrasts"] = {name: contrast(d, a, b, models, PRIMARY_CONDITIONS)
                                       for name, (a, b) in EXPLORATORY_CONTRASTS.items()}
    return out


def arm5(per_model: dict[str, dict[str, Any]], verifier: str = "arm3") -> dict[str, Any]:
    """Arm 5 after a FLAG from ``verifier`` (000, or reg-oracle: a correct critique), metadata on, summed over
    conditions and models (outcome level). Exploratory."""
    tot = {"n": 0, "flagged": 0, "recovered": 0, "degraded": 0, "usable": 0}
    for rec in per_model.values():
        for key, row in rec.get("recovery", {}).items():
            lab, _, cond = key.partition("|")
            if lab != verifier or not cond.endswith("+meta"):
                continue
            tot["n"] += row["n"]
            tot["flagged"] += row["flagged"]
            tot["recovered"] += row["outcome_recovered"]
            tot["degraded"] += row["outcome_degraded"]
            tot["usable"] += row["outcome_initial_wrong"] + row["outcome_initial_correct"]
    res: dict[str, Any] = {"label": "EXPLORATORY"}
    if not tot["n"]:
        return res
    res |= {"n": tot["n"], "flagged": tot["flagged"],
                           "outcome_recovered": tot["recovered"], "outcome_degraded": tot["degraded"]}
    if tot["usable"]:
        res["outcome_net"] = (tot["recovered"] - tot["degraded"]) / tot["usable"]
    return res


# ---------------------------------------------------------------------------------------------
# Macro specs (numbers.py): names and paths
# ---------------------------------------------------------------------------------------------
MODEL_TAGS = {"QwenSeven": "qwen2.5:7b", "LlamaEight": "llama3.1:8b", "QwenFourteen": "qwen2.5:14b",
              "GemmaMoE": "gemma-4-26b-a4b-it", "FlashLite": "gemini-3.5-flash-lite"}
# Every tag is read at metadata on (D29), except ZZZMetaOff (P3's comparator).
CFG_TAGS = {"ZZZ": "arm3", "ZZZValid": "arm3@validity", "ZZZReflect": "arm3_reflect", "ZZZTax": "arm3@tax",
            "ZZZValidTax": "arm3@validity@tax", "HundredNeutral": "arm4_100n", "CrossModel": "arm3@x",
            "RegOracle": "reg_oracle", "RegReal": "reg_real", "RegNoisyTwentyFive": "reg_noisy25",
            "RegNoisyFifty": "reg_noisy50", "RegSpuriousTen": "reg_spurious10", "RegRealLLM": "reg_real_llm"}
CELL_CFGS = ["ZZZ", "ZZZValid", "HundredNeutral", "RegOracle", "RegReal", "RegRealLLM"]
COND_TAGS = {"SSwap": "S-swap", "SBoth": "S-both", "J": "J", "A": "A", "O": "O"}
P_TAGS = {"One": "P1", "Two": "P2", "Three": "P3", "Four": "P4", "Five": "P5"}
# Macros whose source is not run data: they cannot come from results_v2.json.
FILES_SPEC: dict[str, dict[str, Any]] = {
    "RecallDense": {"file": "50_analysis/results/rd4_retrieval_selection/dev_recall.json",
                    "path": "candidates.dense.mean_recall", "fmt": ".1f", "scale": 100},
    "RecallHybrid": {"file": "50_analysis/results/rd4_retrieval_selection/dev_recall.json",
                     "path": "candidates.hybrid.mean_recall", "fmt": ".1f", "scale": 100},
    "GateZeroMisleadDense": {"file": "50_analysis/results/gate0_audit.json",
                             "path": "metrics.misleading_percentage", "fmt": ".1f"},
    "GateZeroMisleadHybrid": {"file": "50_analysis/results/gate0_rerun_rd4_2026-09-30/gate0_audit.json",
                              "path": "metrics.misleading_percentage", "fmt": ".1f"},
    "RegRealNodes": {"file": "50_analysis/results/registry_v2/compare.json", "path": "nodes.registry"},
    "RegRealEdges": {"file": "50_analysis/results/registry_v2/compare.json", "path": "edges_pair.registry"},
    "RegRealNodeRecall": {"file": "50_analysis/results/registry_v2/compare.json",
                          "path": "nodes.recall", "fmt": ".0f", "scale": 100},
    "RegRealEdgeRecall": {"file": "50_analysis/results/registry_v2/compare.json",
                          "path": "edges_pair.recall", "fmt": ".0f", "scale": 100},
    "RegRealTypedEdgeRecall": {"file": "50_analysis/results/registry_v2/compare.json",
                               "path": "edges_typed.recall", "fmt": ".0f", "scale": 100},
    "RegRealDocRecall": {"file": "50_analysis/results/registry_v2/compare.json",
                         "path": "superseded_documents.recall", "fmt": ".0f", "scale": 100},
}
NOT_RUN_DATA = {  # macro -> why results_v2.json does not carry it
    **{m: "source is the corpus manifest or supersession graph, not run data (counts derived from the file)"
       for m in ("NCorpusDocs", "NCorpusPages", "NCorpusChunks", "NCorpusJurisdictions", "NGraphNodes",
                 "NGraphEdges", "NSupersededDocs")},
    "NDevCases": "dev split count; the --cases file of a test run is the test split",
    "NDevClusters": "dev split count; the --cases file of a test run is the test split",
    "NFabDocs": "2026-09 provenance audit, a data file",
    "NFabExcluded": "2026-09 provenance audit, a data file",
    **{m: "20_method/annotation/kappa.json does not exist yet (human annotation, U-tasks)"
       for m in ("KappaLabels", "KappaClauses", "KappaEdges", "NAnnotatedCases", "NLabelsChanged")},
    "RecallHybridTest": "retrieval_test.json needs the test split, which is sealed",
    "BaseAlwaysApprove": "baselines_v2/baselines.json: test re-run not done",
    "BaseHeuristic": "baselines_v2/baselines.json: test re-run not done",
    "NModelCalls": "no call-count manifest exists; calls are not counted in the exposure index",
}


def build_spec() -> dict[str, Any]:
    """Macro -> path (+ format) over results_v2.json."""
    sp: dict[str, Any] = {}
    blocks = {tag: f"exposure.{safe(m)}" for tag, m in MODEL_TAGS.items()} | {"Pooled": "exposure.pooled"}
    for tag, base in blocks.items():
        for ct, lab in [*CFG_TAGS.items(), ("ZZZMetaOff", "arm3")]:
            on = "" if ct == "ZZZMetaOff" else "+meta"
            sp[f"Sens{tag}{ct}"] = f"{base}.pooled.{lab}{on}.sensitivity.display"
            sp[f"FPR{tag}{ct}"] = f"{base}.fpr_clean.{lab}|C{on}.display"
        sp[f"AccN{tag}"] = f"{base}.generator_accuracy_N.display"
        for cn, cond in COND_TAGS.items():
            sp[f"Commit{tag}{cn}"] = f"{base}.commit.{cond}+meta.primary.display"
            sp[f"Cite{tag}{cn}"] = f"{base}.commit.{cond}+meta.citation.display"
    for ct in CELL_CFGS:
        lab = CFG_TAGS[ct]
        for cn, cond in COND_TAGS.items():
            sp[f"SensPooled{ct}{cn}"] = f"exposure.pooled.cells.{lab}|{cond}+meta.sensitivity.display"
        sp[f"SensClassOnlyPooled{ct}"] = f"exposure.pooled.pooled.{lab}+meta.sensitivity_class_only.display"
        sp[f"SensClauseOnlyPooled{ct}"] = f"exposure.pooled.pooled.{lab}+meta.sensitivity_clause_only.display"
        sp[f"WrongReasonPooled{ct}"] = {"path": f"exposure.pooled.pooled.{lab}+meta.wrong_reason_catches", "fmt": ".0f"}
        sp[f"FPRValidityReasonPooled{ct}"] = f"exposure.pooled.fpr_validity_reason_clean.{lab}|C+meta.display"
    for cn, cond in COND_TAGS.items():
        sp[f"NEvents{cn}"] = f"counts.events.{cond}+meta"
    sp["NCasesC"] = "counts.cases_c"
    sp["NTestCases"] = "counts.test_cases"
    sp["NTestClusters"] = "counts.test_clusters"
    sp["POneSens"] = {"path": "family.P1.observed", "fmt": ".0f", "scale": 100}
    sp["POneP"] = {"path": "family.P1.p", "fmt": ".3f"}
    sp["POnePHolm"] = {"path": "family.P1.p_holm", "fmt": ".3f"}
    sp["POneDecision"] = "family.P1.decision"
    for tag, p in P_TAGS.items():
        if p == "P1":
            continue
        sp[f"P{tag}SensDiff"] = {"path": f"family.{p}.sens_diff", "fmt": ".1f", "scale": 100}
        sp[f"P{tag}FPRDiff"] = {"path": f"family.{p}.fpr_diff", "fmt": ".1f", "scale": 100}
        sp[f"P{tag}P"] = {"path": f"family.{p}.sens_p", "fmt": ".3f"}
        sp[f"P{tag}NIp"] = {"path": f"family.{p}.fpr_noninferior_p", "fmt": ".3f"}
        sp[f"P{tag}PHolm"] = {"path": f"family.{p}.p_holm", "fmt": ".3f"}
        sp[f"P{tag}Decision"] = f"family.{p}.decision"
    sp["PFourTOSTp"] = {"path": "family.P4.tost.p", "fmt": ".3f"}
    sp["NFamilyClusters"] = "family.n_clusters"
    for name, key in (("N", "n"), ("Flagged", "flagged"), ("Recovered", "outcome_recovered"),
                      ("Degraded", "outcome_degraded")):
        sp[f"ArmFive{name}"] = f"arm5.{key}"
        sp[f"ArmFiveOracle{name}"] = f"arm5_reg_oracle.{key}"
    sp["ArmFiveNet"] = {"path": "arm5.outcome_net", "fmt": ".0f", "scale": 100}
    sp["ArmFiveOracleNet"] = {"path": "arm5_reg_oracle.outcome_net", "fmt": ".0f", "scale": 100}
    sp["NInvalidVerifier"] = "exposure.pooled.invalid_outputs.verifier_invalid"
    sp["ParaRange"] = {"path": "exposure.pooled.paraphrase_spread.max_range", "fmt": ".0f", "scale": 100}
    return sp


def _walk(results: dict[str, Any], path: str) -> tuple[Any, str | None]:
    cur: Any = results
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None, part
        cur = cur[part]
    return cur, None


def macro_report(results: dict[str, Any], spec: dict[str, Any], macros_md: Path | None) -> dict[str, Any]:
    """Which macros this results file can fill; every other macro is listed with a reason."""
    na: list[dict[str, str]] = []
    emitted = 0
    for name, item in spec.items():
        path = item if isinstance(item, str) else item["path"]
        val, miss = _walk(results, path)
        if miss is not None:
            na.append({"macro": name, "path": path, "reason": f"no data at {miss!r} "
                       "(configuration not run, incomplete, or not applicable to this cases file)"})
        elif val is None or isinstance(val, dict | list):
            na.append({"macro": name, "path": path, "reason": "value is null (nothing to estimate)"})
        else:
            emitted += 1
    for name, why in NOT_RUN_DATA.items():
        na.append({"macro": name, "path": "", "reason": why})
    known = set(spec) | set(NOT_RUN_DATA) | set(FILES_SPEC)
    unmapped: list[str] = []
    if macros_md is not None and macros_md.exists():
        names = set(re.findall(r"^\| `\\([A-Za-z]+)` \|", macros_md.read_text(encoding="utf-8"), re.M))
        unmapped = sorted(names - known)
        na += [{"macro": n, "path": "", "reason": "in MACROS.md but mapped nowhere"} for n in unmapped]
    return {"emitted": emitted, "not_available_count": len(na), "from_saved_files": len(FILES_SPEC),
            "unmapped_in_macros_md": unmapped, "not_available": na}


# ---------------------------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------------------------
def analyse_all(runs_by_model: dict[str, Runs], cases: list[dict[str, Any]], cases_name: str,
                spec: dict[str, Any] | None = None, macros_md: Path | None = None) -> dict[str, Any]:
    d = Data.build(runs_by_model)
    models = d.models
    clusters = sorted({str(c.get("cluster_id")) for c in cases})
    res: dict[str, Any] = {
        "preregistration": "20_method/PREREGISTRATION_v2.md sections 3-4",
        "status": "confirmatory family = results.family (pooled, Holm over 5); everything under "
                  "`exploratory`, per-model `family_secondary` and `arm5` is not confirmatory",
        "models": models, "model_keys": {m: safe(m) for m in models},
        "cases": {"file": cases_name, "n_cases": len(cases), "n_clusters": len(clusters)},
        "counts": {"events": {}},
    }
    if "test" in Path(cases_name).name:
        res["counts"].update(test_cases=len(cases), test_clusters=len(clusters))
    exposure: dict[str, Any] = {}
    per_model: dict[str, dict[str, Any]] = {}
    for m in models:
        b = block(d, [m])
        b["family_secondary"] = family(d, [m], correct=False)
        try:
            ex = analyse_exposure(runs_by_model[m], {})
            b["exploratory"].update(recovery=ex["recovery"], flag_rates=ex["flag_rates"],
                                    mcnemar=ex["contrasts"]["exploratory"])
        except Exception as e:  # noqa: BLE001  (partial pilot data: say so, do not crash)
            b["exploratory"]["legacy_error"] = f"{type(e).__name__}: {e}"
        b["missing_configurations"] = missing(d, m)
        per_model[m] = b
        exposure[safe(m)] = b
    pooled = block(d, models)
    pooled["missing_configurations"] = sorted({f"{m}:{x}" for m in models for x in missing(d, m)})
    exposure["pooled"] = pooled
    res["exposure"] = exposure
    res["family"] = family(d, models, correct=True)
    res["arm5"] = arm5({m: per_model[m]["exploratory"] for m in models})
    res["arm5_reg_oracle"] = arm5({m: per_model[m]["exploratory"] for m in models}, "reg_oracle")
    for cond in EXPOSURE_CLASS:
        key = ckey(cond, True)
        ns = [b["commit"][key]["primary"]["total_opportunities"] for b in per_model.values() if key in b["commit"]]
        if ns:
            res["counts"]["events"][key] = max(ns)
    ns = [b["fpr_clean"]["arm3|C+meta"]["total_opportunities"] for b in per_model.values() if "arm3|C+meta" in b["fpr_clean"]]
    if ns:
        res["counts"]["cases_c"] = max(ns)
    res["incomplete_generator_runs"] = [
        f"{m}:{lab}|{ckey(c, meta)}: {n}/{len(cases)} cases" for (m, lab, c, meta), n in sorted(d.n_records.items())
        if c in ("N", "C") and n < len(cases)]
    mr = macro_report(res, spec if spec is not None else build_spec(), macros_md)
    res["macro_coverage"] = {k: v for k, v in mr.items() if k != "not_available"}
    res["not_available"] = mr["not_available"]
    return res


def missing(d: Data, m: str) -> list[str]:
    out = [f"{lab}|{ckey(c, True)}" for lab in EXPECTED_LABELS for c in EXPECTED_CONDS
           if (m, lab, c, True) not in d.ev and not (c == "C" and (m, lab, True) in d.fp)]
    out += [f"{lab}|{ckey(c, False)}" for lab, c in EXPECTED_META_OFF
            if (m, lab, c, False) not in d.ev and not (c == "C" and (m, lab, False) in d.fp)]
    if m not in d.gen_n:
        out.append("generator|N")
    return out


def load_runs(index_paths: list[Path]) -> dict[str, Runs]:
    runs: dict[str, Runs] = {}
    for ip in index_paths:
        if not ip.exists():  # a pilot still running has no index yet: say so, analyse what exists
            print(f"index not found, skipped: {ip}", file=sys.stderr)
            continue
        for model in sorted({r["model"] for r in json.loads(ip.read_text(encoding="utf-8"))} - {"none"}):
            for (lab, cond, meta), recs in load_exposure(ip, model).items():
                runs.setdefault(model, {})[(canon(lab), cond, meta)] = recs  # later index wins
    return runs


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else None)
    ap.add_argument("--index", action="append", default=[], help="exposure_index.json (repeatable)")
    ap.add_argument("--cases", help="cases JSON the runs were made on")
    ap.add_argument("--out", help="output directory for results_v2.json")
    ap.add_argument("--spec", default="60_paper_drafts/paper_v2/numbers_spec.json")
    ap.add_argument("--macros-md", default="60_paper_drafts/paper_v2/MACROS.md")
    ap.add_argument("--write-spec", metavar="DIR", help="write numbers_spec.json and numbers_spec_files.json")
    a = ap.parse_args(argv)
    if a.write_spec:
        out = resolve(a.write_spec)
        out.mkdir(parents=True, exist_ok=True)
        for name, sp in (("numbers_spec.json", build_spec()), ("numbers_spec_files.json", FILES_SPEC)):
            _dump(out / name, sp)
        print(f"wrote {out}/numbers_spec.json ({len(build_spec())} macros) and numbers_spec_files.json")
        return
    if not (a.index and a.cases and a.out):
        ap.error("--index, --cases and --out are required")
    cases_path = resolve(a.cases)
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    spec_path = resolve(a.spec)
    spec = json.loads(spec_path.read_text(encoding="utf-8")) if spec_path.exists() else None
    res = analyse_all(load_runs([resolve(i) for i in a.index]), cases, display(cases_path), spec, resolve(a.macros_md))
    res["cases"]["sha256"] = hashlib.sha256(cases_path.read_bytes()).hexdigest()
    res["indexes"] = [display(resolve(i)) for i in a.index]
    out_dir = resolve(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    _dump(out_dir / "results_v2.json", res)
    cov = res["macro_coverage"]
    print(f"wrote {out_dir}/results_v2.json: models={res['models']} macros emitted={cov['emitted']} "
          f"not available={cov['not_available_count']}")


def _dump(path: Path, obj: Any) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(obj, indent=1, default=str) + "\n")

if __name__ == "__main__":
    main()
