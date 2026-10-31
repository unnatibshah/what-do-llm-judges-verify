"""D33 verifier probe: item construction, isolation, scoring and the summary. No model is run."""

import hashlib
import json
import re
import sys
from typing import Any

import pytest

from suryabench.analysis import probe
from suryabench.applicability.schema import ApplicabilityPredicate
from suryabench.arms import verifier_probe as vp
from suryabench.arms import verify_reflect, verify_shared
from suryabench.arms.controlled_exposure import cluster_anchor
from suryabench.arms.verify_independent import (
    Registry,
    amendment_quotes,
    load_registry,
    noisy_registry,
)
from suryabench.arms.verify_shared import VerifierResult, generator_block
from suryabench.cases.schema import BenchmarkCase
from suryabench.corpus.manifest import load_manifest
from suryabench.eval.failure_classifier import FailureClassifier
from suryabench.eval.runner import BenchmarkRunner
from suryabench.gate0.retriever import LocalRetriever, build_corpus_chunks, map_chunks_to_clauses
from suryabench.graph.schema import SupersessionGraph
from suryabench.paths import BENCHMARK_DIR, CODE_DIR, CORPUS_R3_DIR, REGISTRIES_DIR

sys.path.insert(0, str(CODE_DIR / "scripts"))
REAL_REGISTRY_R3 = REGISTRIES_DIR / "registry_real_v2_r3.json"

PROBE = "probe-test-model"


@pytest.fixture(scope="module")
def env() -> dict[str, Any]:
    graph = SupersessionGraph.model_validate(
        json.loads((CORPUS_R3_DIR / "graph" / "supersession.json").read_text(encoding="utf-8")))
    manifest = load_manifest(CORPUS_R3_DIR / "MANIFEST.json")
    chunks = build_corpus_chunks(CORPUS_R3_DIR / "text")
    r = LocalRetriever(chunks)  # unindexed: lexical fallback, no Ollama
    r.chunk_clauses = map_chunks_to_clauses(chunks, graph.nodes.values(), CORPUS_R3_DIR / "text")
    r.doc_titles = {d.doc_id: d.title for d in manifest.documents}
    r.doc_meta = {d.doc_id: {"issuer": str(d.issuer or "unknown"), "jurisdiction": str(d.jurisdiction.code.value),
                             "effective_date": str(d.effective_date or "unknown")} for d in manifest.documents}
    preds = [ApplicabilityPredicate.model_validate(p)
             for p in json.loads((CORPUS_R3_DIR / "graph" / "applicability.json").read_text(encoding="utf-8"))]
    cases = [BenchmarkCase.model_validate(c)
             for c in json.loads((BENCHMARK_DIR / "dev_cases_v2.json").read_text(encoding="utf-8"))]
    items, skips = vp.build_items(cases, graph, preds, r)
    return {"graph": graph, "retriever": r, "cases": {c.case_id: c for c in cases}, "items": items, "skips": skips,
            "preds": preds,
            "classifier": FailureClassifier(graph, manifest, r.chunk_clauses)}


def _pairs(items: list[vp.ProbeItem]) -> list[tuple[vp.ProbeItem, vp.ProbeItem]]:
    by = {(i.pair_id, i.role): i for i in items}
    return [(by[(p, "fault")], by[(p, "control")]) for p, r in by if r == "fault" and (p, "control") in by]


def test_dev_item_counts(env: dict[str, Any]) -> None:
    roles = [(i.condition, i.role) for i in env["items"]]
    assert roles.count(("C", "c-control")) == 54  # 60 dev cases minus 6 ABSTAIN
    for cond in ("S-both", "J", "A"):
        assert roles.count((cond, "fault")) == roles.count((cond, "control")) > 0
    # D35: an S-swap control exists only where a decisive clause other than the removed anchor is shown
    assert roles.count(("S-swap", "fault")) > 0
    assert roles.count(("S-swap", "control")) < roles.count(("S-swap", "fault"))
    assert all(k.endswith("#S-swap#control") for k in env["skips"] if k.endswith("#control"))


def _shown(item: vp.ProbeItem, r: LocalRetriever) -> set[str]:
    return set().union(*(r.chunk_clauses.get(i, {i}) for i in item.evidence_ids))


def test_controls_cite_only_their_evidence(env: dict[str, Any]) -> None:
    """D35: every control (and every fault) cites only clauses its own evidence shows, on dev and on the v3 candidate
    (structure only: pairs are built, no model is run)."""
    cand = [BenchmarkCase.model_validate(c)
            for c in json.loads((BENCHMARK_DIR / "test_cases_v3_CANDIDATE.json").read_text(encoding="utf-8"))]
    v3, _ = vp.build_items(cand, env["graph"], env["preds"], env["retriever"])
    cases = {**env["cases"], **{c.case_id: c for c in cand}}
    for items in (env["items"], v3):
        assert any(i.condition == "S-swap" and i.role == "control" for i in items)
        for it in items:
            assert it.answer.cited_rules and set(it.answer.cited_rules) <= _shown(it, env["retriever"]), it.item_id
            if it.condition == "S-swap":
                assert cluster_anchor(cases[it.case_id], env["graph"]) not in it.answer.cited_rules


def test_pairs_differ_only_in_basis(env: dict[str, Any]) -> None:
    for f, c in _pairs(env["items"]):
        if f.condition == "S-swap":  # D35: the control cannot cite the anchor S-swap removed
            assert f.evidence_ids == c.evidence_ids and f.planted in f.answer.cited_rules
            assert set(c.answer.cited_rules) == set(f.answer.cited_rules) - {f.planted}
            continue
        assert f.evidence_ids == c.evidence_ids and f.planted == c.planted and f.cluster == c.cluster
        case = env["cases"][f.case_id]
        decisive = [r.rule_id for r in case.applicable_rules]
        assert c.answer.cited_rules == decisive
        assert f.planted in f.answer.cited_rules and f.planted not in c.answer.cited_rules
        diff = [i for i, (a, b) in enumerate(zip(f.answer.cited_rules, c.answer.cited_rules, strict=True)) if a != b]
        assert len(diff) == 1 and f.answer.cited_rules[diff[0]] == f.planted  # one clause swapped, nothing else
        assert f.answer.computed == c.answer.computed == []
        if not f.outcome_changing:
            assert (f.answer.decision, f.answer.blocking_stage) == (c.answer.decision, c.answer.blocking_stage)
        else:
            assert f.answer.decision != c.answer.decision
        # the same template: the root cause differs only by the basis clause id and its quote
        assert f.answer.root_cause.split(" under ")[0].startswith("The application is")
        assert c.answer.root_cause.split(" under ")[0].startswith("The application is")
        assert f.answer.root_cause.split(" under ")[1].startswith(f.planted)
        lines = {ln.split(":")[0] for ln, m in zip(generator_block(f.answer).splitlines(),
                                                    generator_block(c.answer).splitlines(), strict=True) if ln != m}
        assert lines <= {"Decision", "Blocking stage", "Cited rules", "Subsidy", "Root cause"}


def test_outcome_changing_known_cases(env: dict[str, Any]) -> None:
    by = {i.item_id: i for i in env["items"]}
    # 24 kW, claim Rs 94,822, rejected under PM Surya Ghar (Rs 78,000) but within Phase-II's Rs 94,822
    f = by["SB-4f382ccc#S-both#fault"]
    assert f.outcome_changing and f.answer.decision == "APPROVED" and f.answer.subsidy_amount_inr == 94822
    assert by["SB-4f382ccc#S-both#control"].answer.decision == "REJECTED"
    # RJ transformer: 80% (in force) vs 50% (superseded); where computed to flip, the fault rejects; where computed
    # not to flip, the plan is kept as a basis-only fault with the gold decision (D38)
    rj = [i for i in env["items"] if i.role == "fault" and i.planted == "RJ-C3-002#cl-6.1"]
    flip = [i for i in rj if i.outcome_changing]
    assert flip and all(i.answer.decision == "REJECTED" and i.answer.blocking_stage == "technical_feasibility"
                        for i in flip)
    same = [i for i in rj if not i.outcome_changing]
    assert same and all(i.answer.decision == vp.gold_outcome(env["cases"][i.case_id])[0] for i in same)
    # A siblings have no computable rule function: basis-only faults
    assert all(not i.outcome_changing for i in env["items"] if i.condition == "A")
    assert any(not i.outcome_changing for i in env["items"] if i.condition == "S-both")


def _capture(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    prompts: list[str] = []

    def fake(prompt: str, **_: Any) -> tuple[dict[str, Any], int, int]:
        prompts.append(prompt)
        return {"verdict": "PASS", "risk": 0.1, "findings": [], "reflection": "none"}, 1, 1

    monkeypatch.setattr(verify_shared, "call_llm_json", fake)
    monkeypatch.setattr(verify_reflect, "call_llm_json", fake)
    return prompts


def test_no_gold_reaches_the_verifier(env: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    prompts = _capture(monkeypatch)
    g, r = env["graph"], env["retriever"]
    f, c = next((f, c) for f, c in _pairs(env["items"]) if f.condition == "S-both" and f.outcome_changing)
    ctx = vp.ProbeContext(cases={k: BenchmarkRunner._unlabelled(v) for k, v in env["cases"].items()},
                          texts=vp.evidence_texts([f, c], g, r), retriever=r,
                          registries={n: Registry(n, g, r.chunk_clauses) for n in ("reg-oracle", "reg-real")},
                          labels={d: f"SRC-{i:04d}" for i, d in enumerate(sorted(r.doc_titles))})
    ctx.registries.update(vp.damaged_registries(ctx.registries["reg-real"]))
    for config in vp.CONFIGS:  # every gold field of the case is a tripwire (_Hidden); none may be read
        for it in (f, c):
            res = vp.verify_item(it, config, PROBE, ctx)
            assert res.verdict in {"PASS", "FLAG"}
    case = env["cases"][f.case_id]
    gold = case.expected_answer
    assert prompts
    for p in prompts:
        low = p.lower()
        assert gold.root_cause not in p and "fault" not in low.replace("fault class", "") and "planted" not in low
        assert "control" not in low and "outcome_changing" not in low and "exp-" not in p
    meta_off = [p for p in prompts if "SRC-" in p]
    assert meta_off and all(f.case_id not in p for p in prompts)


def _res(flags: list[str], verdict: str = "FLAG") -> VerifierResult:
    return VerifierResult(case_id="x", verifier_id="v", independence_config="000", verdict=verdict,
                          is_flagged=verdict == "FLAG" or bool(flags), flagged_faults=flags, audit_reason="",
                          latency_sec=0.0, prompt_tokens=0, completion_tokens=0, raw_output={})


def test_scoring(env: dict[str, Any]) -> None:
    f = next(i for i in env["items"] if i.role == "fault" and i.planted == "RJ-C3-002#cl-6.1")
    cl = env["classifier"]
    s = vp.score(f, _res(["ANY:RJ-C3-002#cl-6.1:not_in_force"]), cl)
    assert s["right"] and s["clause"] and not s["wrong"] and s["any"] and s["validity_reason"]
    s = vp.score(f, _res(["ANY:RJ-C3-002#cl-6.1:content_or_arithmetic"]), cl)
    assert s["clause"] and s["wrong"] and not s["right"] and not s["validity_reason"]
    s = vp.score(f, _res(["ANY:RJ-C3-002:not_in_force"]), cl)  # F3: the superseded instrument also counts
    assert s["right"]
    s = vp.score(f, _res(["ANY:RJ-C3-003#cl-2:not_in_force"]), cl)  # another clause: a validity claim, no catch
    assert not s["clause"] and s["validity_reason"]
    s = vp.score(f, _res([], "PASS"), cl)
    assert not s["any"] and not s["clause"]
    s = vp.score(f, _res([], "INVALID"), cl)  # D30: a miss and a false alarm
    assert s["invalid"] and s["any"] and not s["right"]


def _row(model: str, config: str, cluster: str, pair: int, role: str, right: bool, any_: bool,
         validity: bool = False, cond: str = "S-both") -> dict[str, Any]:
    return {"model": model, "config": config, "cluster": cluster, "pair_id": f"{cluster}-{pair}#{cond}",
            "item_id": f"{cluster}-{pair}#{cond}#{role}", "role": role, "condition": cond, "outcome_changing": pair % 2 == 0,
            "right": right, "clause": right, "wrong": False, "any": any_, "validity_reason": validity, "invalid": False}


def test_summary() -> None:
    rows = []
    for cl in ("a", "b", "c"):
        for p in range(2):
            rows += [_row("m", "support", cl, p, "fault", False, False), _row("m", "support", cl, p, "control", False, False),
                     _row("m", "validity", cl, p, "fault", True, True),
                     _row("m", "validity", cl, p, "control", False, True, validity=p == 0)]
    s = probe.summarise(rows)
    v = s["models"]["m"]["validity"]["conditions"]["S-both"]
    assert v["right"] == {"k": 6, "n": 6, "clusters": 3} and v["fpr"]["k"] == 6 and v["fpr_validity"]["k"] == 3
    assert v["discrimination"] == 0.5 and v["right_outcome_changing"]["n"] == 3
    p2 = s["contrasts"]["m"]["P2 validity - support"]
    assert p2["diff"] == 1.0 and p2["n_clusters"] == 3 and p2["p"] == 0.25 and p2["fpr_diff"] == 1.0
    assert s["contrasts"]["m"]["P4 100-neutral - support"]["p"] is None
    md = probe.markdown(s)
    assert "| validity | 6/6 (3cl) |" in md and "P2 validity - support" in md


# T2: sha256 over every prompt each pre-T2 configuration sends for PROMPT_ITEMS (recorded at commit 03ecb4f).
# A changed hash means an old configuration's prompt changed, and its saved blocks and cached replies no longer apply.
PROMPT_ITEMS = ("SB-4f382ccc#S-both#fault", "SB-4f382ccc#S-both#control", "SB-4f382ccc#S-swap#fault",
                "SB-4f382ccc#C#c-control")
OLD_PROMPT_HASHES = {
    "support": "a608824ef3cd51d9b7ff8a43099472455134526158087dc27ee7bb9e66046b10",
    "validity": "ea7bee6c9118faa5531d4f7673936c5fdbd190e63c44eb799df40771388ef9d7",
    "support-metaoff": "583aa8125c1e31ee537446722b93e27eb836c5dbabeac0409eceee5d537d56a2",
    "validity-metaoff": "a30eedcb0992b77def8d2a793409fd8a302474216a9d7c3e46a96f6b33e13b74",
    "reflect": "9587542a7db82f3f77ae15edeef50f1d9c7bbdac74442f38fe6ff9cf17148c1f",
    "100-neutral": "aeed30229ef87c4481fe06f9102d3c60a91a4447bc3d41189cb6aeb93ac6b652",
    "reg-real-llm": "c72590a9520e8474f19db0d8319b4503a948ac8b1a7bde351cc6b7fb440a924d",
}


def _ctx(env: dict[str, Any], items: list[vp.ProbeItem]) -> vp.ProbeContext:
    g, r = env["graph"], env["retriever"]
    return vp.ProbeContext(cases={k: BenchmarkRunner._unlabelled(v) for k, v in env["cases"].items()},
                           texts=vp.evidence_texts(items, g, r), retriever=r,
                           registries={n: Registry(n, g, r.chunk_clauses) for n in ("reg-oracle", "reg-real")},
                           labels={d: f"SRC-{i:04d}" for i, d in enumerate(sorted(r.doc_titles))})


def _prompt_hash(env: dict[str, Any], monkeypatch: pytest.MonkeyPatch, config: str) -> str:
    prompts = _capture(monkeypatch)
    by = {i.item_id: i for i in env["items"]}
    items = [by[k] for k in PROMPT_ITEMS]
    ctx = _ctx(env, items)
    for it in items:
        vp.verify_item(it, config, PROBE, ctx)
    return hashlib.sha256("\n\x00\n".join(prompts).encode("utf-8")).hexdigest()


def test_old_prompts_byte_identical(env: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    assert {c: _prompt_hash(env, monkeypatch, c) for c in OLD_PROMPT_HASHES} == OLD_PROMPT_HASHES


@pytest.fixture(scope="module")
def real(env: dict[str, Any]) -> Registry:
    """The non-gold registry as the probe runner builds it (runner._registry('reg-real'))."""
    manifest = load_manifest(CORPUS_R3_DIR / "MANIFEST.json")
    graph = load_registry(REAL_REGISTRY_R3, {d.doc_id: str(d.effective_date) for d in manifest.documents})
    chunks = build_corpus_chunks(CORPUS_R3_DIR / "text")
    return Registry("reg-real", graph, map_chunks_to_clauses(chunks, graph.nodes.values(), CORPUS_R3_DIR / "text"))


def test_new_prompt_contents(env: dict[str, Any], real: Registry, monkeypatch: pytest.MonkeyPatch) -> None:
    by = {i.item_id: i for i in env["items"]}
    fault = by["SB-8dc1cbde#S-both#fault"]  # RJ-C3-002#cl-6.1 planted: the registry links it
    ctx = _ctx(env, [fault])
    ctx.registries["reg-real"] = real
    sent: dict[str, str] = {}
    for config in ("validity", "validity-amendquote", "validity-regstatus", "validity-cc", "validity-cc-metaoff"):
        prompts = _capture(monkeypatch)
        vp.verify_item(fault, config, PROBE, ctx)
        sent[config] = prompts[-1]
    task = verify_shared.TASKS["validity"]
    assert all(task in p for p in sent.values())
    # R3: R2's prompt plus the quote block, nothing else; quotes verbatim from the registry, no status words
    lines = amendment_quotes(fault.answer, real, env["retriever"])
    block = "\n[TEXT OF THE AMENDING INSTRUMENT]\n" + "\n".join(lines) + "\n"
    assert lines and block in sent["validity-amendquote"]
    assert sent["validity-amendquote"].replace(block, "", 1) == sent["validity"]
    quotes = {" ".join(e.evidence.quote_text.split()) for e in real.graph.edges}
    for ln in lines:
        assert ln.startswith(f"- {fault.planted}: \"") or ln.split(":")[0][2:] in fault.answer.cited_rules
        assert ln.split(": ", 1)[1].strip('"') in quotes
    header = block.split('"')[0]
    assert not re.search(r"supersed|in force|status|not_in_force|amended by|effective", header, re.I)
    # R4: the registry lookup block on the validity prompt
    assert "[CLAUSE REGISTRY LOOKUP OF THE GENERATOR'S CITATIONS]" in sent["validity-regstatus"]
    assert "[CLAUSE REGISTRY LOOKUP" not in sent["validity"]
    status = sent["validity-regstatus"].split("\n[CLAUSE REGISTRY LOOKUP")[1].split("\n\n", 1)[0]
    assert sent["validity-regstatus"].replace("\n[CLAUSE REGISTRY LOOKUP" + status + "\n", "", 1) == sent["validity"]
    # E2: one extra reason code, and only in the -cc prompts
    assert "currency_unconfirmed" in sent["validity-cc"] and "currency_unconfirmed" in sent["validity-cc-metaoff"]
    assert all("currency_unconfirmed" not in sent[c] for c in ("validity", "validity-amendquote", "validity-regstatus"))
    assert sent["validity-cc"].replace(verify_shared.reason_block(verify_shared.CC_REASONS), verify_shared.REASON_BLOCK) \
        == sent["validity"]
    reply = {"verdict": "FLAG", "findings": [{"clause_id": "X#cl-1", "reason": "currency unconfirmed"}]}
    assert verify_shared.parse_verdict(reply, reasons=verify_shared.CC_REASONS)[3] == ["ANY:X#cl-1:currency_unconfirmed"]
    assert verify_shared.parse_verdict(reply)[3] == ["ANY:X#cl-1:other"]  # the old prompts' parsing is unchanged


def _edges(r: Registry) -> set[tuple[str, str, str]]:
    return {(e.from_node, e.to_node, e.relation.value) for e in r.graph.edges}


def test_damaged_registries(real: Registry) -> None:
    for seed in vp.DAMAGE_SEEDS:
        assert _edges(Registry("x", noisy_registry(real.graph, 0.0, seed))) == _edges(real)  # 0% damage = undamaged
    dmg = vp.damaged_registries(real)
    assert set(dmg) == set(vp.DAMAGED) and len(dmg) == 15
    n = len(real.graph.edges)
    for seed in vp.DAMAGE_SEEDS:
        d25, d50 = _edges(dmg[f"reg-drop25-s{seed}"]), _edges(dmg[f"reg-drop50-s{seed}"])
        assert d50 <= d25 <= _edges(real)  # nested: the 50% drop set contains the 25% one
        assert len(real.graph.edges) - len(dmg[f"reg-drop25-s{seed}"].graph.edges) == round(n * 0.25)
        sp = dmg[f"reg-spurious10-s{seed}"]
        assert _edges(real) < _edges(sp) and dmg[f"reg-spurious10-s{seed}"].chunk_map is real.chunk_map
    assert len({frozenset(_edges(dmg[f"reg-drop25-s{k}"])) for k in vp.DAMAGE_SEEDS}) == 5  # seeds differ


def test_rungs_and_registries() -> None:
    assert [vp.rung(c, k) for c, k in [("validity-metaoff", "S-swap"), ("validity", "S-swap"), ("validity", "S-both"),
            ("validity-amendquote", "S-both"), ("validity-regstatus", "S-both"), ("reg-real", "S-both")]] \
        == ["R0", "R1", "R2", "R3", "R4", "R5"]
    assert vp.rung("validity-regstatus", "S-swap") == "R4'" and vp.rung("validity", "C") == "R1-R2"
    assert vp.rung("reg-drop50-s3", "S-swap") == "R5-drop50"
    assert vp.rung("validity-regstatus-drop25-s1", "S-swap") == "R4'-drop25"
    assert vp.rung("reg-drop50-s3", "S-both") == "R5-drop50" and vp.rung("validity-regstatus-spurious10-s0", "C") == "R4-spurious10"
    assert vp.rung("support", "S-both") is None and vp.rung("validity", "J") is None
    assert vp.registry_of("validity-regstatus-drop25-s2") == "reg-drop25-s2" and vp.registry_of("reg-real-llm") == "reg-real"
    assert all(vp.CONFIGS[f"validity-regstatus-{d.removeprefix('reg-')}"][0] == "registry-llm" for d in vp.DAMAGED)
    # D49 R4n
    assert vp.rung("validity-regnorec", "S-both") == "R4n" and vp.rung("validity-regnorec", "C") == "R4n"
    assert vp.rung("validity-regnorec-drop50-s3", "S-both") == "R4n-drop50" and vp.rung("validity-regnorec", "S-swap") is None
    assert vp.registry_of("validity-regnorec-drop50-s3") == "reg-drop50-s3" and vp.registry_of("validity-regnorec") == "reg-real"


def test_no_record_changes_only_the_in_force_word(env: dict[str, Any], real: Registry,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:  # D49
    by = {i.item_id: i for i in env["items"]}
    fault = by["SB-8dc1cbde#S-both#fault"]
    ctx = _ctx(env, [fault])
    ctx.registries["reg-real"] = real
    ctx.registries["reg-drop50-s0"] = vp.damaged_registries(real)["reg-drop50-s0"]
    sent: dict[str, str] = {}
    for config in ("validity-regstatus", "validity-regnorec", "validity-regstatus-drop50-s0", "validity-regnorec-drop50-s0"):
        prompts = _capture(monkeypatch)
        vp.verify_item(fault, config, PROBE, ctx)
        sent[config] = prompts[-1]
    for state in ("", "-drop50-s0"):
        old, new = sent[f"validity-regstatus{state}"], sent[f"validity-regnorec{state}"]
        assert new == old.replace(": in_force", ": no_amendment_recorded")
    assert ": in_force" in sent["validity-regstatus-drop50-s0"] or ": in_force" in sent["validity-regstatus"]


def test_block_manifest_fields(env: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    import run_verifier_probe as rvp

    _capture(monkeypatch)
    by = {i.item_id: i for i in env["items"]}
    items = [by[k] for k in PROMPT_ITEMS[:2]]
    ctx = _ctx(env, items)
    rows = [vp.record(it, "validity", PROBE, vp.verify_item(it, "validity", PROBE, ctx), env["classifier"]) for it in items]
    assert all(r["rung"] == "R2" and len(r["prompt_sha256"]) == 64 for r in rows)
    m = rvp.block_manifest("validity", "S-both", PROBE, rows, dataset_sha256="d" * 64, cases="x.json", allow_test=False,
                           max_items=None)
    for key in ("model", "model_version", "config", "rung", "condition", "prompt_hash", "temperature", "seed",
                "timestamp", "dataset_sha256", "allow_test"):
        assert key in m
    assert m["rung"] == "R2" and m["temperature"] == 0.0 and len(m["prompt_hash"]) == 64
    reg = [vp.record(it, "reg-real", PROBE, vp.verify_item(it, "reg-real", PROBE, ctx), env["classifier"]) for it in items]
    assert rvp.block_manifest("reg-real", "S-both", PROBE, reg)["prompt_hash"] is None


def test_cant_confirm_scored_apart(env: dict[str, Any]) -> None:
    f = next(i for i in env["items"] if i.role == "fault" and i.condition == "S-both")
    cc = f"ANY:{f.planted}:currency_unconfirmed"
    only = vp.score(f, _res([cc]), env["classifier"])
    assert only["cant_confirm"] and not only["any"] and not only["clause"] and not only["right"]
    both = vp.score(f, _res([cc, f"ANY:{f.planted}:not_in_force"]), env["classifier"])
    assert both["cant_confirm"] and both["any"] and both["right"]
    plain = vp.score(f, _res([f"ANY:{f.planted}:not_in_force"]), env["classifier"])
    assert not plain["cant_confirm"] and plain["right"] and plain["any"]
    assert not vp.score(f, _res([], "PASS"), env["classifier"])["any"]


SMOKE = CODE_DIR.parent / "50_analysis" / "results" / "smoke_t2"
MANIFEST_FIELDS = ("model", "model_version", "config", "rung", "condition", "prompt_hash", "code_hash",
                   "max_output_tokens", "temperature", "seed", "dataset_sha256", "timestamp")


@pytest.mark.skipif(not SMOKE.exists(), reason="the T2 dev smoke run has not been made")
def test_smoke_blocks_carry_the_manifest() -> None:
    """P4-4: every block of the T2 smoke run records its provenance, non-empty (a deterministic registry block
    sends no prompt, so its prompt hash and model version are empty)."""
    blocks = sorted(SMOKE.glob("*/blocks/*.json"))
    assert blocks
    for b in blocks:
        d = json.loads(b.read_text(encoding="utf-8"))
        llm = d["config"] in vp.LLM_CONFIGS
        for key in MANIFEST_FIELDS:
            if key in {"prompt_hash", "model_version"} and not llm:
                continue
            if key == "rung":  # None only off the ladder (e.g. R3 is defined on S-both alone)
                assert key in d and (d[key] or vp.rung(d["config"], d["condition"]) is None), b.name
                continue
            assert d.get(key) not in (None, ""), (b.name, key)
        assert d["rows"] and all(r["rung"] == d["rung"] for r in d["rows"])
