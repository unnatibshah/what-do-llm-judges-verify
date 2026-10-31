"""make_numbers_v3.py: macro names are letters only and a missing value prints [TBD] (T7)."""

import importlib.util

from suryabench import paths

_spec = importlib.util.spec_from_file_location("make_numbers_v3", paths.CODE_DIR / "scripts" / "make_numbers_v3.py")
assert _spec and _spec.loader
mn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mn)


def test_stem() -> None:
    assert mn.stem("R4'-R1") == "RFourPMinusROne"
    assert mn.stem("R2-cc") == "RTwoCC"
    assert mn.stem("R5-drop25") == "RFiveDropTwentyFive"


def test_missing_values_are_tbd_and_dev_values_red() -> None:
    lad = {"models": {"qwen2.5:14b": {"R2": {"catch": {"mean": 0.5, "k": 1, "n": 2}}}}, "contrasts": {}}
    tex = mn.render(mn.result_macros(lad), {}, "dev")
    assert r"\newcommand{\CatchQwenFourteenRTwo}{\textcolor{red}{50\%}}" in tex
    assert r"\newcommand{\CatchGemmaRTwo}{\textbf{[TBD]}}" in tex
    assert r"\newcommand{\NumbersFinal}{0}" in tex


def test_annotation_macros(tmp_path) -> None:  # type: ignore[no-untyped-def]
    d = mn.annotation_macros(mn.ASSIGNMENT, tmp_path)  # no agreement files yet
    assert d["NSharedLinks"] == "15" and d["NSharedCases"] == "20"
    assert d["KappaCasesDecision"] is None and d["AgreeLinksRelation"] is None
    (tmp_path / "cases").mkdir()
    fields = {f: {"agreement_a_b": 0.9, "kappa_a_b": 0.8, "pabak_a_b": 0.8} for f in mn.AGREE_FIELDS["cases"]}
    fields["blocking_stage"]["kappa_a_b"] = None
    (tmp_path / "cases" / "agreement.json").write_text(mn.json.dumps({"items": 20, "fields": fields}), encoding="utf-8")
    d = mn.annotation_macros(mn.ASSIGNMENT, tmp_path)
    assert d["NAgreeItemsCases"] == "20" and d["AgreeCasesDecision"] == "90\\%" and d["KappaCasesDecision"] == "0.80"
    assert d["KappaCasesBlockingStage"] == "--" and d["PabakLinksRelation"] is None
    assert all(mn.re.fullmatch(r"[A-Za-z]+", k) for k in d)


def test_seal_overrides_counts_and_blanks_what_a_drop_changes() -> None:
    des = {"NTestCases": "60", "NClauses": "15", "NStates": "6", "NFaultsSBoth": "56", "NClausesStateDL": "4",
           "NClausesSBoth": "15", "NControlsAnnotated": "40", "NPairsCap": "6", "NRegistryFlagged": "12"}
    same = {"n_cases": 60, "distinct_replaced_clauses": 15, "sha256": "a", "candidate_sha256": "a", "dropped_cases": {},
            "clause_disputed": {}, "strict_dropped": [], "controls_checked": 40, "controls_flagged": {},
            "controls_correct": 1.0}
    assert mn.apply_seal(dict(des), same) == []
    d = dict(des)
    stale = mn.apply_seal(d, {**same, "n_cases": 55, "distinct_replaced_clauses": 14, "sha256": "b",
                              "dropped_cases": dict.fromkeys("abcde", "decision"), "clause_disputed": {"f": "x"},
                              "strict_dropped": [*"abcdef"], "controls_flagged": {"g": "INCOMPLETE"},
                              "controls_correct": 0.575})
    assert (d["NCandidateCases"], d["NDroppedDecision"], d["NClauseDisputed"], d["NStrictKept"]) == ("60", "5", "1", "54")
    assert (d["NControlsFlagged"], d["PctControlsCorrect"]) == ("1", "57\\%")
    assert d["NTestCases"] == "55" and d["NClauses"] == "14" and d["NPairsCap"] == "6" and d["NControlsAnnotated"] == "40"
    assert set(stale) == {"NStates", "NFaultsSBoth", "NClausesStateDL", "NClausesSBoth", "NRegistryFlagged"}
    d = dict(des)
    assert mn.apply_seal(d, {**same, "registry_changes": ["L004 removed"]}) == ["NRegistryFlagged"]


def test_d47_macros_cover_the_pending_file() -> None:
    """Every macro numbers_pending.tex holds for the paper is emitted, so a generated numbers.tex supersedes it."""
    pending = (paths.ROOT / "60_paper_drafts" / "paper_v3" / "numbers_pending.tex").read_text(encoding="utf-8")
    wanted = set(mn.re.findall(r"\\providecommand\{\\([A-Za-z]+)\}", pending))
    man = mn.json.loads(mn.MANIFEST.read_text(encoding="utf-8"))
    corpus = mn.json.loads((paths.CORPUS_R3_DIR / "MANIFEST.json").read_text(encoding="utf-8"))
    emitted = set(mn.result_macros({})) | set(mn.design_macros(man, corpus)) | set(mn.AUDIT)
    assert wanted and wanted <= emitted, sorted(wanted - emitted)[:5]


def test_d47_values() -> None:
    q = "qwen2.5:14b"
    lad = {"models": {q: {"R2": {"catch_any": {"mean": 0.9}, "false_alarm_validity": {"mean": 0.1}}}},
           "discrimination": {f"R4 drop50 @ {q}": {"mean_diff": 0.25}},
           "contrasts": {f"Net-drop50 @ {q}": {"mean_diff": -0.5, "ci95": [-0.7, -0.3], "p_holm": 0.004},
                         f"Defer @ {q}": {"mean_diff": 0.4, "ci95": None}},
           "deference": {q: {"clauses": 11, "r2_catch": 0.6, "r4_damage_catch": 0.2}},
           "spurious": {q: {"n": 7, "r4": 5, "r2": 1}}}
    d = mn.result_macros(lad)
    assert d["DiscRFourDropFiftyQwenFourteen"] == "+25" and d["DiffNetDropFiftyQwenFourteen"] == "$-$50"
    assert d["CINetDropFiftyQwenFourteen"] == "[$-$70, $-$30]" and d["PHolmNetDropFiftyQwenFourteen"] == "0.004"
    assert d["DiffDeferQwenFourteen"] == "+40" and d["CIDeferQwenFourteen"] == "--" and d["PHolmDeferQwenFourteen"] is None
    assert d["NDroppedClausesQwenFourteen"] == "11" and d["CatchDroppedQwenFourteen"] == "20\\%"
    assert d["FASpuriousMarkedQwenFourteen"] == "5/7" and d["OwnFASpuriousMarkedQwenFourteen"] == "1/7"
    assert d["ScAnyCatchQwenFourteenRTwo"] == "90\\%" and d["ScReasonFAQwenFourteenRTwo"] == "10\\%"
    assert d["DiffNetIntactGemma"] is None


def test_link_audit_and_wilson() -> None:  # D49
    lo, hi = mn.wilson(5, 34)
    assert 0.06 < lo < 0.07 and 0.30 < hi < 0.31  # textbook Wilson interval for 5/34
    d = mn.link_audit_macros(paths.DATA_DIR / "link_audit_v1" / "links.csv")
    assert d["NRegistryLinks"] == "186" and d["NLinksSample"] == "34" and d["NLinksTestPair"] == "18"
    assert d["LinkSampleNotLink"] == "5/34" and d["LinkTestPairNotLink"] == "1/18"


def test_sealed_manifest_from_items() -> None:  # D49
    cand = {"pairs_per_clause_target": 4, "pairs_per_clause_cap": 6, "replaced_clauses": [
        {"clause": "A", "state": "DL", "explicit_implicit": "EXPLICIT", "registry_flags_superseded": "2/2"},
        {"clause": "B", "state": "UP", "explicit_implicit": "IMPLICIT", "registry_flags_superseded": "0/1"},
        {"clause": "Z", "state": "KA", "explicit_implicit": "EXPLICIT", "registry_flags_superseded": "1/1"}]}
    items = {"items": [{"role": "fault", "condition": "S-both", "planted": "A", "outcome_changing": True},
                       {"role": "control", "condition": "S-both", "planted": "A"},
                       {"role": "fault", "condition": "S-swap", "planted": "B", "outcome_changing": False},
                       {"role": "c-control", "condition": "C", "planted": None}]}
    m = mn.sealed_manifest(items, cand, {"n_cases": 2, "distinct_replaced_clauses": 2})
    assert m["states"] == {"DL": 1, "UP": 1} and m["explicit_implicit"] == {"EXPLICIT": 1, "IMPLICIT": 1}
    assert m["fault_items_by_condition"] == {"S-both": 1, "S-swap": 1} and m["clean_correct_answers_C"] == 1
    assert m["replaced_clauses"][0]["S-both:outcome_changing"] == 1
    d = mn.design_macros(m, {"documents": []})
    assert d["NFaultsSBoth"] == "1" and d["NClausesStateUP"] == "1" and d["NRegistryFlagged"] == "1"
