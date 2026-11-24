import os
import json
import time
import hashlib
from typing import List, Dict, Any, Optional, Tuple
import litellm
from fastapi import HTTPException

# ---------------------------------------------------------------------------
# In-memory response cache:  cache_key -> {reply, metadata}
# Cache key = hash(model + json(full_messages))
# ---------------------------------------------------------------------------
_response_cache: Dict[str, Dict[str, Any]] = {}


def _get_config():
    keys = [k.strip() for k in os.getenv("LLM_API_KEYS", "").split(",") if k.strip()]
    model = os.getenv("LLM_MODEL", "gemini/gemini-3-flash-preview")
    enable_sim = os.getenv("ENABLE_FAILURE_SIMULATION", "false").lower() == "true"
    return keys, model, enable_sim


def _cache_key(model: str, messages: List[Dict[str, str]]) -> str:
    """Deterministic cache key from model + full message list."""
    raw = json.dumps({"model": model, "messages": messages}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def _key_id(idx: int) -> str:
    return f"key_{idx + 1}"


def _parse_failure_header(header: str) -> Dict[str, int]:
    result: Dict[str, int] = {}
    if not header:
        return result
    for part in header.split(","):
        part = part.strip()
        if "=" not in part:
            continue
        key, code = part.split("=", 1)
        try:
            result[key.strip()] = int(code.strip())
        except ValueError:
            continue
    return result


def _should_simulate(key_id: str, simulations: Dict[str, int]) -> Tuple[bool, int]:
    if "*" in simulations:
        return True, simulations["*"]
    if key_id in simulations:
        return True, simulations[key_id]
    return False, 0


def get_chat_response(
    session_id: str,
    full_messages: List[Dict[str, str]],
    simulate_header: Optional[str] = None,
) -> Dict[str, Any]:
    llm_keys, default_model, enable_sim = _get_config()

    # --- Check cache first ------------------------------------------------
    ck = _cache_key(default_model, full_messages)
    start_time = time.time()

    if ck in _response_cache:
        cached = _response_cache[ck]
        latency_ms = int((time.time() - start_time) * 1000)
        return {
            "session_id": session_id,
            "reply": cached["reply"],
            "metadata": {
                "resolution_source": "LLM_CACHE",
                "model": cached["model"],
                "latency_ms": latency_ms,
                "input_tokens": cached["input_tokens"],
                "output_tokens": cached["output_tokens"],
                "key_id": None,
                "fallback_attempts": 0,
            },
        }

    # --- Parse simulation header ------------------------------------------
    simulations: Dict[str, int] = {}
    if enable_sim and simulate_header:
        simulations = _parse_failure_header(simulate_header)

    fallback_attempts = 0

    for idx, api_key in enumerate(llm_keys):
        kid = _key_id(idx)

        # Simulated failure?
        sim, status = _should_simulate(kid, simulations)
        if sim and status in (429, 500, 502, 503):
            fallback_attempts += 1
            continue

        try:
            call_start = time.time()
            response = litellm.completion(
                model=default_model,
                messages=full_messages,
                api_key=api_key,
            )
            latency_ms = int((time.time() - call_start) * 1000)

            usage = getattr(response, "usage", None)
            input_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
            output_tokens = getattr(usage, "completion_tokens", 0) if usage else 0

            reply = response.choices[0].message.content or ""

            # Store in cache
            _response_cache[ck] = {
                "reply": reply,
                "model": default_model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }

            return {
                "session_id": session_id,
                "reply": reply,
                "metadata": {
                    "resolution_source": "LIVE_INFERENCE",
                    "model": default_model,
                    "latency_ms": latency_ms,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "key_id": kid,
                    "fallback_attempts": fallback_attempts,
                },
            }

        except Exception as e:
            fallback_attempts += 1
            continue

    # All keys exhausted
    raise HTTPException(status_code=503, detail="all providers unavailable")
