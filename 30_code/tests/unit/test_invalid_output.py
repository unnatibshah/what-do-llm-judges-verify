"""D24: an unusable model reply is scored as an invalid answer, never correct, never a commitment."""
import json

from suryabench.cases.schema import BenchmarkCase
from suryabench.corpus.schema import CorpusManifest
from suryabench.eval.failure_classifier import FailureClassifier
from suryabench.eval.runner import invalid_generation, invalid_verification
from suryabench.graph.schema import SupersessionGraph
from suryabench.paths import resolve


def _cases() -> list[BenchmarkCase]:
    data = json.loads(resolve("40_data/benchmark/dev_cases_v2.json").read_text(encoding="utf-8"))
    return [BenchmarkCase.model_validate(c) for c in data]


def test_invalid_generation_is_never_correct_or_committed() -> None:
    graph = SupersessionGraph.model_validate_json(resolve("40_data/corpus/graph/supersession.json").read_text(encoding="utf-8"))
    manifest = CorpusManifest.model_validate_json(resolve("40_data/corpus/MANIFEST.json").read_text(encoding="utf-8"))
    clf = FailureClassifier(graph=graph, manifest=manifest)
    clean = [c for c in _cases() if c.expected_answer.blocking_stage is None and not c.fault_events][:3]
    trapped = [c for c in _cases() if c.fault_events][:5]
    assert clean and trapped
    for case in clean + trapped:
        r = clf.classify_case(case, invalid_generation(case.case_id, "cut off"))
        assert r.invalid_output and not r.is_correct and not r.outcome_correct
        assert not any(r.fault_event_committed.values())


def test_invalid_verification_flags_nothing() -> None:
    v = invalid_verification("SB-x", "arm3", "000", "not JSON")
    assert v.verdict == "INVALID" and not v.is_flagged and v.flagged_faults == []


def test_d34_one_element_array_of_object_is_the_object() -> None:
    import pytest

    from suryabench.arms.llm_client import parse_json_reply
    from suryabench.core.exceptions import InvalidModelOutput

    assert parse_json_reply('[ {"verdict": "PASS", "findings": []} ]') == {"verdict": "PASS", "findings": []}
    for raw in ("[]", '[{"verdict": "PASS"}, {"verdict": "FLAG"}]', '["PASS"]', "[[{}]]", '"PASS"'):
        with pytest.raises(InvalidModelOutput):
            parse_json_reply(raw)


def test_prose_around_the_json_object_is_tolerated() -> None:
    import pytest

    from suryabench.arms.llm_client import parse_json_reply
    from suryabench.core.exceptions import InvalidModelOutput

    obj = {"verdict": "FLAG", "findings": [{"doc_id": "RFC1", "reason": "superseded"}]}
    for raw in ('Looking at the dates:\n' + json.dumps(obj), 'Here is my review.\n```json\n' + json.dumps(obj) + '\n```',
                json.dumps(obj) + "\nThe answer is outdated."):
        assert parse_json_reply(raw) == obj
    for raw in ("The answer is valid.", "Verdict: {PASS}"):
        with pytest.raises(InvalidModelOutput):
            parse_json_reply(raw)
