"""Paper analysis: every table and figure is computed from saved run records.

Inputs are the matrix index (`50_analysis/results/runs/matrix_index.json`), each run's `evaluations.json`
(per-case classification plus the arm's raw output) and `scorecard.json`, the sealed case
file, the corpus manifest, and the Gate 0 audit. Nothing is defaulted: an arm or class with no
data is reported as missing, and sparse cells (n < 5 or < 3 clusters) are suppressed with
their raw counts.

Hypotheses are the locked text of 20_method/RESEARCH-CHARTER.md §4 (H1-H4). Confidence intervals are
95% clause-clustered bootstraps (1,000 replicates); paired contrasts resample clusters of
per-case differences. Seeds are pooled within clusters.

Usage: python -m suryabench.analysis.paper --cases 40_data/benchmark/test_cases_100.json --model <id>

Controlled-exposure matrix (Paper A redesign, RD7): add ``--exposure-index <dir>/exposure_index.json``
to analyse a run of ``30_code/scripts/run_exposure_matrix.py`` instead (tables and results.json under
``--out``). Per planted fault class and verifier configuration it reports commit rate, sensitivity,
specificity and survival with clustered CIs; exact McNemar tests on paired catches (EXPLORATORY only: the preregistered family, a cluster-level
permutation analysis with Holm and the co-primary false-positive rule, is `suryabench.analysis.prereg`);
and Arm 5 recovery and degradation rates.

Paths given on the command line or recorded in a matrix index may use the pre-restructure layout
(`results/...`, `benchmark/...`); they are mapped by `suryabench.paths.resolve`.
"""

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "suryabench"  # deterministic SVG ids
import matplotlib.pyplot as plt  # noqa: E402

from suryabench.analysis.stats import cluster_bootstrap_ci, mcnemar_test  # noqa: E402
from suryabench.cases.schema import BenchmarkCase  # noqa: E402
from suryabench.eval.evaluators import MetricWithCI, build_metric_with_ci  # noqa: E402
from suryabench.eval.failure_classifier import NFO_PROPERTY_CLASS, VALIDITY_REASONS  # noqa: E402
from suryabench.paths import (  # noqa: E402
    BENCHMARK_DIR,
    CORPUS_DIR,
    RESULTS_DIR,
    display,
    resolve,
    same_file,
)

VERIFIER_ARMS = ["arm3", "arm3_reflect", "arm4_100", "arm4_110", "arm4_111"]
GENERATOR_ARMS = ["arm0", "arm1", "arm2", "arm2o"]
LABEL = {"arm0": "Arm 0 (rules)", "arm1": "Arm 1 (RAG)", "arm2": "Arm 2 (agent+tools)",
         "arm2o": "Arm 2-O (oracle, diagnostic)", "arm3": "Arm 3 (000)", "arm3_reflect": "Arm 3-Reflect (000, 2-pass)",
         "arm4_100": "Arm 4 (100)", "arm4_110": "Arm 4 (110)", "arm4_111": "Arm 4 (111)"}
CLASSES = ["F2", "F3", "F4", "F5", "F6", "F9"]
DETECTED_ONLY = ["F1", "F7"]  # no seeded events: classifier-detected faults only
TAU = 0.025  # locked oracle-gap margin (20_method/ORACLE_INTERPRETATION_RULE.md)


# ==============================================================================
# Loading
# ==============================================================================
def load(index_path: Path, cases_path: Path, model: str) -> dict[str, list[dict[str, Any]]]:
    """arm -> per-case records pooled over seeds (arm0 is model-free)."""
    index = json.loads(index_path.read_text(encoding="utf-8"))
    runs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in index:
        if not same_file(row["cases"], cases_path) or row["model"] not in {model, "none"}:
            continue
        run_dir = index_path.parent / row["run_id"]
        for rec in json.loads((run_dir / "evaluations.json").read_text(encoding="utf-8")):
            rec["seed"] = row["seed"]
            rec["run_id"] = row["run_id"]
            runs[row["arm"]].append(rec)
    return dict(runs)


def load_cases(cases_path: Path) -> dict[str, BenchmarkCase]:
    return {c["case_id"]: BenchmarkCase.model_validate(c) for c in json.loads(cases_path.read_text(encoding="utf-8"))}


def run_ids(index_path: Path, cases_path: Path, model: str) -> list[str]:
    return [r["run_id"] for r in json.loads(index_path.read_text(encoding="utf-8"))
            if same_file(r["cases"], cases_path) and r["model"] in {model, "none"}]


# ==============================================================================
# Metrics
# ==============================================================================
def metric(records: list[dict[str, Any]], key: str = "v") -> MetricWithCI:
    return build_metric_with_ci([{"cluster_clause_id": r["cluster"], key: r[key]} for r in records], value_key=key)


def _class_of(fe: Any) -> str:
    return str(fe.fault_class.value)


def sensitivity_records(recs: list[dict[str, Any]], cases: dict[str, BenchmarkCase], cls: str) -> list[dict[str, Any]]:
    out = []
    for r in recs:
        for fe in cases[r["case_id"]].fault_events:
            if _class_of(fe) == cls and r["fault_event_committed"].get(fe.fault_event_id):
                out.append({"cluster": r["cluster_clause_id"], "v": float(r["fault_event_matches"].get(fe.fault_event_id, False)),
                            "pair": (r["case_id"], r["seed"], fe.fault_event_id)})
    return out


def specificity_records(recs: list[dict[str, Any]], cases: dict[str, BenchmarkCase], cls: str) -> list[dict[str, Any]]:
    """True negatives over avoided traps of the class and non-fault opportunities of the class."""
    out = []
    for r in recs:
        case = cases[r["case_id"]]
        for fe in case.fault_events:
            if _class_of(fe) == cls and fe.fault_event_id in r["avoided_trap_matches"]:
                out.append({"cluster": r["cluster_clause_id"], "v": float(not r["avoided_trap_matches"][fe.fault_event_id]),
                            "pair": (r["case_id"], r["seed"], fe.fault_event_id)})
        for nfo in case.non_fault_opportunities:
            if NFO_PROPERTY_CLASS.get(nfo.target_property) == cls:
                out.append({"cluster": r["cluster_clause_id"], "v": float(not r["nfo_matches"].get(nfo.opportunity_id, False)),
                            "pair": (r["case_id"], r["seed"], nfo.opportunity_id)})
    return out


def detected_records(recs: list[dict[str, Any]], cls: str) -> list[dict[str, Any]]:
    """Exploratory: every classifier-detected generator fault of the class, flagged or not."""
    out = []
    for r in recs:
        if any(f["fault_class"] == cls for f in r["detected_faults"]):
            flagged = any(cls in f for f in r.get("verifier_flags", []))
            out.append({"cluster": r["cluster_clause_id"], "v": float(flagged), "pair": (r["case_id"], r["seed"], cls)})
    return out


def accuracy_records(recs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"cluster": r["cluster_clause_id"], "v": float(r["is_correct"]), "pair": (r["case_id"], r["seed"])} for r in recs]


def paired_diff(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> dict[str, Any]:
    """Mean of (b - a) over records present in both, with a cluster bootstrap CI."""
    amap = {r["pair"]: r for r in a}
    diffs = [{"cluster_clause_id": r["cluster"], "d": r["v"] - amap[r["pair"]]["v"]} for r in b if r["pair"] in amap]
    if not diffs:
        return {"n": 0, "formatted": "no paired records"}
    n_clusters = len({d["cluster_clause_id"] for d in diffs})
    ci = cluster_bootstrap_ci(diffs, "cluster_clause_id", lambda rs: sum(x["d"] for x in rs) / len(rs))
    sparse = len(diffs) < 5 or n_clusters < 3
    assert ci.point_estimate is not None and ci.ci_lower is not None and ci.ci_upper is not None
    fmt = (f"{ci.point_estimate * 100:+.1f} pp [{ci.ci_lower * 100:+.1f}, {ci.ci_upper * 100:+.1f}] (n={len(diffs)}, "
           f"{n_clusters} clusters)") if not sparse else f"n={len(diffs)}, {n_clusters} clusters (sparse, suppressed)"
    return {"n": len(diffs), "n_clusters": n_clusters, "delta": ci.point_estimate, "ci": [ci.ci_lower, ci.ci_upper],
            "sparse": sparse, "formatted": fmt}


def cell(m: MetricWithCI) -> str:
    if m.total_opportunities == 0:
        return "—"
    if (m.is_sparse or m.point_estimate is None or m.ci_lower is None or m.ci_upper is None
            or m.ci_lower == m.ci_upper):  # a degenerate interval ([0, 0], [100, 100]) is not an interval
        return f"{m.event_count}/{m.total_opportunities}†"
    return f"{m.point_estimate * 100:.0f}% [{m.ci_lower * 100:.0f}, {m.ci_upper * 100:.0f}] ({m.event_count}/{m.total_opportunities}, {m.n_clusters}c)"


def mdump(m: MetricWithCI) -> dict[str, Any]:
    return m.model_dump()


# ==============================================================================
# Analyses
# ==============================================================================
def analyse(runs: dict[str, list[dict[str, Any]]], cases: dict[str, BenchmarkCase]) -> dict[str, Any]:
    res: dict[str, Any] = {"arms_present": sorted(runs)}

    # Correctness per arm
    res["accuracy"] = {a: mdump(metric(accuracy_records(runs[a]))) for a in GENERATOR_ARMS + VERIFIER_ARMS if a in runs}
    res["unsupported_correct"] = {
        a: mdump(metric([{"cluster": r["cluster_clause_id"], "v": float(r["unsupported_correct"])} for r in runs[a]]))
        for a in GENERATOR_ARMS if a in runs}

    # Generator error profile (share of case-runs with a detected fault of each class)
    prof: dict[str, dict[str, Any]] = {}
    for a in ["arm1", "arm2", "arm2o"]:
        if a not in runs:
            continue
        prof[a] = {}
        for cls in ["F1", "F2", "F3", "F4-R", "F4-C", "F5", "F6", "F7", "F9"]:
            recs = [{"cluster": r["cluster_clause_id"], "v": float(any(
                (f["fault_subtype"] or f["fault_class"]) == cls or f["fault_class"] == cls
                for f in r["detected_faults"]))} for r in runs[a]]
            prof[a][cls] = mdump(metric(recs))
        prof[a]["seeded_committed"] = {cls: sum(len(sensitivity_records([r], cases, cls)) > 0 for r in runs[a])
                                       for cls in CLASSES}
    res["generator_profile"] = prof

    # Central table: per verifier arm x class sensitivity / specificity (+ exploratory detected)
    central: dict[str, dict[str, Any]] = {}
    for a in VERIFIER_ARMS:
        if a not in runs:
            continue
        central[a] = {}
        for cls in CLASSES:
            central[a][cls] = {"sensitivity": mdump(metric(sensitivity_records(runs[a], cases, cls))),
                               "specificity": mdump(metric(specificity_records(runs[a], cases, cls))),
                               "detected_sensitivity": mdump(metric(detected_records(runs[a], cls)))}
        for cls in DETECTED_ONLY:
            central[a][cls] = {"detected_sensitivity": mdump(metric(detected_records(runs[a], cls)))}
    res["central"] = central

    # H2 / H1a ladder: paired contrasts 000 -> 100 -> 110 -> 111, and compute control 3R vs 3
    steps = [("arm3", "arm4_100"), ("arm4_100", "arm4_110"), ("arm4_110", "arm4_111"), ("arm3", "arm4_110"), ("arm3", "arm4_111"),
             ("arm3", "arm3_reflect"), ("arm3_reflect", "arm4_111")]
    ladder: dict[str, dict[str, Any]] = {}
    for x, y in steps:
        if x not in runs or y not in runs:
            continue
        key = f"{x}->{y}"
        ladder[key] = {}
        for cls in CLASSES:
            ladder[key][cls] = {
                "sensitivity": paired_diff(sensitivity_records(runs[x], cases, cls), sensitivity_records(runs[y], cases, cls)),
                "specificity": paired_diff(specificity_records(runs[x], cases, cls), specificity_records(runs[y], cases, cls)),
            }
        # Pooled over classes: the preregistered 100 -> 110 prediction concerns overall sensitivity
        ladder[key]["all"] = {
            k: paired_diff([r for cls in CLASSES for r in f(runs[x], cases, cls)],
                           [r for cls in CLASSES for r in f(runs[y], cases, cls)])
            for k, f in (("sensitivity", sensitivity_records), ("specificity", specificity_records))}
        ladder[key]["accuracy"] = paired_diff(accuracy_records(runs[x]), accuracy_records(runs[y]))
    res["ladder"] = ladder

    # H3: completeness vs verification on ground-truth omissions (applicable rule not cited)
    h3: dict[str, dict[str, Any]] = {}
    for a in VERIFIER_ARMS:
        if a not in runs:
            continue
        h3[a] = {}
        for sub in ["F4-R", "F4-C", "all"]:
            om = [{"cluster": r["cluster_clause_id"], "ver": float(c["verifier"]), "comp": float(c["completeness"]),
                   "either": float(c["verifier"] or c["completeness"])}
                  for r in runs[a] for c in r.get("omission_catches", {}).values() if sub == "all" or c["subtype"] == sub]
            h3[a][sub] = {k: mdump(metric([{"cluster": o["cluster"], "v": o[k]} for o in om]))
                          for k in ("ver", "comp", "either")}
    res["h3_completeness"] = h3

    # The checklist's false alarms (it runs on the Arm 2 output, identical across verifier arms)
    if "arm3" in runs:
        rs = runs["arm3"]
        flags = [(r, f) for r in rs for f in r.get("completeness_flags", [])]
        clean = [r for r in rs if not r.get("omission_catches")]
        res["completeness_false_alarms"] = {
            "cases_flagged": sum(bool(r.get("completeness_flags")) for r in rs), "cases": len(rs),
            "clean_cases_flagged": sum(bool(r.get("completeness_flags")) for r in clean), "clean_cases": len(clean),
            "flags_naming_no_omission": sum(not any(o in f for o in r["omission_catches"]) for r, f in flags),
            "flags": len(flags)}

    # Oracle gap (Arm 2-O minus Arm 2), locked interpretation rule including the CI condition
    if "arm2" in runs and "arm2o" in runs:
        gap = paired_diff(accuracy_records(runs["arm2"]), accuracy_records(runs["arm2o"]))
        if gap.get("n"):
            d, (lo, hi) = gap["delta"], gap["ci"]
            gap["classification"] = classify_oracle_gap(d, lo, hi)
            gap["sign"] = "positive" if d > 0 else "negative" if d < 0 else "zero"
        res["oracle_gap"] = gap

    # Table 8 manipulation check: mean Jaccard per verifier arm over non-vacuous cases
    jac = {}
    for a in VERIFIER_ARMS:
        if a in runs:
            vals = [r["evidence_overlap_jaccard"] for r in runs[a] if r.get("evidence_overlap_jaccard") is not None]
            jac[a] = {"mean": sum(vals) / len(vals) if vals else None, "n": len(vals)}
    order: list[float | None] = [jac.get(a, {}).get("mean") for a in ["arm3", "arm4_100", "arm4_110", "arm4_111"]]
    o = [x for x in order if x is not None]
    res["jaccard"] = jac
    res["jaccard_check"] = {
        "J000_is_one": order[0] == 1.0,
        "prereg_ordering_holds": None if len(o) < 4 else (o[0] > o[1] and o[1] >= o[2] >= o[3]
                                                          and (o[1] == 0 or o[1] > o[2])),
    }

    # Risk-coverage operating points (exploratory): abstain whenever the verifier flags
    rc = {}
    for a in VERIFIER_ARMS:
        if a not in runs:
            continue
        answered = [r for r in runs[a] if not r.get("verifier_flags")]
        n = len(runs[a])
        rc[a] = {"coverage": len(answered) / n if n else None,
                 "risk": (sum(not r["is_correct"] for r in answered) / len(answered)) if answered else None,
                 "n": n}
    res["risk_coverage"] = rc

    # Exploratory, case level: does any flag separate wrong decisions from correct ones?
    res["case_flags"] = {a: {"wrong_passed": sum(not r["is_correct"] and not r.get("verifier_flags") for r in runs[a]),
                             "wrong": sum(not r["is_correct"] for r in runs[a]),
                             "correct_flagged": sum(r["is_correct"] and bool(r.get("verifier_flags")) for r in runs[a]),
                             "correct": sum(bool(r["is_correct"]) for r in runs[a])}
                         for a in VERIFIER_ARMS if a in runs}
    return res


def classify_oracle_gap(delta: float, lo: float, hi: float) -> str:
    """Locked rule (20_method/ORACLE_INTERPRETATION_RULE.md): the CI condition overrides the point estimate."""
    if lo <= 0 <= hi or abs(delta) <= TAU:
        return "Reasoning Bottleneck Dominates (0 in CI or |delta| <= 2.5%)"
    if delta > TAU and lo > 0:
        return "Retrieval Bottleneck Dominates"
    if delta < -TAU and hi < 0:
        return "Statutory Context Pathology (oracle context degrades accuracy)"
    return "Unclassified by the locked rule"


def seed_spread(runs: dict[str, list[dict[str, Any]]]) -> dict[str, dict[int, float]]:
    out: dict[str, dict[int, float]] = {}
    for a, recs in runs.items():
        by: dict[int, list[float]] = defaultdict(list)
        for r in recs:
            by[r["seed"]].append(float(r["is_correct"]))
        out[a] = {s: sum(v) / len(v) for s, v in by.items()}
    return out


def cost_sweep(index_path: Path, cases_path: Path, model: str) -> dict[str, dict[str, float]]:
    """Secondary: cost-weighted error per arm under the three preregistered matrices (mean over seeds)."""
    acc: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in json.loads(index_path.read_text(encoding="utf-8")):
        if not same_file(row["cases"], cases_path) or row["model"] not in {model, "none"}:
            continue
        sc = json.loads((index_path.parent / row["run_id"] / "scorecard.json").read_text(encoding="utf-8"))
        for k, v in sc.get("cost_weighted_error", {}).items():
            acc[row["arm"]][k].append(v)
    return {a: {k: sum(v) / len(v) for k, v in d.items()} for a, d in acc.items()}


# ==============================================================================
# Rendering
# ==============================================================================
def write_table(out: Path, name: str, caption: str, header: list[str], rows: list[list[str]], note: str) -> None:
    md = [f"**{caption}**", "", "| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    md += ["| " + " | ".join(r) + " |" for r in rows]
    md += ["", f"*{note}*"]
    (out / "markdown").mkdir(parents=True, exist_ok=True)
    (out / "latex").mkdir(parents=True, exist_ok=True)
    (out / "markdown" / f"{name}.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")

    def esc(s: str) -> str:
        return s.replace("%", r"\%").replace("&", r"\&").replace("#", r"\#").replace("_", r"\_").replace("†", r"$^\dagger$")

    def stack(c: str) -> str:
        # "80% [0, 100] (4/5, 3c)" -> two stacked lines, so wide tables fit the page
        m = re.fullmatch(r"(.+?\]) \((.+)\)", c)
        return rf"\begin{{tabular}}[t]{{@{{}}l@{{}}}}{esc(m.group(1))}\\{esc(m.group(2))}\end{{tabular}}" if m else esc(c)

    # LaTeX numbers tables itself: "Table 5b (EXPLORATORY): x" -> "EXPLORATORY: x"
    cm = re.match(r"Table \w+ ?(?:\((\w+)\))?: (.*)", caption)
    tcap = ((cm.group(1) + ": ") if cm.group(1) else "") + cm.group(2) if cm else caption

    tex = [r"\begin{table*}[t]", r"\centering", r"\scriptsize", rf"\caption{{{esc(tcap)}}}", rf"\label{{tab:{name}}}",
           r"\begin{adjustbox}{max width=\textwidth}",
           r"\begin{tabular}{" + "l" * len(header) + "}", r"\toprule", " & ".join(esc(h) for h in header) + r" \\",
           r"\midrule"] + [" & ".join(stack(c) for c in r) + r" \\" for r in rows] + [
           r"\bottomrule", r"\end{tabular}", r"\end{adjustbox}", rf"\par\smallskip\footnotesize{{{esc(note)}}}",
           r"\end{table*}"]
    (out / "latex" / f"{name}.tex").write_text("\n".join(tex) + "\n", encoding="utf-8", newline="\n")


def render(res: dict[str, Any], out: Path, model: str, runs_used: list[str], gate0: dict[str, Any], manifest: dict[str, Any],
           costs: dict[str, Any], spread: dict[str, Any]) -> None:
    prov = f"Model: {model}. Runs: {len(runs_used)} ({res.get('index', display(RESULTS_DIR / 'runs' / 'matrix_index.json'))}). "
    sparse = "† sparse (n<5 or <3 clusters): point estimate suppressed, k/n shown. "
    tdir = out / "tables"

    # T1 corpus
    docs = manifest["documents"]
    rows = []
    for j in ["IN", "MH", "RJ"]:
        ds = [d for d in docs if d["doc_id"].startswith(j)]
        rows.append([j, str(len(ds)), str(sum(d["pages"] for d in ds)),
                     str(sum(d["status"] == "presumed_superseded" for d in ds)),
                     str(sum(d["text_layer"] == "ocr" for d in ds)),
                     str(sum(d["retrieved_via"] in {"web_search", "orphan"} for d in ds))])
    write_table(tdir, "table1_corpus", "Table 1: Corpus composition (46 authentic documents)",
                ["Jurisdiction", "Documents", "Pages", "Presumed superseded", "OCR text layer", "web_search/orphan"],
                rows, f"Source: {display(CORPUS_DIR / 'MANIFEST.json')} (SuryaBench-Corpus-2026.11-r2).")

    # T4 Gate 0 predicted vs observed
    pred = {"r1_superseded_chunks": ("10 (4-20)"), "r2_wrong_jurisdiction_chunks": "18 (8-30)",
            "r3_severed_chunks": "40 (25-55)", "r4_missing_expected_node_queries": "11 (7-15)",
            "r5_both_versions_present_queries": "3 (1-7)", "r6_undated_chunks": "3 (0-8)",
            "r7_qa_superseded_queries": "3 (1-5)", "r8_qb_wrong_jurisdiction_queries": "3 (2-5)",
            "misleading_percentage": "25% (12-40%)"}
    rows = [[k.split("_")[0].upper() if k.startswith("r") else "Misleading %", v, str(gate0["metrics"][k])]
            for k, v in pred.items()]
    write_table(tdir, "table4_gate0", "Table 4: Gate 0 predicted vs observed (100 chunks, 20 queries)",
                ["Metric", "Predicted (range)", "Observed"], rows,
                "Predictions: 20_method/GATE0_PREDICTIONS_46DOC.md (committed before the run; prior exposure disclosed).")

    # T5 central
    c = res["central"]
    header = ["Verifier"] + [f"{cls} sens" for cls in CLASSES] + [f"{cls} spec" for cls in CLASSES]
    rows = [[LABEL[a]] + [cell(MetricWithCI(**c[a][cls]["sensitivity"])) for cls in CLASSES]
            + [cell(MetricWithCI(**c[a][cls]["specificity"])) for cls in CLASSES] for a in VERIFIER_ARMS if a in c]
    write_table(tdir, "table5_central", "Table 5: Verifier sensitivity and specificity per failure class "
                "(seeded fault events the generator committed; 95% clause-clustered CIs)", header, rows,
                prov + sparse + "Unit: fault events (sensitivity); avoided traps and non-fault opportunities "
                "(specificity). Nested design 000->100->110->111: incremental effects only.")
    header = ["Verifier"] + [f"{cls} (detected)" for cls in CLASSES + DETECTED_ONLY]
    rows = [[LABEL[a]] + [cell(MetricWithCI(**c[a][cls]["detected_sensitivity"])) for cls in CLASSES + DETECTED_ONLY]
            for a in VERIFIER_ARMS if a in c]
    write_table(tdir, "table5b_detected", "Table 5b (EXPLORATORY): verifier flag rate on classifier-detected "
                "generator faults, all cases", header, rows, prov + sparse + "Exploratory: denominators are "
                "faults the classifier detected in any case, not seeded events.")

    # T6 oracle gap
    if "oracle_gap" in res:
        g = res["oracle_gap"]
        acc = res["accuracy"]
        rows = [[LABEL["arm2"], cell(MetricWithCI(**acc["arm2"]))], [LABEL["arm2o"], cell(MetricWithCI(**acc["arm2o"]))],
                ["Oracle gap (2-O minus 2), paired", g["formatted"]],
                ["Sign", g.get("sign", "-")], ["Locked rule (tau = 2.5%, CI condition)", g.get("classification", "-")]]
        write_table(tdir, "table6_oracle_gap", "Table 6: Retrieval-oracle gap (H3 instrument validity, charter RQ-a)",
                    ["Quantity", "Value"], rows, prov + "Arm 2-O is a diagnostic, not a competing system.")

    # T7 H3 completeness
    h3 = res["h3_completeness"]
    rows = []
    for a in VERIFIER_ARMS:
        if a in h3:
            for sub in ["F4-R", "F4-C", "all"]:
                d = h3[a][sub]
                rows.append([LABEL[a], sub, cell(MetricWithCI(**d["ver"])), cell(MetricWithCI(**d["comp"])),
                             cell(MetricWithCI(**d["either"]))])
    write_table(tdir, "table7_completeness", "Table 7: Omissions caught by claim verification vs the affirmative "
                "completeness checklist (H3)", ["Verifier", "Omission", "Verification", "Completeness", "Either"], rows,
                prov + sparse + "Unit: ground-truth omissions (a decisive clause the generator did not cite). "
                + ("Checklist false alarms: {cases_flagged}/{cases} cases flagged; {clean_cases_flagged}/{clean_cases} "
                   "cases with no omission flagged; {flags_naming_no_omission}/{flags} flags name no ground-truth "
                   "omission.".format(**res["completeness_false_alarms"]) if "completeness_false_alarms" in res else ""))

    # T8 Jaccard
    j = res["jaccard"]
    rows = [[LABEL[a], f"{j[a]['mean']:.4f}" if j[a]["mean"] is not None else "—", str(j[a]["n"])] for a in VERIFIER_ARMS if a in j]
    chk = res["jaccard_check"]
    write_table(tdir, "table8_overlap", "Table 8: Manipulation check: generator-verifier evidence overlap (Jaccard)",
                ["Verifier", "Mean J", "Non-vacuous n"], rows,
                prov + f"J(000)=1: {chk['J000_is_one']}; preregistered ordering holds: {chk['prereg_ordering_holds']}.")

    # T9 generator profile
    gp = res["generator_profile"]
    fcls = ["F1", "F2", "F3", "F4-R", "F4-C", "F5", "F6", "F7", "F9"]
    rows = [[LABEL[a], cell(MetricWithCI(**res["accuracy"][a]))] + [cell(MetricWithCI(**gp[a][k])) for k in fcls]
            for a in ["arm1", "arm2", "arm2o"] if a in gp]
    if "arm0" in res["accuracy"]:
        rows.insert(0, [LABEL["arm0"], cell(MetricWithCI(**res["accuracy"]["arm0"]))] + ["—"] * len(fcls))
    write_table(tdir, "table9_generators", "Table 9: Generator correctness and detected error profile "
                "(share of case-runs with a detected fault)", ["Arm", "Accuracy"] + fcls, rows,
                prov + sparse + "Arm 0 reproduces the rule-derived labels and is a ceiling reference.")

    # T10 ladder contrasts + compute control
    rows = []
    for key, d in res["ladder"].items():
        x, y = key.split("->")
        name = f"{LABEL[y]} vs {LABEL[x]}" + (" [COMPUTE CONTROL]" if y == "arm3_reflect" else
                                              " [EXPLORATORY]" if x == "arm3_reflect" else "")
        for cls in CLASSES + ["all"]:
            rows.append([name, cls, d[cls]["sensitivity"]["formatted"], d[cls]["specificity"]["formatted"]])
        rows.append([name, "accuracy", d["accuracy"]["formatted"], ""])
    write_table(tdir, "table10_ladder", "Table 10: Paired contrasts along the independence ladder (H2) and the "
                "compute control (Arm 3-Reflect vs Arm 3)", ["Contrast", "Class", "Delta sensitivity", "Delta specificity"],
                rows, prov + "Paired by case, seed and fault event; the same Arm 2 output is verified in every "
                "configuration. The compute control is not a hypothesis. EXPLORATORY: the Arm 4 (111) vs Arm 3-Reflect "
                "contrast (not preregistered) and the pooled 'all' rows except 100->110 (the preregistered flat-step test).")

    # T11 cost (secondary)
    rows = [[LABEL.get(a, a)] + [f"{costs[a].get(k, float('nan')):.3f}" for k in ("low_asymmetry", "central", "high_asymmetry")]
            for a in GENERATOR_ARMS + VERIFIER_ARMS if a in costs]
    write_table(tdir, "table11_cost", "Table 11 (SECONDARY): cost-weighted error across three assumed cost matrices",
                ["Arm", "Low", "Central", "High"], rows,
                prov + "Assumed parameters (charter §16.10); read as a range, never a single number.")

    # T12 seed spread
    rows = [[LABEL.get(a, a)] + [f"{spread[a][s] * 100:.1f}%" for s in sorted(spread[a])] for a in spread]
    write_table(tdir, "table12_seeds", "Table 12: Case accuracy per seed", ["Arm", "Seed accuracy (ascending seed)"], rows,
                prov + "Temperature 0; seed variation measures provider nondeterminism.")

    # T13 (exploratory) case-level flag informativeness
    rows = [[LABEL[a], f"{d['wrong_passed']}/{d['wrong']}", f"{d['correct_flagged']}/{d['correct']}"]
            for a, d in res["case_flags"].items()]
    write_table(tdir, "table13_case_flags", "Table 13 (EXPLORATORY): case-level flag informativeness",
                ["Verifier", "Wrong decisions passed", "Correct decisions flagged"], rows,
                prov + "Exploratory, not preregistered. Unit: cases. A flag is any verifier fault flag, of any class.")

    figures(res, out / "figures", model, gate0)


def _save(fig: Any, path: Path, model: str) -> None:
    fig.text(0.99, 0.005, f"SuryaBench · {model}", ha="right", va="bottom", fontsize=6, color="#888")
    path.parent.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "svg", "png"):
        meta = {"pdf": {"CreationDate": None}, "svg": {"Date": None}}.get(ext, {})  # byte-reproducible
        fig.savefig(path.with_suffix(f".{ext}"), dpi=200, bbox_inches="tight", metadata=meta)
    plt.close(fig)


def figures(res: dict[str, Any], out: Path, model: str, gate0: dict[str, Any]) -> None:
    # F2: Gate 0 misleading chunks by band (data: 50_analysis/results/gate0_audit.json)
    bands: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for ch in gate0["chunks"]:
        b = ch["query_id"][:3]
        bands[b][0] += int(ch["would_mislead"])
        bands[b][1] += 1
    fig, ax = plt.subplots(figsize=(5, 3))
    ks = sorted(bands)
    ax.bar(ks, [100 * bands[k][0] / bands[k][1] for k in ks], color="#4c72b0")
    ax.axhline(12, ls="--", color="#c44e52", lw=1, label="12% branch threshold")
    ax.set_ylabel("Misleading chunks (%)")
    ax.set_title("Gate 0 exposure by query band (100 chunks)")
    ax.legend(fontsize=7)
    _save(fig, out / "fig2_gate0_exposure", model)

    # F3: sensitivity heatmap (seeded events; sparse cells blank)
    c = res["central"]
    arms = [a for a in VERIFIER_ARMS if a in c]
    if arms:
        grid = [[(c[a][cls]["sensitivity"]["point_estimate"] if not c[a][cls]["sensitivity"]["is_sparse"] else float("nan"))
                 for cls in CLASSES] for a in arms]
        fig, ax = plt.subplots(figsize=(6, 3))
        im = ax.imshow([[x if x is not None else float("nan") for x in row] for row in grid], vmin=0, vmax=1, cmap="viridis")
        ax.set_xticks(range(len(CLASSES)), CLASSES)
        ax.set_yticks(range(len(arms)), [LABEL[a] for a in arms], fontsize=7)
        for i, a in enumerate(arms):
            for jdx, cls in enumerate(CLASSES):
                s = c[a][cls]["sensitivity"]
                txt = "—" if s["total_opportunities"] == 0 else (f"{s['event_count']}/{s['total_opportunities']}"
                                                                if s["is_sparse"] else f"{s['point_estimate']:.2f}")
                ax.text(jdx, i, txt, ha="center", va="center", fontsize=6,
                        color="k" if s["is_sparse"] or s["total_opportunities"] == 0 else "w")
        fig.colorbar(im, ax=ax, fraction=0.04)
        ax.set_title("Verifier sensitivity by class, seeded events (sparse: k/n shown, no colour)", fontsize=8)
        _save(fig, out / "fig3_sensitivity_heatmap", model)

    # F4: oracle gap
    if "oracle_gap" in res and res["oracle_gap"].get("n"):
        acc = res["accuracy"]
        fig, ax = plt.subplots(figsize=(4, 3))
        for i, a in enumerate(["arm2", "arm2o"]):
            m = acc[a]
            if m["point_estimate"] is not None:
                ax.errorbar(i, m["point_estimate"], yerr=[[m["point_estimate"] - m["ci_lower"]], [m["ci_upper"] - m["point_estimate"]]],
                            fmt="o", capsize=4)
        ax.set_xticks([0, 1], ["Arm 2", "Arm 2-O (oracle)"])
        ax.set_ylabel("Case accuracy")
        ax.set_title(f"Oracle gap: {res['oracle_gap']['formatted']}", fontsize=7)
        _save(fig, out / "fig4_oracle_gap", model)

    # F6 (secondary): cost-weighted error per arm under the three assumed cost matrices
    costs = res.get("cost", {})
    arms_c = [a for a in GENERATOR_ARMS + VERIFIER_ARMS if a in costs]
    if arms_c:
        fig, ax = plt.subplots(figsize=(6, 3))
        for k, (key, lab) in enumerate([("low_asymmetry", "low"), ("central", "central"), ("high_asymmetry", "high")]):
            ax.bar([i + (k - 1) * 0.27 for i in range(len(arms_c))], [costs[a].get(key, float("nan")) for a in arms_c],
                   width=0.27, label=lab)
        ax.set_xticks(range(len(arms_c)), [LABEL[a] for a in arms_c], rotation=35, ha="right", fontsize=6)
        ax.set_ylabel("Cost-weighted error")
        ax.set_title("SECONDARY: cost-weighted error under three assumed cost matrices", fontsize=8)
        ax.legend(fontsize=6, title="asymmetry", title_fontsize=6)
        _save(fig, out / "fig6_cost_sweep", model)

    # F5 (exploratory): risk-coverage operating points, abstain on verifier flag
    rc = res["risk_coverage"]
    pts = [(a, v) for a, v in rc.items() if v["coverage"] is not None and v["risk"] is not None]
    if pts:
        fig, ax = plt.subplots(figsize=(4, 3))
        for a, v in pts:
            ax.scatter(v["coverage"], v["risk"])
            ax.annotate(LABEL[a], (v["coverage"], v["risk"]), fontsize=6)
        ax.set_xlabel("Coverage (answered when verifier passes)")
        ax.set_ylabel("Risk (error among answered)")
        ax.set_title("EXPLORATORY: risk-coverage (abstain on any flag); arms at 0 coverage omitted", fontsize=7)
        _save(fig, out / "fig5_risk_coverage", model)


# ==============================================================================
# Controlled-exposure matrix (RD2/RD7)
# ==============================================================================
EXPOSURE_CLASS = {"S-swap": "F3", "S-both": "F3", "J": "F2", "A": "F5", "O": "F4"}
# D28: the F3 primary condition is S-both (current and superseded clause both in context); S-swap is secondary.
PRIMARY_CONDITIONS = ["S-both", "J", "A"]  # one planted validity fault per case per class (plan section 4)
NOISE_LEVELS = ["reg_noisy25", "reg_noisy50", "reg_spurious10"]  # each run at seeds _s0.._s4 (D31)
EXP_ARMS = ["arm3", "arm3_reflect", "arm4_100n", "arm4_100", "reg_oracle", "reg_real", *NOISE_LEVELS, "reg_real_llm"]
EXP_LABEL = {"arm3": "000", "arm3_reflect": "000-Reflect", "arm4_100n": "100-neutral", "arm4_100": "100-audit",
             "reg_oracle": "reg-oracle", "reg_real": "reg-real", "reg_noisy25": "reg-noisy25", "reg_noisy50": "reg-noisy50",
             "reg_spurious10": "reg-spurious10",
             "reg_real_llm": "reg-real-llm",
             # retired configurations, kept so old exposure indexes still render
             "arm4_110": "110", "arm4_111": "111"}
REGISTRY_LABELS = ["reg_oracle", "reg_real", *NOISE_LEVELS, "reg_real_llm"]
# McNemar contrasts, pooled over PRIMARY_CONDITIONS. EXPLORATORY and labelled so: the preregistered family
# (PREREGISTRATION_v2.md section 4) is computed by suryabench.analysis.prereg (cluster permutation, Holm,
# co-primary FPR rule). Each side is (verifier label, metadata).
# D29: every contrast at metadata on, except metadata on vs off.
MCNEMAR_POOLED = {
    "validity vs support prompt (000), pooled S-both+J+A": (("arm3", True), ("arm3@validity", True)),
    "metadata on vs off (000), pooled S-both+J+A": (("arm3", False), ("arm3", True)),
    "100-neutral vs 000, pooled S-both+J+A": (("arm3", True), ("arm4_100n", True)),
    "reg-real vs 000, pooled S-both+J+A": (("arm3", True), ("reg_real", True)),
}
EXPLORATORY_CONTRASTS = [("arm3", "arm3_reflect"), ("arm3_reflect", "arm4_100n"), ("arm3", "reg_oracle"),
                         ("reg_real", "reg_oracle"), ("arm3", "reg_real_llm"), ("arm3", "arm4_100")]


def verifier_label(row: dict[str, Any]) -> str:
    """Index row -> verifier label: arm, plus @variant, @tax (taxonomy ablation, D26) and @x:<model> when they
    differ from the default. Deterministic registries carry no suffix."""
    lab = str(row["arm"])
    if not lab.startswith("reg_") or lab == "reg_real_llm":
        if row.get("variant", "support") != "support":
            lab += f"@{row['variant']}"
        if row.get("taxonomy", False) is True:
            lab += "@tax"
        if row.get("verifier_model", row["model"]) != row["model"]:
            lab += f"@x:{row['verifier_model']}"
    return lab


def label_name(lab: str) -> str:
    arm, _, rest = lab.partition("@")
    return EXP_LABEL.get(arm, arm) + (f" @{rest}" if rest else "")


def load_exposure(index_path: Path, model: str) -> dict[tuple[str, str, bool], list[dict[str, Any]]]:
    """(verifier label, condition, metadata) -> per-case records of that run (latest run wins)."""
    runs: dict[tuple[str, str, bool], list[dict[str, Any]]] = {}
    for row in json.loads(index_path.read_text(encoding="utf-8")):
        if row["model"] != model:
            continue
        path = index_path.parent / row["run_id"] / "evaluations.json"
        if not path.exists():
            continue
        runs[(verifier_label(row), row["condition"], bool(row.get("metadata", False)))] = json.loads(
            path.read_text(encoding="utf-8"))
    return runs


def _planted(r: dict[str, Any]) -> str | None:
    exp = r.get("raw", {}).get("exposure") or {}
    return exp.get("planted")


def exposure_events(recs: list[dict[str, Any]], cond: str) -> list[dict[str, Any]]:
    """One row per planted fault event: committed (primary: cited and outcome flipped; secondary: cited),
    caught (primary, D32: a finding names the planted clause with the class's reason; secondary: the clause
    whatever the reason, ``caught_clause``, and the class label), and completeness-caught (O)."""
    out = []
    for r in recs:
        eid = f"{r['case_id']}#exp-{cond}"
        committed = r["fault_event_committed"].get(eid)
        if committed is None:
            continue
        cited = r.get("fault_event_committed_citation", {}).get(eid, committed)
        caught = r["fault_event_matches"].get(eid, False) if cited else r["avoided_trap_matches"].get(eid, False)
        caught_class = r.get("fault_event_matches_class", r["fault_event_matches"]).get(eid, False) if cited else caught
        caught_clause = r.get("fault_event_matches_clause", r["fault_event_matches"]).get(eid, False) if cited else caught
        planted = _planted(r)
        comp = cond == "O" and planted is not None and bool(r.get("omission_catches", {}).get(planted, {}).get("completeness"))
        flip = (r.get("raw", {}).get("exposure") or {}).get("implied_flip")
        out.append({"cluster": r["cluster_clause_id"], "case_id": r["case_id"], "event": eid,
                    "committed": bool(committed), "cited": bool(cited), "caught": bool(caught),
                    "caught_class": bool(caught_class), "caught_clause": bool(caught_clause), "comp": comp, "flip_verified": flip is True})
    return out


def _flagged(r: dict[str, Any]) -> bool:
    """Any finding on the case. D30: an invalid verifier reply counts as a flag (a false alarm on condition C),
    while it catches nothing (no findings), so invalid replies cost a configuration on both co-primaries."""
    ver = r.get("raw", {}).get("verifier") or {}
    return ver.get("verdict") == "INVALID" or bool(ver.get("is_flagged", bool(r.get("verifier_flags"))))


def _validity_flagged(r: dict[str, Any]) -> bool:
    """D32, exploratory: a finding whose reason asserts a validity fault (not in force, wrong jurisdiction, not
    applicable). On condition C every such finding is a false alarm about validity."""
    return any(f.rpartition(":")[2] in VALIDITY_REASONS for f in r.get("verifier_flags", []) if f.count(":") >= 2)


def _mcnemar(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> dict[str, Any]:
    """Exact McNemar over primary-committed events present in both configurations (caught under a vs b).
    One unit per (case, condition) event; S-swap and S-both are never pooled."""
    amap = {e["event"]: e["caught"] for e in a if e["committed"]}
    pairs = [(amap[e["event"]], e["caught"]) for e in b if e["committed"] and e["event"] in amap]
    if not pairs:
        return {"n": 0}
    m = mcnemar_test([x for x, _ in pairs], [y for _, y in pairs], exact=True)
    clusters = {e["cluster"] for e in b if e["committed"] and e["event"] in amap}
    return {"n": len(pairs), "n_clusters": len(clusters), "a_caught": sum(x for x, _ in pairs),
            "b_caught": sum(y for _, y in pairs), "a_only": m.n_discordant_a, "b_only": m.n_discordant_b, "p": m.p_value}


def analyse_exposure(runs: dict[tuple[str, str, bool], list[dict[str, Any]]], cases: dict[str, BenchmarkCase]) -> dict[str, Any]:
    labels = sorted({k[0] for k in runs}, key=lambda lab: (EXP_ARMS.index(lab.split("@")[0]) if lab.split("@")[0] in EXP_ARMS else 99, lab))
    keys = sorted({(k[1], k[2]) for k in runs}, key=lambda c: (CONDITIONS_ORDER.index(c[0]) if c[0] in CONDITIONS_ORDER else 99, c[1]))
    res: dict[str, Any] = {"labels": labels, "conditions": [f"{c}{'+meta' if m else ''}" for c, m in keys],
                           "commit": {}, "cells": {}, "fpr_clean": {}, "contrasts": {}, "recovery": {},
                           "flag_rates": {}, "registry_curve": {}, "paraphrase_spread": {}}

    def ckey(c: str, m: bool) -> str:
        return f"{c}{'+meta' if m else ''}"

    # Commit rate: a generator property, identical across configurations (one cached output per condition)
    for c, m in keys:
        if c not in EXPOSURE_CLASS:
            continue
        recs = next(runs[k] for k in runs if k[1] == c and k[2] == m)
        ev = exposure_events(recs, c)
        res["commit"][ckey(c, m)] = {
            "class": EXPOSURE_CLASS[c],
            "primary": mdump(metric([{"cluster": e["cluster"], "v": float(e["committed"])} for e in ev])),
            "citation": mdump(metric([{"cluster": e["cluster"], "v": float(e["cited"])} for e in ev]))}

    for (lab, c, m), recs in runs.items():
        if c == "C":  # clean context, nothing planted: every flag is a false alarm at case level
            res["fpr_clean"][f"{lab}|{ckey(c, m)}"] = mdump(metric(
                [{"cluster": r["cluster_clause_id"], "v": float(_flagged(r))} for r in recs]))
            res.setdefault("fpr_validity_reason_clean", {})[f"{lab}|{ckey(c, m)}"] = mdump(metric(
                [{"cluster": r["cluster_clause_id"], "v": float(_validity_flagged(r))} for r in recs]))
        if c not in EXPOSURE_CLASS:
            continue
        ev = exposure_events(recs, c)
        cell_: dict[str, Any] = {
            "sensitivity": mdump(metric([{"cluster": e["cluster"], "v": float(e["caught"])} for e in ev if e["committed"]])),
            "sensitivity_class_only": mdump(metric([{"cluster": e["cluster"], "v": float(e["caught_class"])}
                                                    for e in ev if e["committed"]])),
            "sensitivity_clause_only": mdump(metric([{"cluster": e["cluster"], "v": float(e["caught_clause"])}
                                                     for e in ev if e["committed"]])),
            "wrong_reason_catches": sum(e["committed"] and e["caught_clause"] and not e["caught"] for e in ev),
            "sensitivity_citation_committed": mdump(metric([{"cluster": e["cluster"], "v": float(e["caught"])}
                                                            for e in ev if e["cited"]])),
            "survival": mdump(metric([{"cluster": e["cluster"], "v": float(e["committed"] and not e["caught"])} for e in ev]))}
        if c == "O":  # completeness on: caught by the verifier or by the checklist
            cell_["sensitivity_with_completeness"] = mdump(metric(
                [{"cluster": e["cluster"], "v": float(e["caught"] or e["comp"])} for e in ev if e["committed"]]))
        res["cells"][f"{lab}|{ckey(c, m)}"] = cell_

    def pooled(lab: str, meta: bool, conds: list[str]) -> list[dict[str, Any]]:
        return [e for c in conds if (lab, c, meta) in runs for e in exposure_events(runs[(lab, c, meta)], c)]

    exploratory = {
        f"{x}->{y}|{ckey(c, m)}": _mcnemar(exposure_events(runs[(x, c, m)], c), exposure_events(runs[(y, c, m)], c))
        for x, y in EXPLORATORY_CONTRASTS for c, m in keys if c in EXPOSURE_CLASS
        if (x, c, m) in runs and (y, c, m) in runs}
    for name, ((la, ma), (lb, mb)) in MCNEMAR_POOLED.items():
        if any(k[0] == la and k[2] == ma for k in runs) and any(k[0] == lb and k[2] == mb for k in runs):
            exploratory[name] = _mcnemar(pooled(la, ma, PRIMARY_CONDITIONS), pooled(lb, mb, PRIMARY_CONDITIONS))
    res["contrasts"]["exploratory"] = exploratory

    # Registry quality curve: sensitivity per registry, per currency/jurisdiction condition
    for c, m in keys:
        if c in {"S-swap", "S-both", "J"}:
            res["registry_curve"][ckey(c, m)] = {
                lab: res["cells"][f"{lab}|{ckey(c, m)}"]["sensitivity"] for lab in REGISTRY_LABELS
                if f"{lab}|{ckey(c, m)}" in res["cells"]}

    # Paraphrase spread of the 000 support prompt
    for c, m in keys:
        vals = {lab: res["cells"][f"{lab}|{ckey(c, m)}"]["sensitivity"] for lab in ("arm3", "arm3@support-p1", "arm3@support-p2")
                if f"{lab}|{ckey(c, m)}" in res["cells"]}
        pts = [v["point_estimate"] for v in vals.values() if v.get("point_estimate") is not None]
        if len(vals) > 1:
            res["paraphrase_spread"][ckey(c, m)] = {"cells": vals, "range": (max(pts) - min(pts)) if pts else None}

    # Arm 5: final = revision if flagged, else the initial answer; on full correctness and on outcome alone
    for (lab, c, m), recs in runs.items():
        rec = [r["raw"]["recovery"] for r in recs if "recovery" in r.get("raw", {})]
        if not rec:
            continue
        row: dict[str, Any] = {"n": len(rec), "flagged": sum(x["flagged"] for x in rec)}
        for tag, i, f in (("", "initial_correct", "final_correct"),
                          ("outcome_", "initial_outcome_correct", "final_outcome_correct")):
            usable = [x for x in rec if i in x and f in x]
            wrong = [x for x in usable if not x[i]]
            right = [x for x in usable if x[i]]
            rec_n, deg_n = sum(x[f] for x in wrong), sum(not x[f] for x in right)
            row.update({f"{tag}initial_wrong": len(wrong), f"{tag}recovered": rec_n, f"{tag}initial_correct": len(right),
                        f"{tag}degraded": deg_n, f"{tag}net": (rec_n - deg_n) / len(usable) if usable else None})
        res["recovery"][f"{lab}|{ckey(c, m)}"] = row

    for (lab, c, m), recs in runs.items():
        res["flag_rates"][f"{lab}|{ckey(c, m)}"] = {"n": len(recs), "any_flag": sum(_flagged(r) for r in recs),
                                                    "F1": sum(any(f.startswith("F1") for f in r.get("verifier_flags", []))
                                                              for r in recs)}
    return res


CONDITIONS_ORDER = ["N", "C", "S-swap", "S-both", "J", "A", "O"]


def render_exposure(res: dict[str, Any], out: Path, model: str, index: str) -> None:
    prov = f"Generator: {model}. Runs: {index}. "
    sparse = "† sparse (n<5, <3 clusters, or a degenerate interval): point estimate suppressed, k/n shown. "
    tdir = out / "tables"
    rows = [[c, v["class"], cell(MetricWithCI(**v["primary"])), cell(MetricWithCI(**v["citation"]))]
            for c, v in res["commit"].items()]
    write_table(tdir, "exp1_commit", "Table E1: Generator commitment of the planted fault, per exposure condition",
                ["Condition", "Planted class", "Committed (primary)", "Cited (secondary)"], rows,
                prov + sparse + "Primary: the answer cites the planted clause and its approve/block outcome flips against "
                "the label (O: omits the removed clause and the outcome flips). Secondary: citation only.")
    rows = []
    for c in res["conditions"]:
        for lab in res["labels"]:
            d = res["cells"].get(f"{lab}|{c}")
            if d:
                rows.append([c, label_name(lab), cell(MetricWithCI(**d["sensitivity"])),
                             cell(MetricWithCI(**d["sensitivity_class_only"])), cell(MetricWithCI(**d["survival"])),
                             cell(MetricWithCI(**d["sensitivity_with_completeness"])) if "sensitivity_with_completeness" in d else ""])
    write_table(tdir, "exp2_detection", "Table E2: Verifier sensitivity and survival of the planted fault",
                ["Condition", "Verifier", "Sensitivity (evidence)", "Sensitivity (class only)", "Survival",
                 "Sens. + completeness (O)"], rows,
                prov + sparse + "Over primary-committed events. Evidence: a finding names the planted class and clause. "
                "Survival = committed and not caught, over exposed cases. Read with Table E2b.")
    rows = [[k.split("|")[1], label_name(k.split("|")[0]), cell(MetricWithCI(**v))] for k, v in sorted(res["fpr_clean"].items())]
    write_table(tdir, "exp2b_fpr_clean", "Table E2b: Case-level false-positive rate on the clean condition C",
                ["Condition", "Verifier", "Cases flagged"], rows,
                prov + sparse + "Condition C shows only the decisive clauses and plants nothing: every flag is a false alarm.")
    rows = []
    for fam, d in res["contrasts"].items():
        for k, v in d.items():
            name = k if "->" not in k else (lambda x, y, cnd: f"{label_name(y)} vs {label_name(x)} ({cnd})")(
                k.split("->")[0], k.split("->")[1].split("|")[0], k.split("|")[1])
            if not v.get("n"):
                rows.append([fam, name, "0", "", "", ""])
                continue
            rows.append([fam, name, f"{v['n']} ({v['n_clusters']}c)", f"{v['a_caught']} / {v['b_caught']}",
                         f"{v['p']:.4f}", f"{v['p_holm']:.4f}" if "p_holm" in v else "(exploratory)"])
    write_table(tdir, "exp3_mcnemar", "Table E3 (EXPLORATORY): Exact McNemar tests on paired catches of committed planted faults",
                ["Family", "Contrast", "Paired events (clusters)", "Caught (first / second)", "p (exact)", "p (Holm)"], rows,
                prov + "Events are not independent within a cluster, so these p-values are descriptive. The preregistered "
                "family (cluster permutation, Holm, co-primary FPR rule) is analysis/prereg.py.")
    rows = [[k.split("|")[1], label_name(k.split("|")[0]), str(v["n"]), str(v["flagged"]),
             f"{v['recovered']}/{v['initial_wrong']}", f"{v['degraded']}/{v['initial_correct']}",
             f"{v['outcome_recovered']}/{v['outcome_initial_wrong']}", f"{v['outcome_degraded']}/{v['outcome_initial_correct']}",
             f"{v['outcome_net'] * 100:+.0f} pp" if v.get("outcome_net") is not None else ""]
            for k, v in sorted(res["recovery"].items())]
    write_table(tdir, "exp4_recovery", "Table E4: Arm 5 closed-loop recovery",
                ["Condition", "Verifier", "Cases", "Flagged", "Recovered", "Degraded", "Recovered (outcome)",
                 "Degraded (outcome)", "Net (outcome)"],
                rows, prov + "Final answer = the revision when the verifier flags, else the initial answer. Outcome = "
                "approve/block/abstain right, ignoring citations. Net = (recovered - degraded) / cases.")
    rows = [[k.split("|")[1], label_name(k.split("|")[0]), f"{v['F1']}/{v['n']}", f"{v['any_flag']}/{v['n']}"]
            for k, v in sorted(res["flag_rates"].items())]
    write_table(tdir, "exp5_flag_rates", "Table E5: Cases with an F1 flag and with any flag",
                ["Condition", "Verifier", "F1 flagged", "Any flag"], rows, prov + "Unit: cases.")
    rows = [[c, label_name(lab), cell(MetricWithCI(**v))] for c, d in res["registry_curve"].items() for lab, v in d.items()]
    write_table(tdir, "exp6_registry_curve", "Table E6: Registry quality and catch rate",
                ["Condition", "Registry", "Sensitivity (evidence)"], rows,
                prov + sparse + "reg-oracle is the benchmark's own graph (upper bound, it also chose the planted clause); "
                "reg-real was built blind from the corpus text; reg-noisy drops 25% / 50% of the oracle's edges.")
    rows = [[c, label_name(lab), cell(MetricWithCI(**v)), f"{d['range'] * 100:.0f} pp" if d["range"] is not None else ""]
            for c, d in res["paraphrase_spread"].items() for lab, v in d["cells"].items()]
    write_table(tdir, "exp7_paraphrase", "Table E7: Spread over three paraphrases of the 000 support prompt",
                ["Condition", "Prompt", "Sensitivity (evidence)", "Range"], rows, prov + sparse)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default=str(RESULTS_DIR / "runs" / "matrix_index.json"))
    ap.add_argument("--cases", default=str(BENCHMARK_DIR / "test_cases_100.json"))
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", default=str(RESULTS_DIR / "paper"))
    ap.add_argument("--exposure-index", default=None, help="analyse a controlled-exposure matrix instead")
    args = ap.parse_args()
    if args.exposure_index:
        eindex, out = resolve(args.exposure_index), resolve(args.out)
        eres = analyse_exposure(load_exposure(eindex, args.model), load_cases(resolve(args.cases)))
        eres.update({"model": args.model, "index": display(eindex)})
        out.mkdir(parents=True, exist_ok=True)
        (out / "results.json").write_text(json.dumps(eres, indent=2, default=str) + "\n", encoding="utf-8", newline="\n")
        render_exposure(eres, out, args.model, display(eindex))
        print(f"wrote {out}/results.json and exposure tables for {args.model}")
        return
    index, cases_path, out = resolve(args.index), resolve(args.cases), resolve(args.out)
    runs = load(index, cases_path, args.model)
    cases = load_cases(cases_path)
    res = analyse(runs, cases)
    res["model"] = args.model
    res["index"] = display(index)
    res["runs"] = run_ids(index, cases_path, args.model)
    res["cost"] = cost_sweep(index, cases_path, args.model)
    res["seed_accuracy"] = seed_spread(runs)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(res, indent=2, default=str), encoding="utf-8", newline="\n")
    gate0 = json.loads((RESULTS_DIR / "gate0_audit.json").read_text(encoding="utf-8"))
    manifest = json.loads((CORPUS_DIR / "MANIFEST.json").read_text(encoding="utf-8"))
    render(res, out, args.model, res["runs"], gate0, manifest, res["cost"], res["seed_accuracy"])
    print(f"wrote {out}/results.json, tables and figures for {args.model} ({len(res['runs'])} runs)")


if __name__ == "__main__":
    main()
