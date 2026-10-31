"""D49: the paper's result tables, written from result files only (no number is typed into the manuscript).

Inputs: ``ladder.json`` (``python -m suryabench.analysis.ladder``; optionally the S1 and S2 sensitivity runs), the seal
manifest ``TEST_MANIFEST_v3.json``, the link-audit table and the annotation agreement. Outputs, in ``--out``
(``60_paper_drafts/paper_v3/generated``): ``tab_main.tex``, ``tab_provenance.tex``, ``tab_scoring.tex``,
``tab_splits.tex``, ``tab_audit.tex``. A cell with no result prints ``--``; a table with no results is not written.

Pooled confusion counts treat items as rows, but items share clauses, so the pooled precision, recall, specificity
and balanced accuracy are descriptive. The headline, discrimination, is clause-averaged with a bootstrap over clauses.
True positive = a right-reason catch of the planted clause (D32); false positive = any finding on a matched control.

    PYTHONPATH=30_code/src:30_code/scripts python 30_code/scripts/make_tables_v3.py --ladder <dir>/ladder.json \
        [--ladder-s1 <dir>/ladder.json --ladder-s2 <dir>/ladder.json] --out 60_paper_drafts/paper_v3/generated
"""

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

from make_numbers_v3 import PANEL, wilson

from suryabench import paths
from suryabench.analysis.ladder import CAPABLE

MAIN_RUNGS = [("R2", "R2", "both versions"), ("R4", "R4", "status line"), ("R4n", "R4n", "no-record wording"),
              ("R5", "R5", "lookup (ref.)"), ("R4-drop50", "R4", "status, drop 50\\%"),
              ("R4n-drop50", "R4n", "no-record, drop 50\\%"), ("R5-drop50", "R5", "lookup, drop 50\\%"),
              ("R4-spurious10", "R4", "status, spur. 10\\%"), ("R5-spurious10", "R5", "lookup, spur. 10\\%")]
DASH = "--"
SHORT = {"kbench-claude-opus-4-5": "Claude Opus 4.5", "qwen2.5:14b": "Qwen 14B", "qwen2.5:7b": "Qwen 7B", "llama3.1:8b": "Llama 8B", "gemma-4-26b-a4b-it": "Gemma 4 26B",
         "gemini-3.5-flash-lite": "Flash-Lite", "qwen2.5:32b": "Qwen 32B"}


def short(model: str) -> str:
    return SHORT.get(model, model.removeprefix("kbench-"))


def pts(x: float | None) -> str:
    return DASH if x is None else re.sub(r"-0(?=\D|$)", "0", f"{100 * x:+.0f}").replace("-", "$-$")


def pc(k: int, n: int) -> str:
    return DASH if not n else f"{100 * k / n:.0f}"


def ci(c: dict[str, Any]) -> str:
    v = c.get("ci95")
    return re.sub(r"-0(?=\D|$)", "0", f"[{100 * v[0]:+.0f}, {100 * v[1]:+.0f}]").replace("-", "$-$") if v else DASH


def disc_key(rung: str, model: str) -> str:
    base, _, state = rung.partition("-")
    return f"R2 @ {model}" if base == "R2" else f"{base} {state or 'intact'} @ {model}"  # R2 has no registry state


def main_table(lad: dict[str, Any], models: list[str] | None = None, label_name: str = "tab:main") -> list[str]:
    """Capable models by default (``models`` picks others, for the appendix). The lookup (R5) is deterministic, the same
    for every model, so it is shown once, as ``Lookup``."""
    rows = []
    chosen = models if models is not None else [m for m in CAPABLE if m in lad.get("models", {})]
    lookup_shown = models is not None  # the appendix table does not repeat the lookup
    for model in chosen:
        cells = lad["models"].get(model, {})
        for rung, _, label in MAIN_RUNGS:
            cell = cells.get(rung)
            if not cell or (rung.startswith("R5") and lookup_shown):
                continue
            tp, n_f = cell["catch_sboth"]["k"], cell["catch_sboth"]["n"]
            fp, n_c = cell["false_alarm_sboth"]["k"], cell["false_alarm_sboth"]["n"]
            if not n_f:
                continue
            fn, tn = n_f - tp, n_c - fp
            prec = pc(tp, tp + fp)
            spec = pc(tn, n_c)
            bal = DASH if not (n_f and n_c) else f"{100 * (tp / n_f + tn / n_c) / 2:.0f}"
            d = lad.get("discrimination", {}).get(disc_key(rung, model), {})
            who = "Lookup" if rung.startswith("R5") else short(model)
            rows.append(f"{who} & {rung} & {label} & {tp} & {fn} & {fp} & {tn} & {pc(tp, n_f)} & {spec} & {prec} & {bal} "
                        f"& {frac(cell['false_alarm_C'])} & {pts(d.get('mean_diff'))} {ci(d)} & {d.get('clauses', DASH)} \\\\")
        lookup_shown = True
    if not rows:
        return []
    return [r"\begin{table*}[t]\centering\scriptsize",
            r"\caption{Main results on S-both faults and their matched correct answers. TP: right-reason catches of the "
            r"planted superseded clause; FN: faults not caught; FP: matched correct answers with any finding; TN: matched "
            r"correct answers passed. Recall, specificity, precision and balanced accuracy (\%) pool items, which share "
            r"clauses, so they are descriptive. FA$_C$: clean correct answers flagged. Disc.: discrimination (catch minus "
            r"matched false alarm), clause-averaged, with a 95\% bootstrap interval over clauses (points). R5 recovers "
            r"the registry's own links by construction and R4 (intact) is given the answer: reference rows.}",
            f"\\label{{{label_name}}}", r"\resizebox{\textwidth}{!}{%", r"\begin{tabular}{lllrrrrrrrrrll}", r"\toprule",
            r"Model & Arm & Reviewer sees & TP & FN & FP & TN & Rec. & Spec. & Prec. & Bal. & FA$_C$ & Disc. [95\% CI] & Cl. \\",
            r"\midrule", *rows, r"\bottomrule", r"\end{tabular}}", r"\end{table*}"]


def frac(d: dict[str, Any] | None) -> str:
    return DASH if not d or not d.get("n") else f"{d['k']}/{d['n']}"


def provenance_table(lad: dict[str, Any], s1: dict[str, Any], s2: dict[str, Any]) -> list[str]:
    rows = []
    names = [("Net-intact", "Q1, intact: R4 $-$ R5 discrimination"), ("Net-drop50", "Q1, 50\\% dropped"),
             ("Net-spurious10", "Q1, 10\\% spurious"), ("Defer", "Q2: R2 $-$ R4-damage catch, dropped links"),
             ("NoRec", "R4n $-$ R4 catch, dropped links")]
    for model in [m for m in lad.get("models", {}) if m in CAPABLE]:  # the primary family only
        for key, label in names:
            c = lad.get("contrasts", {}).get(f"{key} @ {model}")
            if not c:
                continue
            sens = [(x.get("contrasts", {}).get(f"{key} @ {model}") or {}) for x in (s1, s2)]
            holm = f"{c['p_holm']:.3f}" if "p_holm" in c else DASH
            rows.append(f"{short(model)} & {label} & {c['clauses']} & {pts(c.get('mean_diff'))} & {ci(c)} & {holm} & "
                        f"{pts(sens[0].get('mean_diff'))} & {pts(sens[1].get('mean_diff'))} \\\\")
    if not rows:
        return []
    return [r"\begin{table*}[t]\centering\small",
            r"\caption{Primary contrasts (capable models; Holm over the family of ten). Per-clause differences in "
            r"points, mean over clauses, 95\% bootstrap interval over clauses, two-sided sign-flip test. S1: without the "
            r"cases whose checked correct answer was judged flawed; S2: under the original strict annotation rule "
            r"(descriptive when it leaves fewer than ten clauses).}",
            r"\label{tab:provenance}", r"\resizebox{\textwidth}{!}{%", r"\begin{tabular}{llrrlrrr}", r"\toprule",
            r"Model & Contrast & Clauses & Diff. & 95\% CI & $p$ (Holm) & S1 & S2 \\", r"\midrule", *rows,
            r"\bottomrule", r"\end{tabular}}", r"\end{table*}"]


def scoring_table(lad: dict[str, Any], scorer: dict[str, Any] | None) -> list[str]:
    rows = []
    for model, cells in lad.get("models", {}).items():
        for rung in ("R2", "R4", "R4n"):
            c = cells.get(rung)
            if not c:
                continue
            rows.append(f"{short(model)} & {rung} & {frac(c['catch_any'])} & {frac(c['catch_clause'])} & {frac(c['catch'])} & "
                        f"{frac(c['false_alarm_matched'])} & {frac(c['false_alarm_validity'])} \\\\")
    if not rows:
        return []
    note = ""
    if scorer:
        note = (f" Human check of the right-reason scorer on {scorer['n']} dev replies: {scorer['agree']}/{scorer['n']} "
                f"agree (planned gate 95\\%).")
    return [r"\begin{table}[t]\centering\small",
            r"\caption{E5: the same replies under three scoring rules. Catch: any finding on the fault; a finding naming "
            r"the planted clause; naming it with the reason ``not in force'' (the primary rule). False alarms on matched "
            r"correct answers: any finding; a finding with a validity reason." + note + "}",
            r"\label{tab:scoring}", r"\begin{tabular}{llrrrrr}", r"\toprule",
            r"Model & Arm & Any & Clause & Right reason & FA any & FA validity \\", r"\midrule", *rows,
            r"\bottomrule", r"\end{tabular}", r"\end{table}"]


def splits_table(lad: dict[str, Any]) -> list[str]:
    rows = []
    for key, v in lad.get("splits", {}).items():
        rung, model = key.split(" @ ")
        if model not in CAPABLE:
            continue
        w, o = v.get("wording", {}), v.get("outcome", {})
        cell = [f"{frac(x.get(k))} ({x.get(k, {}).get('clauses', 0)})" for x, k in
                ((w, "EXPLICIT"), (w, "IMPLICIT"), (o, "changing"), (o, "basis_only"))]
        cost = lad.get("cost", {}).get(key, {})
        rows.append(f"{short(model)} & {rung} & {' & '.join(cell)} & {cost.get('prompt_tokens', DASH)} & "
                    f"{cost.get('latency_sec', DASH)} \\\\")
    if not rows:
        return []
    return [r"\begin{table*}[t]\centering\small",
            r"\caption{Descriptive splits, no test: right-reason catches k/n (clauses) on S-both faults by how the "
            r"amendment is worded and whether the fault changes the decision; mean prompt tokens and seconds per call.}",
            r"\label{tab:splits}", r"\resizebox{\textwidth}{!}{%", r"\begin{tabular}{llllllrr}", r"\toprule",
            r"Model & Arm & Explicit & Implicit & Outcome-changing & Basis-only & Tokens & s/call \\", r"\midrule",
            *rows, r"\bottomrule", r"\end{tabular}}", r"\end{table*}"]


def audit_table(sealed: dict[str, Any], links: list[dict[str, str]], agreement: dict[str, Any]) -> list[str]:
    n_cand = sealed["n_cases"] + len(sealed["dropped_cases"])
    dec = sum(v.startswith("decision") for v in sealed["dropped_cases"].values())
    stage = sum(v.startswith("blocking stage") for v in sealed["dropped_cases"].values())

    def share(k: int, n: int) -> str:
        lo, hi = wilson(k, n)
        return f"{k}/{n} [{100 * lo:.0f}, {100 * hi:.0f}]"

    flagged = [v for v in sealed["controls_flagged"].values()]
    ctrl_ok = round(sealed["controls_correct"] * sealed["controls_checked"])
    sample = [r for r in links if r["checked_as"] == "quality_sample"]
    pairs = [r for r in links if r["checked_as"] == "test_pair"]
    cases_k = agreement["cases"]["fields"]
    rows = [
        f"Answer key: decision differs from adjudication & {share(dec, n_cand)} \\\\",
        f"Answer key: blocking stage differs (rejected cases) & {share(stage, n_cand)} \\\\",
        f"Kept with deciding clauses disputed & {len(sealed['clause_disputed'])}/{sealed['n_cases']} \\\\",
        f"Sealed: cases / distinct replaced clauses & {sealed['n_cases']} / {sealed['distinct_replaced_clauses']} \\\\",
        f"Checked correct answers judged correct & {share(ctrl_ok, sealed['controls_checked'])} \\\\",
        f"\\quad kept cases whose checked answer was flagged (S1 removes) & {len(flagged)} \\\\",
        f"Registry links, random sample: not a link & {share(sum(r['outcome'] == 'not_a_link' for r in sample), len(sample))} \\\\",
        f"Registry links, random sample: other relation & {share(sum(r['outcome'] == 'relation_changed' for r in sample), len(sample))} \\\\",
        f"Registry links used by test items: not a link & {share(sum(r['outcome'] == 'not_a_link' for r in pairs), len(pairs))} \\\\",
        f"Annotators A vs B, decision: agreement, $\\kappa$ & {cases_k['decision']['agreement_a_b']:.2f}, {cases_k['decision']['kappa_a_b']:.2f} \\\\",
        f"Annotators A vs B, deciding clauses: agreement, $\\kappa$ & {cases_k['deciding_clauses']['agreement_a_b']:.2f}, "
        f"{cases_k['deciding_clauses']['kappa_a_b']:.2f} \\\\",
    ]
    return [r"\begin{table}[t]\centering\small",
            r"\caption{Ground-truth audit. Shares with 95\% Wilson intervals (\%). The random link sample is a seeded "
            r"20\% of the registry links no test item uses; it describes links the registry asserts, not links it "
            r"misses. Agreement is on the seeded shared subset labelled by both annotators.}",
            r"\label{tab:audit}", r"\begin{tabular}{p{6.2cm}l}", r"\toprule", r"Check & Result \\", r"\midrule", *rows,
            r"\bottomrule", r"\end{tabular}", r"\end{table}"]


PER_CLAUSE_RUNGS = ("R2", "R4", "R4n", "R5")


def per_clause_table(path: Path) -> list[str]:
    """D49: right-reason catches per replaced clause (the unit of evidence), capable models, main arms, S-both and
    S-swap faults pooled as ladder_per_clause.csv pools them."""
    with path.open(encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["model"] in CAPABLE and r["rung"] in PER_CLAUSE_RUNGS]
    if not rows:
        return []
    cell = {(r["model"], r["rung"], r["clause"]): f"{r['right']}/{r['faults']}" for r in rows}
    models = [m for m in CAPABLE if any(r["model"] == m for r in rows)]
    lines = []
    for clause in sorted({r["clause"] for r in rows}):
        vals = [cell.get((m, g, clause), DASH) for m in models for g in PER_CLAUSE_RUNGS]
        tex = clause.replace("#", r"\#")  # Python 3.11: no backslash inside an f-string expression
        lines.append(f"\\texttt{{{tex}}} & " + " & ".join(vals) + " \\\\")
    head = " & ".join(f"\\multicolumn{{{len(PER_CLAUSE_RUNGS)}}}{{c}}{{{short(m)}}}" for m in models)
    sub = " & ".join(g for _ in models for g in PER_CLAUSE_RUNGS)
    return [r"\begin{table*}[t]\centering\scriptsize",
            r"\caption{Right-reason catches per replaced clause (k/n faults; R5 also counts S-swap faults), capable "
            r"models. The clause is the unit of every interval and test in the paper.}",
            r"\label{tab:perclause}", r"\resizebox{\textwidth}{!}{%",
            r"\begin{tabular}{l" + "c" * (len(models) * len(PER_CLAUSE_RUNGS)) + "}", r"\toprule",
            f"Replaced clause & {head} \\\\", f" & {sub} \\\\", r"\midrule", *lines, r"\bottomrule",
            r"\end{tabular}}", r"\end{table*}"]


ROBUST_ORDER = ["llama3.1:8b", "qwen2.5:7b", "qwen2.5:14b", "gemma-4-26b-a4b-it", "gemini-3.5-flash-lite", "qwen2.5:32b"]
VALIDITY = {"not_in_force", "wrong_jurisdiction", "not_applicable"}


def robust_table(lad: dict[str, Any]) -> list[str]:
    """The findings that hold across models, one column per model, from one ladder over every model's blocks."""
    models = [m for m in ROBUST_ORDER if m in lad.get("models", {})] + sorted(m for m in lad.get("models", {})
                                                                            if m.startswith("kbench-"))
    if not models:
        return []

    def cell(m: str, rung: str, key: str) -> str:
        return frac(lad["models"][m].get(rung, {}).get(key))

    def gap(m: str) -> str:
        c = lad["models"][m].get("R2", {})  # pooled, like the two rows above it
        a, r = c.get("catch_any") or {}, c.get("catch_sboth") or {}
        return DASH if not a.get("n") or not r.get("n") else pts(a["k"] / a["n"] - r["k"] / r["n"])

    def nonvalidity(m: str) -> str:
        reasons = lad.get("alarm_reasons", {}).get(f"R4 @ {m}", {})
        n = sum(reasons.values())
        return DASH if not n else f"{sum(v for k, v in reasons.items() if k not in VALIDITY)}/{n}"

    def rec(m: str) -> str:
        r = lad.get("recovery", {}).get(f"drop50 @ {m}", {})
        return DASH if not r or not r.get("pairs") else f"+{r['gained']} / $-${r['lost']}"

    def defer(m: str) -> str:
        d = lad.get("deference", {}).get(m)
        return DASH if not d else f"{100 * d['r2_catch']:.0f} $\\to$ {100 * d['r4_damage_catch']:.0f} ({d['clauses']})"

    rows = [("Right-reason catch, both versions (R2)", lambda m: cell(m, "R2", "catch_sboth")),
            ("Any-finding catch, R2", lambda m: cell(m, "R2", "catch_any")),
            ("Scoring gap at R2, any minus right reason (points)", gap),
            ("Right-reason catch, status line (R4)", lambda m: cell(m, "R4", "catch_sboth")),
            ("Correct answers flagged, R4", lambda m: cell(m, "R4", "false_alarm_sboth")),
            ("R4 findings on correct answers not about validity", nonvalidity),
            ("Catches gained / lost vs lookup, 50\\% dropped", rec),
            ("Catch on dropped links, R2 $\\to$ R4-damage, \\% (clauses)", defer)]
    body = [f"{label} & " + " & ".join(fn(m) for m in models) + " \\\\" for label, fn in rows]
    return [r"\begin{table*}[t]\centering\scriptsize",
            r"\caption{The findings across all models, on the same items (pooled k/n over S-both faults, where both versions "
            r"of the clause are shown, or matched correct answers; 50\%-dropped arms pooled over each model's damage "
            r"seeds). The five planned models come first (the open models by size, then Flash-Lite); the last two "
            r"columns were added after the analysis plan was fixed. Gains and losses compare each fault and seed with the "
            r"damaged lookup. The dropped-link catch is clause-averaged over the faults the intact registry catches and the "
            r"damaged one drops.}",
            r"\label{tab:robust}", r"\resizebox{\textwidth}{!}{%",
            r"\begin{tabular}{l" + "c" * len(models) + "}", r"\toprule",
            "Finding & " + " & ".join(short(m) for m in models) + r" \\", r"\midrule", *body, r"\bottomrule",
            r"\end{tabular}}", r"\end{table*}"]


EXPLORE_MODELS = ["qwen2.5:7b", "qwen2.5:14b", "qwen2.5:32b"]  # D49: the size comparison within one family


def exploratory_table(lad: dict[str, Any]) -> list[str]:
    """D49, exploratory: the qwen2.5 sizes (7B, 14B preregistered; 32B and any Kaggle-hosted model added after
    filing) on the main arms, pooled S-both counts and clause-averaged discrimination, and Q1 at two states."""
    models = [m for m in EXPLORE_MODELS if m in lad.get("models", {})]
    models += [m for m in lad.get("models", {}) if m.startswith("kbench-")]
    rows = []
    for m in models:
        cells = lad["models"][m]
        for rung in ("R2", "R4", "R4n", "R4-drop50"):
            c = cells.get(rung)
            if not c or not c["catch_sboth"]["n"]:
                continue
            d = lad.get("discrimination", {}).get(disc_key(rung, m), {})
            reg = "yes" if m in PANEL else "no"
            rows.append(f"{short(m)} & {reg} & {rung} & {frac(c['catch_sboth'])} & {frac(c['false_alarm_sboth'])} & "
                        f"{frac(c['catch_any'])} & {pts(d.get('mean_diff'))} \\\\")
        for state in ("intact", "drop50"):
            c = lad.get("contrasts", {}).get(f"Net-{state} @ {m}", {})
            if c:
                rows.append(f"{short(m)} & {'yes' if m in PANEL else 'no'} & R4$-$R5, {state} & \\multicolumn{{3}}{{c}}{{}} & {pts(c.get('mean_diff'))} "
                            f"{ci(c)} \\\\")
        rows.append(r"\addlinespace")
    if not any(m not in PANEL for m in models):
        return []
    return [r"\begin{table}[t]\centering\small",
            r"\caption{Size comparison within one family. Rows marked ``no'' were added after the analysis plan was fixed and are "
            r"exploratory; the planned sizes are shown beside them. The 32B model ran damage seeds 0--2 (the "
            r"planned capable models ran 0--4). S-both right-reason catches, false alarms on matched correct answers (any finding) and "
            r"any-finding catches, pooled k/n; discrimination clause-averaged (points), and the Q1 difference with a "
            r"95\% bootstrap interval over clauses. No test.}",
            r"\label{tab:exploratory}", r"\footnotesize\setlength{\tabcolsep}{3pt}", r"\begin{tabular}{lllrrrl}",
            r"\toprule",
            r"Model & Planned & Arm & Catch & FA & Any & Disc. / diff. \\", r"\midrule", *rows[:-1], r"\bottomrule",
            r"\end{tabular}", r"\end{table}"]


def write(out: Path, name: str, lines: list[str]) -> None:
    if lines:
        (out / name).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {name}")
    else:
        print(f"skipped {name}: no results")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ladder")
    ap.add_argument("--ladder-s1")
    ap.add_argument("--ladder-s2")
    ap.add_argument("--ladder-exploratory", help="ladder.json over the main and exploratory blocks (D49)")
    ap.add_argument("--sealed", default=str(paths.BENCHMARK_DIR / "TEST_MANIFEST_v3.json"))
    ap.add_argument("--links", default=str(paths.DATA_DIR / "link_audit_v1" / "links.csv"))
    ap.add_argument("--agreement", default=str(paths.RESULTS_DIR / "annotation_d45"))
    ap.add_argument("--scorer", default=str(paths.RESULTS_DIR / "scorer_check" / "scorer_check_report_human.json"))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    def load(p: str | None) -> dict[str, Any]:
        return json.loads(paths.resolve(p).read_text(encoding="utf-8")) if p else {}

    lad, s1, s2 = load(a.ladder), load(a.ladder_s1), load(a.ladder_s2)
    out = Path(paths.resolve(a.out))
    out.mkdir(parents=True, exist_ok=True)
    with Path(paths.resolve(a.links)).open(encoding="utf-8", newline="") as f:
        links = list(csv.DictReader(f))
    agreement = {k: load(str(Path(a.agreement) / k / "agreement.json")) for k in ("cases", "links")}
    scorer_path = Path(paths.resolve(a.scorer))
    scorer = json.loads(scorer_path.read_text(encoding="utf-8")) if scorer_path.exists() else None
    write(out, "tab_audit.tex", audit_table(load(a.sealed), links, agreement))
    write(out, "tab_main.tex", main_table(lad))
    others = [m for m in lad.get("models", {}) if m not in CAPABLE]
    write(out, "tab_main_other.tex", main_table(lad, others, "tab:mainother") if others else [])
    write(out, "tab_provenance.tex", provenance_table(lad, s1, s2))
    write(out, "tab_scoring.tex", scoring_table(lad, scorer))
    write(out, "tab_splits.tex", splits_table(lad))
    if a.ladder:
        write(out, "tab_perclause.tex", per_clause_table(Path(paths.resolve(a.ladder)).parent / "ladder_per_clause.csv"))
    if a.ladder_exploratory:
        write(out, "tab_exploratory.tex", exploratory_table(load(a.ladder_exploratory)))
        write(out, "tab_robust.tex", robust_table(load(a.ladder_exploratory)))
    assert set(PANEL) >= set(lad.get("models", {})), "a model outside the preregistered panel"


if __name__ == "__main__":
    main()
