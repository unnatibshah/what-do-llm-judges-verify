"""T3: integrity of the v3 candidate's probe items and of every ladder prompt built from them. Structure-only read
of 40_data/benchmark/test_cases_v3_CANDIDATE.json: pairs are built and prompts rendered with the model call stubbed;
no model is run and nothing is scored."""

import json
import re
import sys
from collections import Counter
from typing import Any

import pytest

from suryabench.arms import verifier_probe as vp
from suryabench.arms import verify_reflect, verify_shared
from suryabench.arms.verify_independent import amendment_quotes, resolve_citation
from suryabench.arms.verify_shared import generator_block
from suryabench.cases.schema import BenchmarkCase
from suryabench.eval.runner import BenchmarkRunner
from suryabench.paths import BENCHMARK_DIR, CODE_DIR

sys.path.insert(0, str(CODE_DIR / "scripts"))
from count_ladder_items import ProbeWorld  # noqa: E402

LADDER = ("validity-metaoff", "validity", "validity-amendquote", "validity-regstatus", "validity-cc",
          "validity-cc-metaoff", "validity-regstatus-drop50-s0", "validity-regstatus-spurious10-s0")


@pytest.fixture(scope="module")
def v3() -> dict[str, Any]:
    world = ProbeWorld()
    cases = [BenchmarkCase.model_validate(c) for c in
             json.loads((BENCHMARK_DIR / "test_cases_v3_CANDIDATE.json").read_text(encoding="utf-8"))]
    items, _ = vp.build_items(cases, world.graph, world.predicates, world.retriever)
    return {"world": world, "cases": {c.case_id: c for c in cases}, "items": items}


def test_no_duplicate_items_one_condition_each(v3: dict[str, Any]) -> None:
    items = v3["items"]
    assert len({i.item_id for i in items}) == len(items)
    assert all(n == 1 for n in Counter((i.case_id, i.condition, i.role) for i in items).values())
    for i in items:
        assert i.pair_id == f"{i.case_id}#{i.condition}" and i.item_id == f"{i.pair_id}#{i.role}"
        assert i.condition in vp.CONDITIONS and (i.role == "c-control") == (i.condition == "C")


def test_pairs_differ_only_in_clause_and_decision(v3: dict[str, Any]) -> None:
    by = {(i.pair_id, i.role): i for i in v3["items"]}
    pairs = [(by[(p, "fault")], by[(p, "control")]) for p, r in by if r == "fault" and (p, "control") in by]
    assert pairs
    for f, c in pairs:
        assert f.evidence_ids == c.evidence_ids and f.case_id == c.case_id and f.planted == c.planted
        assert f.planted in f.answer.cited_rules and f.planted not in c.answer.cited_rules
        if f.condition == "S-swap":  # D35: the control cannot cite the removed anchor
            assert set(c.answer.cited_rules) == set(f.answer.cited_rules) - {f.planted}
        else:
            diff = [k for k, (a, b) in enumerate(zip(f.answer.cited_rules, c.answer.cited_rules, strict=True)) if a != b]
            assert len(diff) == 1 and f.answer.cited_rules[diff[0]] == f.planted
        if not f.outcome_changing:
            assert (f.answer.decision, f.answer.blocking_stage) == (c.answer.decision, c.answer.blocking_stage)
        changed = {a.split(":")[0] for a, b in zip(generator_block(f.answer).splitlines(),
                                                   generator_block(c.answer).splitlines(), strict=True) if a != b}
        assert changed <= {"Decision", "Blocking stage", "Cited rules", "Subsidy", "Root cause"}


def test_no_gold_or_role_word_in_any_prompt(v3: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    prompts: list[str] = []

    def fake(prompt: str, **_: Any) -> tuple[dict[str, Any], int, int]:
        prompts.append(prompt)
        return {"verdict": "PASS", "risk": 0.1, "findings": []}, 1, 1

    monkeypatch.setattr(verify_shared, "call_llm_json", fake)
    monkeypatch.setattr(verify_reflect, "call_llm_json", fake)
    w = v3["world"]
    one = {}
    for i in v3["items"]:  # one item per (rule group, condition, role): every group and pair shape is covered
        one.setdefault((i.cluster, i.condition, i.role), i)
    items = list(one.values())
    ctx = vp.ProbeContext(cases={k: BenchmarkRunner._unlabelled(c) for k, c in v3["cases"].items()},
                          texts=vp.evidence_texts(items, w.graph, w.retriever), retriever=w.retriever,
                          registries={"reg-real": w.registry, **vp.damaged_registries(w.registry)},
                          labels={d: f"SRC-{n:04d}" for n, d in enumerate(sorted(w.retriever.doc_titles))})
    for config in LADDER:  # _unlabelled hides every gold field behind a tripwire; reading one raises
        for it in items:
            prompts.clear()
            vp.verify_item(it, config, "probe-test-model", ctx)
            assert prompts, (config, it.item_id)
            p = prompts[0]
            # the regulations' own words may say "fault" or "control"; everything the probe writes may not
            head, _, rest = p.partition("[REGULATORY EVIDENCE]")
            task = verify_shared.TASKS[vp.CONFIGS[config][1]]
            low = (head + task + rest.partition(task)[2]).lower()
            case = v3["cases"][it.case_id]
            assert case.expected_answer is None or case.expected_answer.root_cause is None \
                or case.expected_answer.root_cause not in p
            hit = re.search(r".{40}(?:\bfault\b|\bcontrol\b|planted|outcome_changing|exp-|basis-only).{40}", low, re.S)
            assert not hit, (config, it.item_id, hit.group(0) if hit else "")
            assert it.case_id not in p  # opaque ids never reach the verifier


def test_r3_quotes_come_from_the_registry(v3: dict[str, Any]) -> None:
    w = v3["world"]
    raw = json.loads(w.registry_file.read_text(encoding="utf-8"))["edges"]
    by_from: dict[str, set[str]] = {}
    for e in raw:
        by_from.setdefault(e["from_node"], set()).add(" ".join(str(e.get("evidence_quote") or "").split()))
    seen = 0
    for it in v3["items"]:
        for line in amendment_quotes(it.answer, w.registry, w.retriever):
            cited, quote = re.fullmatch(r'- (.+?): "(.*)"', line).groups()  # type: ignore[union-attr]
            assert cited in it.answer.cited_rules
            nodes = resolve_citation(cited, w.registry, w.retriever) or []
            assert any(quote in by_from.get(n, set()) for n in nodes), line
            seen += 1
    assert seen
