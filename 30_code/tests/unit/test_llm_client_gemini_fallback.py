"""MAX_TOKENS in JSON mode is retried once without JSON mode, and counted."""
import io
import json
from typing import Any

from suryabench.arms import llm_client


class _Resp(io.BytesIO):
    def __enter__(self) -> "_Resp":
        return self

    def __exit__(self, *a: Any) -> None:
        pass


def test_max_tokens_retries_without_json_mode(monkeypatch: Any) -> None:
    sent: list[dict[str, Any]] = []
    replies = [{"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": []}}]},
               {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": '{"ok": true}'}]}}]}]

    def fake_urlopen(req: Any, timeout: float = 0) -> _Resp:
        sent.append(json.loads(req.data))
        return _Resp(json.dumps(replies[len(sent) - 1]).encode())

    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(llm_client, "_throttle", lambda *a: None)
    text, _, _ = llm_client._call_gemini_api("p", "s", "gemma-test", 0.0, 10.0, 3)
    assert text == '{"ok": true}'
    assert "responseMimeType" in sent[0]["generationConfig"]
    assert "responseMimeType" not in sent[1]["generationConfig"]
    assert llm_client.JSON_MODE_FALLBACKS["gemma-test"] == 1
