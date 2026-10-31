r"""T11 / U6: write ``80_review/NUMBER-TRACE-v3.csv``: every macro in ``numbers.tex`` with its value, the file it comes
from and the key inside that file, and a blank ``checked_by`` column for the person who traces it (Aum, U6).

The map mirrors ``make_numbers_v3.py`` (same loops, same names). A macro the map does not know fails the script, so
the trace cannot fall behind the generator.

    python 30_code/scripts/make_number_trace.py --ladder 50_analysis/results/ladder_test_v3/ladder.json \
        --manifest 40_data/benchmark/TEST_MANIFEST_v3.json
"""

import argparse
import csv
import importlib.util
import json
import re
from pathlib import Path

from suryabench import paths

_spec = importlib.util.spec_from_file_location("make_numbers_v3", paths.CODE_DIR / "scripts" / "make_numbers_v3.py")
assert _spec and _spec.loader
mn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mn)

NUMBERS = paths.ROOT / "60_paper_drafts" / "paper_v3" / "numbers.tex"
OUT = paths.ROOT / "80_review" / "NUMBER-TRACE-v3.csv"
GEN = "30_code/scripts/make_numbers_v3.py"
CORPUS = "40_data/corpus_r3/MANIFEST.json"
DESIGN = {"NTestCases": "n_cases", "NClauses": "distinct_replaced_clauses", "NStates": "len(states)",
          "NPairsPerClause": "pairs_per_clause_target", "NPairsCap": "pairs_per_clause_cap",
          "NCleanC": "clean_correct_answers_C", "NExplicit": "explicit_implicit.EXPLICIT",
          "NImplicit": "explicit_implicit.IMPLICIT", "NNoLink": "explicit_implicit.NONE",
          "NRegistryFlagged": "count of replaced_clauses[].registry_flags_superseded > 0",
          "NOutcomeChangingSBoth": "sum of replaced_clauses[].S-both:outcome_changing"}
CODE = {"NumbersStage": (GEN, "--stage"), "NumbersFinal": (GEN, "--stage test"),
        "NCorpusDocs": (CORPUS, "len(documents)"), "NCorpusJurisdictions": (CORPUS, "distinct documents[].jurisdiction.code"),
        "NPanelModels": (GEN, "PANEL minus the secondary model (prereg section 4)"),
        "NCapable": ("30_code/src/suryabench/analysis/ladder.py", "CAPABLE"),
        "NPrimaryTests": ("30_code/src/suryabench/analysis/ladder.py", "CAPABLE x primary CONTRASTS (prereg section 6)"),
        "NDamageSeeds": ("30_code/src/suryabench/arms/verifier_probe.py", "DAMAGE_SEEDS")}
CONTRAST_FIELDS = {"Diff": "mean_diff", "CI": "ci95", "P": "signflip_p", "PHolm": "p_holm", "Clauses": "clauses"}


def source_map(ladder: str, manifest: str, agreement: str) -> dict[str, tuple[str, str]]:
    src: dict[str, tuple[str, str]] = dict(CODE)
    src |= {k: (manifest, v) for k, v in DESIGN.items()}
    src |= {k: ("20_method/PREREGISTRATION_v3.md", f"PREREG table in {GEN}") for k in mn.PREREG}
    src |= {f"Damage{mn.stem(d)}": ("30_code/src/suryabench/arms/verifier_probe.py", f"DAMAGE[{d}]") for d in mn.DAMAGE}
    for model, m in mn.PANEL.items():
        for rung in mn.RUNG_ORDER + mn.DAMAGED_RUNGS:
            r, at = mn.stem(rung), f"models[{model}][{rung}]"
            for name, key in mn.METRICS.items():
                src[f"{name}{m}{r}"] = (ladder, f"{at}.{key}.mean")
                src[f"{name}KN{m}{r}"] = (ladder, f"{at}.{key}.k / .n")
            src[f"Misnamed{m}{r}"] = (ladder, f"{at}.misnamed.k / .n")
            for name, key in (("MisnamedKN", "misnamed"), ("InvalidKN", "invalid"),
                              ("CantConfirmCorrectKN", "cant_confirm_correct")):
                src[f"{name}{m}{r}"] = (ladder, f"{at}.{key}.k / .n")
        names = [(n, f"{n} @ {model}") for n in mn.CONTRASTS]
        names += [(f"Gap-{w}", f"(R4-R2) {model} - {w}") for w in mn.WEAK if model in mn.CAPABLE]
        for label, key in names:
            k = mn.stem(label.replace(mn.WEAK[0], "Weak")) + m
            src |= {f"{p}{k}": (ladder, f"contrasts[{key}].{f}") for p, f in CONTRAST_FIELDS.items()}
    for sheet, fields in mn.AGREE_FIELDS.items():
        S, file = sheet.capitalize(), f"{agreement}/{sheet}/agreement.json"
        src[f"NShared{S}"] = ("20_method/annotation/ASSIGNMENT_D45.csv", f"rows with sheet={sheet}, annotator=AB")
        src[f"NAgreeItems{S}"] = (file, "items")
        for field in fields:
            F = "".join(w.capitalize() for w in field.split("_"))
            for p, key in (("Agree", "agreement_a_b"), ("Kappa", "kappa_a_b"), ("Pabak", "pabak_a_b")):
                src[f"{p}{S}{F}"] = (file, f"fields.{field}.{key}")
    return src


def by_prefix(name: str, manifest: str) -> tuple[str, str] | None:
    """The per-condition and per-state design macros, named from the manifest's own keys."""
    man = json.loads(paths.resolve(manifest).read_text(encoding="utf-8"))
    for prefix, key in (("NClausesState", "states"), ("NFaults", "fault_items_by_condition"),
                        ("NControls", "control_items_by_condition"), ("NClauses", "distinct_planted_clauses_by_condition")):
        found = [k for k in man.get(key, {}) if name == prefix + mn.stem(k)]
        if found:
            return manifest, f"{key}[{found[0]}]"
    return None


SEALED = "40_data/benchmark/TEST_MANIFEST_v3.json"
LINKS = "40_data/link_audit_v1/links.csv"
SCORER = "50_analysis/results/scorer_check/scorer_check_report_human.json"
REPEAT = "50_analysis/results/probe_test_v3_repeat/agreement.json"
SEAL_KEYS = {"NCandidateCases": "n_cases + len(dropped_cases)", "NDroppedDecision": "len(dropped_cases)",
             "NDroppedDecisionOnly": "dropped_cases[] starting 'decision'",
             "NDroppedBlockingStage": "dropped_cases[] starting 'blocking stage'",
             "NClauseDisputed": "len(clause_disputed)", "NStrictKept": "n_cases + len(dropped_cases) - len(strict_dropped)",
             "NControlsChecked": "controls_checked", "NControlsFlagged": "len(controls_flagged)",
             "PctControlsCorrect": "controls_correct", "NControlsCorrect": "controls_correct x controls_checked"}
FIXED_KEYS = {"ControlsGatePct": ("20_method/PREREGISTRATION_v3.md", "section 3: 95% controls gate"),
              "NPrimaryTestsVFour": ("20_method/PREREGISTRATION_v3_AMENDMENT_1_DRAFT.md", "section 3: 8 tests"),
              "NPrimaryTestsVFive": ("20_method/PREREGISTRATION_v3_AMENDMENT_2_DRAFT.md", "section 5b: 10 tests"),
              "NDamageSeedsCapable": ("30_code/src/suryabench/arms/verifier_probe.py", "DAMAGE_SEEDS")}


def rule_source(name: str, ladder: str) -> tuple[str, str] | None:
    """D48/D49 macro families, named as make_numbers_v3.py names them."""
    if name.startswith("Rob"):
        rob = {m: model for model, m in mn.ROB_MODELS.items()}
        mm = re.fullmatch(r"Rob([A-Za-z]+?)(" + "|".join(sorted(rob, key=len, reverse=True)) + r")(RTwo|RFour)?", name)
        if mm:
            all_file = ladder.replace("ladder_test_v3/", "ladder_test_v3_exploratory/")
            key = {"Catch": "catch_sboth", "CatchPct": "catch_sboth", "Any": "catch_any", "Flagged": "false_alarm_sboth"}
            g = {"RTwo": "R2", "RFour": "R4"}.get(mm.group(3) or "")
            if mm.group(1) in key and g:
                return all_file, f"models[{rob[mm.group(2)]}][{g}].{key[mm.group(1)]}.k / .n"
            other = {"NonValidity": f"alarm_reasons[R4 @ {rob[mm.group(2)]}] (non-validity / all)",
                     "Gained": f"recovery[drop50 @ {rob[mm.group(2)]}].gained",
                     "Lost": f"recovery[drop50 @ {rob[mm.group(2)]}].lost",
                     "DeferFrom": f"deference[{rob[mm.group(2)]}].r2_catch",
                     "DeferTo": f"deference[{rob[mm.group(2)]}].r4_damage_catch",
                     "DeferClauses": f"deference[{rob[mm.group(2)]}].clauses"}
            if mm.group(1) in other:
                return all_file, other[mm.group(1)]
    models = {m: model for model, m in mn.PANEL.items()}
    states = {mn.stem(st): st for st in mn.STATES}
    rungs = {mn.stem(g): g for g in mn.RUNG_ORDER + mn.DAMAGED_RUNGS}
    file = ladder
    for tag, sub in (("SOne", "_S1"), ("STwo", "_S2")):
        if name.startswith(tag):
            name, file = name.removeprefix(tag), ladder.replace("ladder_test_v3/", f"ladder_test_v3{sub}/")
    mm = re.fullmatch(r"(.*?)(" + "|".join(sorted(models, key=len, reverse=True)) + r")(.*)", name)
    if mm:
        head, model, tail = mm.group(1), models[mm.group(2)], mm.group(3)
        rc = re.fullmatch(r"Rec(Gained|Lost|Pairs)(Intact|DropFifty)", head)
        if rc and not tail:
            return file, f"recovery[{states[rc.group(2)]} @ {model}].{rc.group(1).lower()}"
        ins = re.fullmatch(r"Instr(P|N)(\w+)", head)
        if ins and not tail:
            return file, f"by_instrument[Net-{states[ins.group(2)]} @ {model}]." + ("signflip_p" if ins.group(1) == "P" else "instruments")
        if head == "NSpuriousClauses" and not tail:
            return file, f"spurious[{model}].clauses"
        v = re.fullmatch(r"(Diff|CI|PHolm)NetV(\w+)", head)
        if v and not tail:
            return file, f"q1_validity[Net-{states[v.group(2)]} @ {model}].{CONTRAST_FIELDS[v.group(1)]}"
        c = re.fullmatch(r"(Diff|CI|PHolm)(Net(\w+)|Defer|NoRec)", head)
        if c and not tail:
            label = f"Net-{states[c.group(3)]}" if c.group(3) else c.group(2)
            return file, f"contrasts[{label} @ {model}].{CONTRAST_FIELDS[c.group(1)]}"
        d = re.fullmatch(r"Disc(RFourn|RFour|RFive|RTwo)(\w*)", head)
        if d and not tail:
            rung = {"RFourn": "R4n", "RFour": "R4", "RFive": "R5", "RTwo": "R2"}[d.group(1)]
            key = f"R2 @ {model}" if rung == "R2" else f"{rung} {states[d.group(2)]} @ {model}"
            return file, f"discrimination[{key}].mean_diff"
        simple = {"CatchDropped": f"deference[{model}].r4_damage_catch", "OwnCatchDropped": f"deference[{model}].r2_catch",
                  "NDroppedClauses": f"deference[{model}].clauses", "CatchDroppedRFour": f"no_record[{model}].r4_damage_catch",
                  "CatchDroppedRFourn": f"no_record[{model}].r4n_damage_catch",
                  "CatchNoRecDropped": f"no_record[{model}].r4n_damage_catch", "NNoRecClauses": f"no_record[{model}].clauses",
                  "FASpuriousMarked": f"spurious[{model}].r4 / .n", "OwnFASpuriousMarked": f"spurious[{model}].r2 / .n",
                  "KNSpuriousMarked": f"spurious[{model}].n"}
        if head in simple and not tail:
            return file, simple[head]
        sc = {"ScAnyCatch": "catch_any", "ScClauseCatch": "catch_clause", "ScAnyFA": "false_alarm_matched",
              "ScReasonFA": "false_alarm_validity"}
        if head in sc and tail in rungs:
            return file, f"models[{model}][{rungs[tail]}].{sc[head]}.mean"
        fam = {"RFourN": "R4n", "RFourNDropFifty": "R4n-drop50"}
        if head == "FAM" and tail in fam:
            return file, f"models[{model}][{fam[tail]}].false_alarm_matched.mean"
    if name in SEAL_KEYS:
        return SEALED, SEAL_KEYS[name]
    if name in FIXED_KEYS:
        return FIXED_KEYS[name]
    if name in ("NRepeatItems", "NRepeatSameFindings"):
        return REPEAT, "qwen2.5_14b." + ("items" if name == "NRepeatItems" else "same_findings")
    if name.startswith(("Link", "NLinks", "CINotALink")) or name == "NRegistryLinks":
        return LINKS, "rows by checked_as and outcome (make_numbers_v3.link_audit_macros)"
    if name.startswith(("ScorerCheck", "NScorer")):
        return SCORER, "agree, n, confusion (make_numbers_v3.scorer_macros)"
    return None


def trace(numbers: Path, ladder: str, manifest: str, agreement: str) -> list[dict[str, str]]:
    src = source_map(ladder, manifest, agreement)
    rows = []
    for name, val in re.findall(r"\\newcommand\{\\([A-Za-z]+)\}\{(.*)\}$", numbers.read_text(encoding="utf-8"), re.M):
        val = re.sub(r"^\\textcolor\{red\}\{(.*)\}$", r"\1", val)
        file, key = src.get(name) or by_prefix(name, manifest) or rule_source(name, ladder) or ("UNMAPPED", "")
        for tag, sub in (("SOne", "_S1"), ("STwo", "_S2")):  # D49 sensitivity copies of the ladder contrasts
            if file == "UNMAPPED" and name.startswith(tag) and name.removeprefix(tag) in src:
                file, key = src[name.removeprefix(tag)]
                file = file.replace("ladder_test_v3/", f"ladder_test_v3{sub}/")
        rows.append({"macro": name, "value": val, "source_file": file, "key": key, "checked_by": ""})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--numbers", default=str(NUMBERS))
    ap.add_argument("--ladder", default="50_analysis/results/ladder_test_v3/ladder.json")
    ap.add_argument("--manifest", default=str(mn.MANIFEST.relative_to(paths.ROOT)))
    ap.add_argument("--agreement", default=str(mn.AGREEMENT.relative_to(paths.ROOT)))
    ap.add_argument("--items", help="D49: items.json the design facts were rebuilt from (make_numbers_v3 --items)")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    rows = trace(Path(args.numbers), args.ladder, args.manifest, args.agreement)
    if args.items:  # design facts of the sealed set: rebuilt from the run's items plus the candidate's per-clause facts
        for r in rows:
            if r["source_file"] == args.manifest and r["macro"] not in ("NPairsPerClause", "NPairsCap"):
                r["source_file"], r["key"] = f"{args.items} + {args.manifest}", f"make_numbers_v3.sealed_manifest: {r['key']}"
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    missing = [r["macro"] for r in rows if r["source_file"] == "UNMAPPED"]
    print(f"{len(rows)} macros -> {args.out}")
    if missing:
        raise SystemExit(f"{len(missing)} macros have no mapped source (update make_number_trace.py): {missing[:10]}")


if __name__ == "__main__":
    main()
