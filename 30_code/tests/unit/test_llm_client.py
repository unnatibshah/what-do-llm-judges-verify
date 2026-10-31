"""Unit tests for the unified LLM client (protocol §1.4)."""

from unittest.mock import patch

import pytest

from suryabench.arms.llm_client import call_llm_json
from suryabench.core.exceptions import SuryaBenchError


def test_call_llm_groq_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that requesting Groq without an API key raises an error."""
    monkeypatch.setenv("GROQ_API_KEY", "")
    with pytest.raises(SuryaBenchError, match="GROQ_API_KEY is not set"):
        call_llm_json("test", provider="groq")


def test_call_llm_provider_routing_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that default provider routes to local Ollama."""
    monkeypatch.setenv("LLM_PROVIDER", "local")

    with patch("suryabench.arms.llm_client._call_local_ollama") as mock_local:
        mock_local.return_value = ('{"decision": "APPROVED"}', 10, 20)
        res, p_tok, c_tok = call_llm_json("Test prompt")
        assert mock_local.called
        assert res["decision"] == "APPROVED"
        assert p_tok == 10
        assert c_tok == 20


def test_call_llm_provider_routing_groq(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that setting provider to 'groq' routes to Groq API."""
    monkeypatch.setenv("GROQ_API_KEY", "mock_key")

    with patch("suryabench.arms.llm_client._call_groq_api") as mock_groq:
        mock_groq.return_value = ('{"verdict": "PASS"}', 30, 40)
        res, p_tok, c_tok = call_llm_json("Test prompt", provider="groq")
        assert mock_groq.called
        assert res["verdict"] == "PASS"
        assert p_tok == 30
        assert c_tok == 40
