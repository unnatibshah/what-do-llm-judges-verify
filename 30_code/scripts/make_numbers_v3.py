r"""Write ``numbers.tex`` for the Paper A v3 manuscript (T7): one ``\newcommand`` per number.

Results come from a ``ladder.json`` made by ``python -m suryabench.analysis.ladder``. Design facts come from the v3
candidate manifest and the r3 corpus manifest. Every macro the paper can use is always defined: a value the inputs do
not contain prints as a bold ``[TBD]``. With ``--stage dev`` every result value prints in red and the paper shows a
banner (dev pilot numbers are engineering evidence, never results).

    python 30_code/scripts/make_numbers_v3.py --stage dev --ladder <scratch>/ladder.json \
        --out 60_paper_drafts/paper_v3/numbers.tex
"""

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

from suryabench import paths
from suryabench.analysis.ladder import CAPABLE, CONTRASTS, NET_PRIMARY, RUNG_ORDER, STATES, WEAK
from suryabench.arms.verifier_probe import DAMAGE, DAMAGE_SEEDS

TBD = r"\textbf{[TBD]}"
MANIFEST = paths.RESULTS_DIR / "ladder_design" / "candidate_v3_manifest.json"
ASSIGNMENT = paths.ANNOTATION_DIR / "ASSIGNMENT_D45.csv"
AGREEMENT = paths.RESULTS_DIR / "annotation_d45"  # written by friday_t8.sh: links/ and cases/agreement.json
# The fields annotation_agreement.py scores on each sheet (D45: on the shared subset only).
AGREE_FIELDS = {"links": ["relation", "effective_date", "wording", "new_clause_id"],
                "cases": ["decision", "blocking_stage", "deciding_clauses"]}
# PREREGISTRATION_v3 section 4: the panel and the macro stem of each model.
PANEL = {"llama3.1:8b": "Llama", "qwen2.5:7b": "QwenSeven", "qwen2.5:14b": "QwenFourteen",
         "gemma-4-26b-a4b-it": "Gemma", "gemini-3.5-flash-lite": "Flash"}
# Fixed design constants stated in PREREGISTRATION_v3 (sections 2-7); edit only with a dated DECISIONS.md entry.
PREREG = {"Temperature": "0", "RunSeed": "42", "OutputCap": "1024", "CILevel": "95", "Alpha": "0.05",
          "MinClauses": "10", "SparseItems": "5", "SparseClauses": "3", "InterpPoints": "10", "NPermutations": "10{,}000",
          "ScorerCheckN": "50", "ScorerCheckPct": "95", "NDevClauses": "2", "NLinksAnnotated": "52", "NLinksUsed": "18",
          "LinkSamplePct": "20", "NControlsAnnotated": "40", "NDevPilotModels": "4", "NSharedInstrument": "3"}
WORDS = {"0": "Zero", "1": "One", "2": "Two", "3": "Three", "4": "Four", "5": "Five", "10": "Ten",
         "25": "TwentyFive", "50": "Fifty"}
DAMAGED_RUNGS = [f"R{n}-{d}" for n in (4, 5) for d in DAMAGE] + ["R4n", "R4n-drop25", "R4n-drop50"]  # R4n: D49
METRICS = {"Catch": "catch", "FAM": "false_alarm_matched", "FAC": "false_alarm_C", "CantConfirm": "cant_confirm_fault"}


def stem(label: str) -> str:
    """A rung or contrast label as letters only: R4'-R1 -> RFourPMinusROne, R2-cc -> RTwoCC."""
    s = label.replace("'", "P").replace("-cc", "CC").replace("-", "Minus" if "-R" in label else "-")
    s = re.sub(r"\d+", lambda m: WORDS[m.group()], s)
    return "".join(p[:1].upper() + p[1:] for p in s.split("-"))


def minus(s: str) -> str:
    """A typeset minus sign, not a hyphen, in text-mode numbers."""
    return re.sub(r"-0(?=\D|$)", "0", s).replace("-", "$-$")  # a value that rounds to zero has no sign


def points(x: float | None) -> str | None:
    return None if x is None else minus(f"{100 * x:+.0f}")


def pct(x: float | None) -> str | None:
    return None if x is None else f"{100 * x:.0f}\\%"


def frac(d: dict[str, Any] | None) -> str | None:
    return None if not d or not d.get("n") else f"{d['k']}/{d['n']}"


def result_macros(lad: dict[str, Any]) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    models, contrasts = lad.get("models", {}), lad.get("contrasts", {})
    for model, m in PANEL.items():
        rungs = models.get(model, {})
        for rung in RUNG_ORDER + DAMAGED_RUNGS:
            cell, r = rungs.get(rung, {}), stem(rung)
            for name, key in METRICS.items():
                out[f"{name}{m}{r}"] = pct((cell.get(key) or {}).get("mean"))
                out[f"{name}KN{m}{r}"] = frac(cell.get(key))
            mis = cell.get("misnamed")
            out[f"Misnamed{m}{r}"] = pct(mis["k"] / mis["n"]) if mis and mis["n"] else None
            out[f"MisnamedKN{m}{r}"] = frac(mis)
            out[f"InvalidKN{m}{r}"] = frac(cell.get("invalid"))
            out[f"CantConfirmCorrectKN{m}{r}"] = frac(cell.get("cant_confirm_correct"))
        names = [(n, f"{n} @ {model}") for n in CONTRASTS]
        names += [(f"Gap-{w}", f"(R4-R2) {model} - {w}") for w in WEAK if model in CAPABLE]
        for label, key in names:
            c, k = contrasts.get(key, {}), stem(label.replace(WEAK[0], "Weak")) + m
            diff = c.get("mean_diff")
            out[f"Diff{k}"] = None if diff is None else minus(f"{100 * diff:+.0f}")
            ci = c.get("ci95")
            out[f"CI{k}"] = minus(f"[{100 * ci[0]:+.0f}, {100 * ci[1]:+.0f}]") if ci else ("--" if c else None)
            out[f"P{k}"] = None if "signflip_p" not in c else f"{c['signflip_p']:.3f}"
            out[f"PHolm{k}"] = None if "p_holm" not in c else f"{c['p_holm']:.3f}"
            out[f"Clauses{k}"] = str(c["clauses"]) if c else None
        out |= d47_macros(lad, model, m)
    return out


def d47_macros(lad: dict[str, Any], model: str, m: str) -> dict[str, str | None]:
    """D48 (amendment 1): discrimination and Net contrasts per registry state, deference, spurious links, E5 scoring."""
    out: dict[str, str | None] = {}
    disc, con = lad.get("discrimination", {}), lad.get("contrasts", {})

    def contrast_macros(key: str, c: dict[str, Any]) -> None:
        out[f"Diff{key}"] = points(c.get("mean_diff"))
        ci = c.get("ci95")
        out[f"CI{key}"] = minus(f"[{100 * ci[0]:+.0f}, {100 * ci[1]:+.0f}]") if ci else ("--" if c else None)
        out[f"PHolm{key}"] = None if "p_holm" not in c else f"{c['p_holm']:.3f}"

    for state in STATES:
        s = stem(state)
        for rung in ("R4", "R5"):
            out[f"Disc{stem(rung)}{s}{m}"] = points((disc.get(f"{rung} {state} @ {model}") or {}).get("mean_diff"))
        contrast_macros(f"Net{s}{m}", con.get(f"Net-{state} @ {model}", {}))
    contrast_macros(f"Defer{m}", con.get(f"Defer @ {model}", {}))
    contrast_macros(f"NoRec{m}", con.get(f"NoRec @ {model}", {}))  # D49
    for state in ("intact", "drop50"):  # post hoc (review): per item-seed gains and losses against the lookup
        rec = lad.get("recovery", {}).get(f"{state} @ {model}", {})
        for f in ("gained", "lost", "pairs"):
            out[f"Rec{f.capitalize()}{stem(state)}{m}"] = str(rec[f]) if rec else None
    for state in NET_PRIMARY:  # post hoc (review): Q1 with the amending instrument as the unit
        bi = lad.get("by_instrument", {}).get(f"Net-{state} @ {model}", {})
        out[f"InstrP{stem(state)}{m}"] = f"{bi['signflip_p']:.3f}" if bi else None
        out[f"InstrN{stem(state)}{m}"] = str(bi["instruments"]) if bi else None
    for state in STATES:  # post hoc (review): Q1 with validity-reason false alarms only
        contrast_macros(f"NetV{stem(state)}{m}", lad.get("q1_validity", {}).get(f"Net-{state} @ {model}", {}))
    nr = lad.get("no_record", {}).get(model, {})
    out[f"CatchDroppedRFour{m}"] = pct(nr.get("r4_damage_catch"))
    out[f"CatchDroppedRFourn{m}"] = pct(nr.get("r4n_damage_catch"))
    out[f"NNoRecClauses{m}"] = str(nr["clauses"]) if nr else None
    out[f"CatchNoRecDropped{m}"] = out[f"CatchDroppedRFourn{m}"]
    out[f"DiscRTwo{m}"] = points((disc.get(f"R2 @ {model}") or {}).get("mean_diff"))
    cells = lad.get("models", {}).get(model, {})
    for rung, name in (("R4n", "RFourN"), ("R4n-drop50", "RFourNDropFifty")):
        out[f"FAM{m}{name}"] = pct(((cells.get(rung) or {}).get("false_alarm_matched") or {}).get("mean"))
    for state in ("intact", "drop25", "drop50"):
        out[f"DiscRFourn{stem(state)}{m}"] = points((disc.get(f"R4n {state} @ {model}") or {}).get("mean_diff"))
    d = lad.get("deference", {}).get(model, {})
    out[f"CatchDropped{m}"] = pct(d.get("r4_damage_catch"))
    out[f"OwnCatchDropped{m}"] = pct(d.get("r2_catch"))
    out[f"NDroppedClauses{m}"] = str(d["clauses"]) if d else None
    sp = lad.get("spurious", {}).get(model) or {}
    out[f"NSpuriousClauses{m}"] = str(sp["clauses"]) if sp.get("clauses") else None
    n = sp.get("n")
    out[f"KNSpuriousMarked{m}"] = str(n) if n else None
    out[f"FASpuriousMarked{m}"] = f"{sp['r4']}/{n}" if n else None
    out[f"OwnFASpuriousMarked{m}"] = f"{sp['r2']}/{n}" if n else None
    for rung in ("R0", "R2", "R4"):
        cell = lad.get("models", {}).get(model, {}).get(rung, {})
        for name, key in (("ScAnyCatch", "catch_any"), ("ScClauseCatch", "catch_clause"),
                          ("ScAnyFA", "false_alarm_matched"), ("ScReasonFA", "false_alarm_validity")):
            out[f"{name}{m}{stem(rung)}"] = pct((cell.get(key) or {}).get("mean"))
    return out


ROB_MODELS = {**PANEL, "qwen2.5:32b": "QwenThirtyTwo", "kbench-claude-opus-4-5": "ClaudeOpus"}
VALIDITY = {"not_in_force", "wrong_jurisdiction", "not_applicable"}


def robust_macros(lad: dict[str, Any]) -> dict[str, str | None]:
    """The cross-model findings (Table tab:robust), from the ladder over every model's blocks, main and added."""
    out: dict[str, str | None] = {}
    for model, m in ROB_MODELS.items():
        cells = lad.get("models", {}).get(model, {})

        for rung in ("R2", "R4"):
            c, a, f = ((cells.get(rung) or {}).get(k) or {} for k in ("catch_sboth", "catch_any", "false_alarm_sboth"))
            out[f"RobCatch{m}{stem(rung)}"] = frac(c) if c.get("n") else None
            out[f"RobCatchPct{m}{stem(rung)}"] = pct(c["k"] / c["n"]) if c.get("n") else None
            out[f"RobAny{m}{stem(rung)}"] = frac(a) if a.get("n") else None
            out[f"RobFlagged{m}{stem(rung)}"] = frac(f) if f.get("n") else None
        reasons = lad.get("alarm_reasons", {}).get(f"R4 @ {model}", {})
        n = sum(reasons.values())
        out[f"RobNonValidity{m}"] = f"{sum(v for k, v in reasons.items() if k not in VALIDITY)}/{n}" if n else None
        rec = lad.get("recovery", {}).get(f"drop50 @ {model}", {})
        out[f"RobGained{m}"] = str(rec["gained"]) if rec.get("pairs") else None
        out[f"RobLost{m}"] = str(rec["lost"]) if rec.get("pairs") else None
        d = lad.get("deference", {}).get(model)
        out[f"RobDeferFrom{m}"] = pct(d["r2_catch"]) if d else None
        out[f"RobDeferTo{m}"] = pct(d["r4_damage_catch"]) if d else None
        out[f"RobDeferClauses{m}"] = str(d["clauses"]) if d else None
    return out


def design_macros(man: dict[str, Any], corpus: dict[str, Any]) -> dict[str, str | None]:
    clauses = man["replaced_clauses"]
    ei = man["explicit_implicit"]
    oc = sum(c.get("S-both:outcome_changing", 0) for c in clauses)
    out: dict[str, str | None] = {
        "NTestCases": str(man["n_cases"]), "NClauses": str(man["distinct_replaced_clauses"]),
        "NStates": str(len(man["states"])), "NPairsPerClause": str(man["pairs_per_clause_target"]),
        "NPairsCap": str(man["pairs_per_clause_cap"]), "NCleanC": str(man["clean_correct_answers_C"]),
        "NExplicit": str(ei.get("EXPLICIT", 0)), "NImplicit": str(ei.get("IMPLICIT", 0)), "NNoLink": str(ei.get("NONE", 0)),
        "NRegistryFlagged": str(sum(int(c["registry_flags_superseded"].split("/")[0]) > 0 for c in clauses)),
        "NOutcomeChangingSBoth": str(oc),
        "NCorpusDocs": str(len(corpus["documents"])),
        "NCorpusJurisdictions": str(len({d["jurisdiction"]["code"] for d in corpus["documents"]})),
        "NPanelModels": str(len(PANEL) - 1), "NCapable": str(len(CAPABLE)),
        "NPrimaryTests": str(len(CAPABLE) * (len(NET_PRIMARY) + 1)),  # D48: Net x 3 states + Defer
        "NPrimaryTestsVFour": str(len(CAPABLE) * (len(NET_PRIMARY) + 1)),
        "NDamageSeedsCapable": str(len(DAMAGE_SEEDS)),
        "NDamageSeeds": str(len(DAMAGE_SEEDS)),
        **{f"Damage{stem(name)}": str(round(100 * f)) for name, (_, f) in DAMAGE.items()},
        **PREREG,
    }
    for cond, n in man["fault_items_by_condition"].items():
        out[f"NFaults{stem(cond)}"] = str(n)
    for cond, n in man["control_items_by_condition"].items():
        out[f"NControls{stem(cond)}"] = str(n)
    for cond, n in man["distinct_planted_clauses_by_condition"].items():
        out[f"NClauses{stem(cond)}"] = str(n)
    for state, n in man["states"].items():
        out[f"NClausesState{state}"] = str(n)
    return out


def sealed_manifest(items: dict[str, Any], cand: dict[str, Any], sealed: dict[str, Any]) -> dict[str, Any]:
    """D49: the candidate-style design manifest rebuilt for the sealed set, from the run's ``items.json`` (the items
    built from the sealed cases; structure only, no replies) and the candidate manifest's per-clause facts."""
    rows = items["items"]
    faults = [i for i in rows if i["role"] == "fault"]
    kept = {str(i["planted"]) for i in faults}
    info = [c for c in cand["replaced_clauses"] if c["clause"] in kept]
    count: dict[str, dict[str, int]] = {"fault": {}, "control": {}}
    for i in rows:
        if i["role"] in count:
            count[i["role"]][i["condition"]] = count[i["role"]].get(i["condition"], 0) + 1
    oc = {c: 0 for c in kept}
    for i in faults:
        if i["condition"] == "S-both" and str(i.get("outcome_changing")) == "True":
            oc[str(i["planted"])] += 1

    def tally(key: str) -> dict[str, int]:
        out: dict[str, int] = {}
        for c in info:
            out[c[key]] = out.get(c[key], 0) + 1
        return dict(sorted(out.items()))

    return {**{k: cand[k] for k in ("pairs_per_clause_target", "pairs_per_clause_cap")},
            "n_cases": sealed["n_cases"], "distinct_replaced_clauses": sealed["distinct_replaced_clauses"],
            "states": tally("state"), "explicit_implicit": tally("explicit_implicit"),
            "clean_correct_answers_C": sum(i["role"] == "c-control" for i in rows),
            "fault_items_by_condition": dict(sorted(count["fault"].items())),
            "control_items_by_condition": dict(sorted(count["control"].items())),
            "distinct_planted_clauses_by_condition": {c: len({str(i["planted"]) for i in faults if i["condition"] == c})
                                                      for c in sorted(count["fault"])},
            "replaced_clauses": [{**c, "S-both:outcome_changing": oc[c["clause"]]} for c in info]}


def annotation_macros(assignment: Path, agreement: Path) -> dict[str, str | None]:
    """D45 shared-subset sizes from the assignment, and raw agreement, kappa and PABAK per scored field once
    friday_t8.sh has written the agreement files ([TBD] before; "--" where kappa is undefined)."""
    with assignment.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    out: dict[str, str | None] = {}
    for sheet, fields in AGREE_FIELDS.items():
        S = sheet.capitalize()
        out[f"NShared{S}"] = str(sum(r["sheet"] == sheet and r["annotator"] == "AB" for r in rows))
        file = agreement / sheet / "agreement.json"
        res = json.loads(file.read_text(encoding="utf-8")) if file.exists() else None
        out[f"NAgreeItems{S}"] = str(res["items"]) if res else None
        for field in fields:
            F = "".join(w.capitalize() for w in field.split("_"))
            r = res["fields"][field] if res else None
            out[f"Agree{S}{F}"] = pct(r["agreement_a_b"]) if r and r["agreement_a_b"] is not None else ("--" if r else None)
            for name, key in (("Kappa", "kappa_a_b"), ("Pabak", "pabak_a_b")):
                out[f"{name}{S}{F}"] = None if r is None else ("--" if r[key] is None else f"{r[key]:.2f}")
    return out


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    """95% Wilson score interval for k of n."""
    p, d = k / n, 1 + z * z / n
    c, h = (p + z * z / (2 * n)) / d, z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return max(0.0, c - h), min(1.0, c + h)


def link_audit_macros(path: Path) -> dict[str, str | None]:
    """D49: the registry audit from 40_data/link_audit_v1/links.csv. The quality sample is a seeded random 20% of
    the links no test item uses, so it estimates the error rate of links the registry asserts (not missing links)."""
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    out: dict[str, str | None] = {"NRegistryLinks": str(len(rows)), "NLinksRegistry": str(len(rows))}
    for frame, name in (("quality_sample", "Sample"), ("test_pair", "TestPair")):
        cell = [r for r in rows if r["checked_as"] == frame]
        out[f"NLinks{name}"] = str(len(cell))
        for oc, mac in (("not_a_link", "NotLink"), ("relation_changed", "RelChanged"), ("confirmed", "Confirmed")):
            k = sum(r["outcome"] == oc for r in cell)
            out[f"Link{name}{mac}"] = f"{k}/{len(cell)}"
            lo, hi = wilson(k, len(cell))
            out[f"Link{name}{mac}Pct"] = pct(k / len(cell))
            out[f"Link{name}{mac}CI"] = f"[{100 * lo:.0f}, {100 * hi:.0f}]\\%"
            out[f"NLinks{name}{'NotALink' if mac == 'NotLink' else mac}"] = str(k)  # the manuscript's names
    out["CINotALinkSample"] = out["LinkSampleNotLinkCI"]
    return out


def scorer_macros(path: Path) -> dict[str, str | None]:
    """D49: the human scorer check (H-16) on the dev replies."""
    if not path.exists():
        return dict.fromkeys(SCORER)
    r = json.loads(path.read_text(encoding="utf-8"))
    conf = r["confusion"]

    def pair(a: str, b: str) -> int:
        return conf.get(f"{a} -> {b}", 0) + conf.get(f"{b} -> {a}", 0)

    return {"ScorerCheckAgreeN": f"{r['agree']} of {r['n']}", "ScorerCheckPctObserved": pct(r["agreement"]),
            "NScorerDisagree": str(r["n"] - r["agree"]), "NScorerClauseReason": str(pair("WRONG_CLAUSE", "WRONG_REASON")),
            "NScorerCatchReason": str(pair("RIGHT_CATCH", "WRONG_REASON"))}


SCORER = ("ScorerCheckAgreeN", "ScorerCheckPctObserved", "NScorerDisagree", "NScorerClauseReason", "NScorerCatchReason")
LINK_NAMES = ("NLinksRegistry", "NLinksSample", "NLinksSampleConfirmed", "NLinksSampleRelChanged", "NLinksSampleNotALink",
              "CINotALinkSample", "NLinksTestPairNotALink", "NLinksTestPairRelChanged")
SEAL_NAMES = ("NDroppedDecisionOnly", "NDroppedBlockingStage", "NControlsCorrect")
FIXED = {"ControlsGatePct": "95", "NPrimaryTestsVFive": str(len(CAPABLE) * (len(NET_PRIMARY) + 2))}  # D49: + Defer, NoRec


AUDIT = ("NCandidateCases", "NDroppedDecision", "NClauseDisputed", "NStrictKept", "NControlsChecked",
         "NControlsFlagged", "PctControlsCorrect", "NRepeatItems", "NRepeatSameFindings", *SEAL_NAMES, *LINK_NAMES, *SCORER, *FIXED)  # D49: set by apply_seal, [TBD] without --sealed


def apply_seal(des: dict[str, str | None], sealed: dict[str, Any]) -> list[str]:
    """Design facts come from the candidate manifest. If the seal (T8) dropped cases or changed the registry, the
    case and clause counts come from TEST_MANIFEST_v3.json and every count the change could alter prints [TBD] until
    the candidate-style manifest is rebuilt for the sealed set. Returns the macros set to [TBD]."""
    des["NTestCases"], des["NClauses"] = str(sealed["n_cases"]), str(sealed["distinct_replaced_clauses"])
    # D49: the annotation audit (the AI-built key against the adjudicated labels)
    n_cand = sealed["n_cases"] + len(sealed["dropped_cases"])
    des["NCandidateCases"], des["NDroppedDecision"] = str(n_cand), str(len(sealed["dropped_cases"]))
    des["NClauseDisputed"], des["NStrictKept"] = str(len(sealed["clause_disputed"])), str(n_cand - len(sealed["strict_dropped"]))
    des["NControlsChecked"], des["NControlsFlagged"] = str(sealed["controls_checked"]), str(len(sealed["controls_flagged"]))
    des["PctControlsCorrect"] = pct(sealed["controls_correct"])
    why = list(sealed["dropped_cases"].values())
    des["NDroppedDecisionOnly"] = str(sum(v.startswith("decision") for v in why))
    des["NDroppedBlockingStage"] = str(sum(v.startswith("blocking stage") for v in why))
    des["NControlsCorrect"] = str(round(sealed["controls_correct"] * sealed["controls_checked"]))
    stale = []
    if sealed["sha256"] != sealed["candidate_sha256"]:
        stale += [k for k in des if k in {"NStates", "NCleanC", "NExplicit", "NImplicit", "NNoLink",
                                          "NOutcomeChangingSBoth", "NRegistryFlagged"}
                  or k.startswith(("NFaults", "NControls", "NClauses")) and k not in {"NClauses", "NControlsAnnotated", *AUDIT}]
    if sealed.get("registry_changes"):
        stale.append("NRegistryFlagged")
    for k in stale:
        des[k] = None
    return sorted(set(stale))


def render(results: dict[str, str | None], design: dict[str, str | None], stage: str) -> str:
    final = stage == "test"
    lines = ["% Generated by 30_code/scripts/make_numbers_v3.py; do not edit by hand.",
             f"\\newcommand{{\\NumbersStage}}{{{stage}}}",
             f"\\newcommand{{\\NumbersFinal}}{{{int(final)}}}"]
    for name, val in design.items():
        lines.append(f"\\newcommand{{\\{name}}}{{{TBD if val is None else val}}}")
    for name, val in results.items():
        shown = TBD if val is None else (val if final else f"\\textcolor{{red}}{{{val}}}")
        lines.append(f"\\newcommand{{\\{name}}}{{{shown}}}")
    bad = [n for n in [*design, *results] if not re.fullmatch(r"[A-Za-z]+", n)]
    if bad:
        raise ValueError(f"macro names must be letters only: {bad[:5]}")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ladder", help="ladder.json from suryabench.analysis.ladder; omit for all-[TBD] results")
    ap.add_argument("--stage", choices=["dev", "test"], required=True)
    ap.add_argument("--manifest", default=str(MANIFEST), help="the candidate-style design manifest")
    ap.add_argument("--sealed", help="TEST_MANIFEST_v3.json from the seal (T8): case and clause counts, drops")
    ap.add_argument("--assignment", default=str(ASSIGNMENT))
    ap.add_argument("--agreement", default=str(AGREEMENT), help="folder with links/ and cases/agreement.json")
    ap.add_argument("--items", help="items.json of the test run: rebuilds the design facts for the sealed set (D49)")
    ap.add_argument("--links", default=str(paths.DATA_DIR / "link_audit_v1" / "links.csv"))
    ap.add_argument("--ladder-s1", help="ladder.json of sensitivity S1 (D49)")
    ap.add_argument("--ladder-s2", help="ladder.json of sensitivity S2 (D49)")
    ap.add_argument("--ladder-all", help="ladder.json over every model's blocks, main and added (robust findings)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    lad = json.loads(paths.resolve(args.ladder).read_text(encoding="utf-8")) if args.ladder else {}
    man = json.loads(paths.resolve(args.manifest).read_text(encoding="utf-8"))
    corpus = json.loads((paths.CORPUS_R3_DIR / "MANIFEST.json").read_text(encoding="utf-8"))
    res = result_macros(lad)
    res |= robust_macros(json.loads(paths.resolve(args.ladder_all).read_text(encoding="utf-8")) if args.ladder_all else {})
    for tag, f in (("SOne", args.ladder_s1), ("STwo", args.ladder_s2)):  # D49: the primary family under S1 and S2
        sens = result_macros(json.loads(paths.resolve(f).read_text(encoding="utf-8")) if f else {})
        res |= {f"{tag}{k}": v for k, v in sens.items() if k.startswith(("DiffNet", "DiffDefer", "DiffNoRec", "CINet",
                                                                           "CIDefer", "CINoRec", "PHolm"))}
    des = design_macros(man, corpus) | annotation_macros(paths.resolve(args.assignment), paths.resolve(args.agreement))
    des |= dict.fromkeys(AUDIT)
    des |= link_audit_macros(Path(paths.resolve(args.links)))
    rep = paths.RESULTS_DIR / "probe_test_v3_repeat" / "agreement.json"  # D49 exploratory determinism check
    r = json.loads(rep.read_text(encoding="utf-8")).get("qwen2.5_14b", {}) if rep.exists() else {}
    des |= {"NRepeatItems": str(r["items"]) if r else None, "NRepeatSameFindings": str(r["same_findings"]) if r else None}
    des |= scorer_macros(paths.RESULTS_DIR / "scorer_check" / "scorer_check_report_human.json") | FIXED
    if args.sealed and args.items:
        sealed = json.loads(paths.resolve(args.sealed).read_text(encoding="utf-8"))
        rebuilt = sealed_manifest(json.loads(paths.resolve(args.items).read_text(encoding="utf-8")), man, sealed)
        des |= design_macros(rebuilt, corpus)
        apply_seal(des, {**sealed, "sha256": sealed["candidate_sha256"], "registry_changes": []})  # audit macros only
    elif args.sealed:
        stale = apply_seal(des, json.loads(paths.resolve(args.sealed).read_text(encoding="utf-8")))
        if stale:
            print(f"the seal changed the test set: {len(stale)} design macros print [TBD] until the design manifest "
                  f"is rebuilt for the sealed set: {', '.join(stale)}")
    out = Path(paths.resolve(args.out))
    out.write_text(render(res, des, args.stage), encoding="utf-8", newline="\n")
    filled = sum(v is not None for v in res.values())
    print(f"{len(des)} design + {len(res)} result macros ({filled} filled, stage {args.stage}) -> {out}")


if __name__ == "__main__":
    main()
