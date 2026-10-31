"""T3: scoring of synthetic verifier replies, end to end. Each raw reply goes through the real path (provider call
stubbed -> parse_json_reply -> parse_verdict -> verify_item's invalid handling -> score) and must give exactly the
expected scores. No model is run."""

import json
from typing import Any

import pytest
from test_verifier_probe import _ctx, env  # noqa: F401  (the dev probe fixture)

from suryabench.arms import llm_client
from suryabench.arms import verifier_probe as vp

KEYS = ("invalid", "any", "clause", "right", "wrong", "validity_reason", "cant_confirm")


def _scores(**true: bool) -> dict[str, bool]:
    return {k: true.get(k, False) for k in KEYS}


def _reply(findings: list[dict[str, Any]], verdict: str = "FLAG") -> str:
    return json.dumps({"verdict": verdict, "risk": 0.8, "findings": findings})


@pytest.fixture()
def run(env: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> Any:  # noqa: F811
    monkeypatch.delenv("SURYABENCH_LLM_CACHE", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "local")
    item = {i.item_id: i for i in env["items"]}["SB-8dc1cbde#S-both#fault"]  # F3, planted RJ-C3-002#cl-6.1
    ctx = _ctx(env, [item])

    def score(raw: str, config: str = "validity") -> dict[str, bool]:
        monkeypatch.setattr(llm_client, "_call_local_ollama", lambda *a, **k: (raw, 10, 5))
        return vp.score(item, vp.verify_item(item, config, "qwen2.5:7b", ctx), env["classifier"])

    return item, score


PLANT = "RJ-C3-002#cl-6.1"
OTHER = "MH-C3-001#cl-6.2"  # another document: not the planted clause even under F3's same-document rule


def test_synthetic_replies(run: Any) -> None:
    item, score = run
    assert item.planted == PLANT and item.fault_class == "F3"
    f = {"clause_id": PLANT, "rationale": "x"}
    cases = {
        "right catch": (_reply([{**f, "reason": "not_in_force"}]),
                        _scores(any=True, clause=True, right=True, validity_reason=True)),
        "right catch, same document (F3)": (_reply([{**f, "clause_id": "RJ-C3-002#cl-9", "reason": "not_in_force"}]),
                                            _scores(any=True, clause=True, right=True, validity_reason=True)),
        "wrong reason": (_reply([{**f, "reason": "not_applicable"}]),
                         _scores(any=True, clause=True, wrong=True, validity_reason=True)),
        "wrong clause": (_reply([{**f, "clause_id": OTHER, "reason": "not_in_force"}]),
                         _scores(any=True, validity_reason=True)),
        "PASS": (_reply([], "PASS"), _scores()),
        "FLAG without findings": (_reply([]), _scores(any=True)),
        "array-wrapped (D34)": ("[" + _reply([{**f, "reason": "not_in_force"}]) + "]",
                                _scores(any=True, clause=True, right=True, validity_reason=True)),
        "code fence": ("```json\n" + _reply([{**f, "reason": "not_in_force"}]) + "\n```",
                       _scores(any=True, clause=True, right=True, validity_reason=True)),
        "empty": ("", _scores(invalid=True, any=True)),
        "truncated JSON": (_reply([{**f, "reason": "not_in_force"}])[:40], _scores(invalid=True, any=True)),
        "no verdict": (json.dumps({"findings": [{**f, "reason": "not_in_force"}]}), _scores(invalid=True, any=True)),
        "two-element array": ("[" + _reply([]) + "," + _reply([]) + "]", _scores(invalid=True, any=True)),
        "unknown reason -> other": (_reply([{**f, "reason": "outdated"}]), _scores(any=True, clause=True, wrong=True)),
        "extra fields ignored": (json.dumps({"verdict": "FLAG", "risk": 1, "note": "n", "findings": [
            {**f, "reason": "Not in force", "class": "F3", "page": 4}]}),
            _scores(any=True, clause=True, right=True, validity_reason=True)),
        "can't confirm under the old prompt -> other": (_reply([{**f, "reason": "currency_unconfirmed"}]),
                                                        _scores(any=True, clause=True, wrong=True)),
    }
    for name, (raw, want) in cases.items():
        assert score(raw) == want, name


def test_cant_confirm_replies(run: Any) -> None:
    _, score = run
    cc = {"clause_id": PLANT, "reason": "currency unconfirmed", "rationale": "dates not shown"}
    assert score(_reply([cc]), "validity-cc") == _scores(cant_confirm=True)  # neither a catch nor an alarm
    both = _reply([cc, {"clause_id": PLANT, "reason": "not_in_force"}])
    assert score(both, "validity-cc") == _scores(any=True, clause=True, right=True, validity_reason=True,
                                                 cant_confirm=True)
    other = _reply([{**cc, "clause_id": OTHER}])
    assert score(other, "validity-cc") == _scores(cant_confirm=True)
    assert score(_reply([cc]), "validity") == _scores(any=True, clause=True, wrong=True)  # old list: "other"


def test_invalid_replies_are_never_cached(run: Any, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    _, score = run
    monkeypatch.setenv("SURYABENCH_LLM_CACHE", str(tmp_path))
    assert score("not json")["invalid"]
    assert not list(tmp_path.rglob("*.json"))
    assert score(_reply([], "PASS")) == _scores()
    assert len(list(tmp_path.rglob("*.json"))) == 1  # a valid reply is cached
