"""Unified LLM inference client: local Ollama (default), Google Gemini API, Groq Cloud (protocol §1.4).

Routing is by model name: ``gemini-*`` and ``gemma-*`` go to the Gemini API, names containing ``/``
or ``groq`` to Groq, everything else to Ollama (``LLM_PROVIDER`` or ``provider=`` override it).

Every prompt carries ``CANARY`` so that benchmark text found in a future training corpus can be
recognised. A reply that is not valid JSON raises: no call is ever replaced by a synthetic answer.

Free-tier support (2026-10-01, plan D4/D6): exponential backoff on 429/500/503, a per-model minimum
interval between calls (``SURYABENCH_MIN_INTERVAL_<MODEL>`` or ``SURYABENCH_MIN_INTERVAL``, seconds),
and an optional on-disk response cache (``SURYABENCH_LLM_CACHE=<dir>``) keyed by the full request, so
an interrupted run resumes without re-paying for finished calls.
"""

import hashlib
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from suryabench.core.exceptions import InvalidModelOutput, SuryaBenchError
from suryabench.paths import ENV_FILE

# Fixed for the life of the benchmark; never change it (it is how contamination is detected).
CANARY = "SURYABENCH-CANARY-6f1d2c84-3b7e-4a9d-9c5e-2e8a71b0d4f3"


def _load_env_file() -> None:
    """Load key-value pairs from .env if present and not already in environment."""
    env_path = ENV_FILE
    if not env_path.exists():
        return

    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("\"'")
            if key not in os.environ:
                os.environ[key] = val


_load_env_file()

# Raw completion string of the most recent call, before any JSON parsing.
# Diagnostic use only (see scripts/diagnose_flag_path.py); never read by the eval path.
LAST_RAW: str | None = None

# model -> {"provider", "model_version"} of the most recent reply; the runner copies it into manifests.
MODEL_INFO: dict[str, dict[str, str]] = {}

# Free-tier output-token-per-minute caps reject any request whose max_tokens exceeds them.
GROQ_MAX_TOKENS = {"qwen/qwen3.8-27b": 900}

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# Models that rejected responseMimeType=application/json; they get prompt-only JSON (strictly parsed).
_NO_JSON_MODE: set[str] = set()
JSON_MODE_FALLBACKS: dict[str, int] = {}  # per model: MAX_TOKENS replies retried without JSON mode

# Provider seed for the current run; BenchmarkRunner sets it from BenchmarkRunConfig.seed.
RUN_SEED = 42

_last_call: dict[str, float] = {}
_rate_lock = threading.Lock()


class QuotaExhausted(SuryaBenchError):
    """A daily quota is spent: retrying today cannot succeed. Re-run tomorrow; the cache resumes it."""


def set_run_seed(seed: int) -> None:
    """Set the seed forwarded to Groq/Ollama for every subsequent call."""
    global RUN_SEED
    RUN_SEED = seed


def as_str_list(value: Any) -> list[str]:
    """Coerce an LLM-returned list field (cited_rules, flagged_faults) to list[str].

    Models return these as a JSON list, as a single delimited string, or as null.
    A bare string must not be passed through: downstream code iterates these
    fields element-wise, and iterating a str yields one character per element
    (e.g. one fabricated-citation fault per character of a prose answer).
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [p.strip() for p in re.split(r"[,;\n]", value) if p.strip()]
    if isinstance(value, list):
        return [str(v).strip() for v in value if v is not None and str(v).strip()]
    return [str(value).strip()]


def parse_json_reply(raw: str) -> dict[str, Any]:
    """The reply as a JSON object, tolerating a Markdown code fence or prose around it (2026-10-30); else raise."""
    text = raw.strip()
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        start = text.find("{")  # prose before or after the object: the first complete object is the reply
        try:
            data = json.JSONDecoder().raw_decode(text, start)[0] if start >= 0 else None
        except json.JSONDecodeError:
            data = None
        if data is None:
            raise InvalidModelOutput(f"Model reply is not valid JSON ({e}): {raw[:300]!r}") from e
    if isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict):
        data = data[0]  # D34: one object wrapped in a one-element array is that object
    if not isinstance(data, dict):
        raise InvalidModelOutput(f"Model reply is JSON but not an object: {raw[:300]!r}")
    return data


def _slug(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", model).strip("_")


def _min_interval(model: str, provider: str) -> float:
    env = os.environ.get(f"SURYABENCH_MIN_INTERVAL_{_slug(model).upper()}") or os.environ.get("SURYABENCH_MIN_INTERVAL")
    if env:
        return float(env)
    return 4.0 if provider == "gemini" else 0.0  # ponytail: one default for every free Gemini model


def _max_tokens(default: int) -> int:
    """Output-token cap: ``SURYABENCH_MAX_OUTPUT_TOKENS`` (D33 sets 1024 for every verifier call), else the default."""
    return int(os.environ.get("SURYABENCH_MAX_OUTPUT_TOKENS") or default)


def _throttle(model: str, provider: str) -> None:
    gap = _min_interval(model, provider)
    if gap <= 0:
        return
    with _rate_lock:
        wait = _last_call.get(model, 0.0) + gap - time.time()
        if wait > 0:
            time.sleep(wait)
        _last_call[model] = time.time()


def _backoff(attempt: int) -> float:
    cap = float(os.environ.get("SURYABENCH_BACKOFF_CAP", "300"))
    return float(min(cap, 5.0 * 2**attempt))


def _quota_info(err: str) -> tuple[bool, float]:
    """(daily quota spent, server-suggested retry delay in seconds) from a Gemini error body.

    The body lists every quota a request touches; it is a daily exhaustion only when every violated quota
    is a per-day one (a per-minute 429 also names the per-day quotas in its text)."""
    try:
        details = json.loads(err).get("error", {}).get("details", [])
    except (json.JSONDecodeError, AttributeError):
        return False, 0.0
    violated = [str(v.get("quotaId", "")) for d in details for v in d.get("violations", [])]
    delay = next((d.get("retryDelay") for d in details if "retryDelay" in d), "0s")
    m = re.match(r"([0-9.]+)s", str(delay))
    return bool(violated) and all("PerDay" in q for q in violated), float(m.group(1)) + 1.0 if m else 0.0


def _call_gemini_api(
    prompt: str,
    system_prompt: str,
    model: str,
    temperature: float,
    timeout: float,
    max_retries: int,
    response_schema: dict[str, Any] | None = None,
) -> tuple[str, int, int]:
    """Raw text reply via the Gemini REST API. The system prompt is sent as text (Gemma has no system role)."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise SuryaBenchError("GEMINI_API_KEY is not set in environment or .env file.")

    json_mode = True  # off for this call after a MAX_TOKENS reply (JSON-mode looping at temperature 0)
    for attempt in range(max_retries):
        config: dict[str, Any] = {"temperature": temperature, "maxOutputTokens": _max_tokens(8192)}
        if json_mode and model not in _NO_JSON_MODE:
            config["responseMimeType"] = "application/json"
            if response_schema is not None:
                config["responseSchema"] = response_schema
        body = json.dumps({"contents": [{"role": "user", "parts": [{"text": f"{system_prompt}\n\n{prompt}"}]}],
                           "generationConfig": config}).encode("utf-8")
        req = urllib.request.Request(GEMINI_URL.format(model=model), data=body,
                                     headers={"x-goog-api-key": key, "Content-Type": "application/json"})
        _throttle(model, "gemini")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                res = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", "replace")
            if e.code == 400 and model not in _NO_JSON_MODE and ("JSON mode" in err or "response_mime_type" in err
                                                                 or "responseMimeType" in err):
                _NO_JSON_MODE.add(model)
                continue
            daily, retry_after = _quota_info(err)
            if e.code == 429 and daily:
                raise QuotaExhausted(f"Gemini daily quota exhausted for {model}: {err[:1500]}") from e
            if e.code in {429, 500, 503} and attempt < max_retries - 1:
                time.sleep(max(_backoff(attempt), retry_after))
                continue
            raise SuryaBenchError(f"Gemini API HTTP {e.code} for {model}: {err[:500]}") from e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt < max_retries - 1:
                time.sleep(_backoff(attempt))
                continue
            raise SuryaBenchError(f"Gemini API call failed for {model}: {e}") from e

        cands = res.get("candidates") or []
        parts = (cands[0].get("content") or {}).get("parts", []) if cands else []
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        if cands and cands[0].get("finishReason") == "MAX_TOKENS" and json_mode and model not in _NO_JSON_MODE:
            # Logged and counted; the reply is then parsed strictly, and a second failure fails the run.
            json_mode = False
            JSON_MODE_FALLBACKS[model] = JSON_MODE_FALLBACKS.get(model, 0) + 1
            print(f"[llm_client] {model}: MAX_TOKENS in JSON mode; retrying once without JSON mode", file=sys.stderr)
            continue
        if not text:
            reason = cands[0].get("finishReason") if cands else res.get("promptFeedback")
            if reason == "MAX_TOKENS":
                raise InvalidModelOutput(f"Gemini returned no text for {model} (finish: {reason})")
            raise SuryaBenchError(f"Gemini returned no text for {model} (finish: {reason})")
        usage = res.get("usageMetadata", {})
        MODEL_INFO[model] = {"provider": "gemini", "model_version": str(res.get("modelVersion", model)),
                             "json_mode_fallbacks": str(JSON_MODE_FALLBACKS.get(model, 0))}
        return text, int(usage.get("promptTokenCount", 0)), int(usage.get("candidatesTokenCount", 0)) + int(
            usage.get("thoughtsTokenCount", 0))
    raise SuryaBenchError(f"Exhausted retries calling Gemini API for {model}.")


def _call_groq_api(
    prompt: str,
    system_prompt: str,
    model: str | None,
    temperature: float,
    timeout: float,
    max_retries: int,
) -> tuple[str, int, int]:
    """Raw text reply via Groq Cloud API with rate-limit backoff."""
    groq_api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not groq_api_key:
        raise SuryaBenchError("GROQ_API_KEY is not set in environment or .env file.")

    target_model = model or os.environ.get("GROQ_MODEL", "qwen/qwen3.8-27b")
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = json.dumps(
        {
            "model": target_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": GROQ_MAX_TOKENS.get(target_model, 4096),  # reasoning models spend tokens before the JSON
            "temperature": temperature,
            "seed": RUN_SEED,
        }
    ).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {groq_api_key}",
        "Content-Type": "application/json",
        "User-Agent": "SuryaBench/1.0",
    }

    for attempt in range(max_retries):
        req = urllib.request.Request(url, data=payload, headers=headers)
        _throttle(target_model, "groq")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                res = json.loads(resp.read().decode("utf-8"))
            choice = res.get("choices", [{}])[0]
            usage = res.get("usage", {})
            MODEL_INFO[target_model] = {"provider": "groq", "model_version": str(res.get("model", target_model))}
            return (choice.get("message", {}).get("content", ""), usage.get("prompt_tokens", 0),
                    usage.get("completion_tokens", 0))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            if e.code == 429 and attempt < max_retries - 1:
                match = re.search(r"try again in ([0-9.]+)(s|ms)", err_body)
                if match:
                    val = float(match.group(1))
                    wait_sec = (val if match.group(2) == "s" else val / 1000.0) + 1.5
                else:
                    wait_sec = 3.0 * (attempt + 1)
                time.sleep(wait_sec)
                continue
            if e.code == 400 and "json_validate_failed" in err_body and attempt < max_retries - 1:
                time.sleep(2.0)
                continue
            raise SuryaBenchError(f"Groq API HTTP {e.code} error: {err_body}") from e
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2.0)
                continue
            raise SuryaBenchError(f"Groq API call failed: {e}") from e

    raise SuryaBenchError("Exhausted retries calling Groq API.")


def _call_local_ollama(
    prompt: str,
    system_prompt: str,
    model: str | None,
    temperature: float,
    timeout: float,
) -> tuple[str, int, int]:
    """Raw text reply via local Ollama instance (Apple Silicon GPU)."""
    local_model = model or os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    url = f"{host.rstrip('/')}/api/generate"

    payload = json.dumps(
        {
            "model": local_model,
            "prompt": f"{system_prompt}\n\n{prompt}",
            "format": "json",
            "stream": False,
            "options": {"temperature": temperature, "seed": RUN_SEED, "num_predict": _max_tokens(1024), "num_ctx": 16384},
        }
    ).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            res = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise SuryaBenchError(f"Local Ollama call failed on {url}: {e}") from e
    MODEL_INFO[local_model] = {"provider": "ollama", "model_version": local_model}
    return res.get("response", ""), res.get("prompt_eval_count", 0), res.get("eval_count", 0)


def _provider_for(model: str | None, provider: str | None) -> str:
    if provider is not None:
        p = provider.strip().lower()
        return "groq" if p == "cloud" else p
    if model == "mock":
        return "mock"
    if model and model.startswith(("gemini-", "gemma-")):
        return "gemini"
    if model and ("/" in model or "groq" in model.lower()):
        return "groq"
    return os.environ.get("LLM_PROVIDER", "local").strip().lower()


MOCK_REPLY: dict[str, Any] = {
    "action": "final",
    "decision": "APPROVED",
    "root_cause": None,
    "cfa_subsidy_inr": 60000,
    "cited_rules": ["IN-C1-001#cl-4.1"],
    "next_action": "proceed_to_metering_installation",
    "computed": [],
    "verdict": "PASS",
    "risk": 0.1,
    "findings": [],
    "reason": "Deterministic mock evaluation",
    "reflection": "Mock reflection pass",
}


def call_llm_json(
    prompt: str,
    system_prompt: str = "You are an Indian Rooftop Solar Regulatory Verification Agent. Keep explanation concise under 30 words. Respond in strict JSON.",
    model: str | None = None,
    provider: str | None = None,
    temperature: float = 0.0,
    timeout: float = 240.0,
    max_retries: int = 12,
    response_schema: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int, int]:
    """One JSON-constrained call. Returns (parsed JSON object, prompt tokens, completion tokens).

    Raises SuryaBenchError if the call fails or the reply is not a JSON object.
    """
    _load_env_file()
    # Unattended free-tier runs ride out long 503 spells (SURYABENCH_MAX_RETRIES x backoff cap).
    max_retries = int(os.environ.get("SURYABENCH_MAX_RETRIES", max_retries))
    selected = _provider_for(model, provider)
    if selected in {"mock", "test"}:
        return dict(MOCK_REPLY), 120, 30

    prompt = f"{prompt}\n\n[{CANARY}]"
    target = model or (os.environ.get("OLLAMA_MODEL", "qwen2.5:7b") if selected == "local" else "")
    cache_dir = os.environ.get("SURYABENCH_LLM_CACHE", "").strip()
    cache_file: Path | None = None
    if cache_dir:
        key = hashlib.sha256(json.dumps([selected, target, system_prompt, prompt, temperature, RUN_SEED,
                                         response_schema], sort_keys=True).encode("utf-8")).hexdigest()
        cache_file = Path(cache_dir) / _slug(target or selected) / f"{key}.json"
        if cache_file.exists():
            hit = json.loads(cache_file.read_text(encoding="utf-8"))
            MODEL_INFO.setdefault(target, hit.get("info", {}))
            return parse_json_reply(hit["raw"]), hit["p"], hit["c"]

    global LAST_RAW
    if selected == "gemini":
        raw, p_tok, c_tok = _call_gemini_api(prompt, system_prompt, target, temperature, timeout, max_retries,
                                             response_schema)
    elif selected == "groq":
        raw, p_tok, c_tok = _call_groq_api(prompt, system_prompt, model, temperature, timeout, max_retries)
    else:
        raw, p_tok, c_tok = _call_local_ollama(prompt, system_prompt, model, temperature, timeout)
    LAST_RAW = raw
    data = parse_json_reply(raw)  # raises before anything is cached

    if cache_file is not None:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache_file.with_suffix(".tmp")
        tmp.write_text(json.dumps({"raw": raw, "p": p_tok, "c": c_tok, "info": MODEL_INFO.get(target, {})}),
                       encoding="utf-8", newline="\n")
        tmp.replace(cache_file)
    return data, p_tok, c_tok
