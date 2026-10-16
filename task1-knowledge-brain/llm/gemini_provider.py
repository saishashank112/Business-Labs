"""Gemini LLM Provider using the google-genai SDK."""

from __future__ import annotations

import time
import logging
from typing import Optional, Type, Any
from pydantic import BaseModel

from app.config import settings
from llm.interface import LLMClient, LLMResponse, LLMError
from llm.logger import log_llm_call, estimate_cost

logger = logging.getLogger(__name__)


import asyncio


class GeminiProvider(LLMClient):
    """Google Gemini model provider using google-genai SDK."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.t1_rag_model
        self.fallback_model = getattr(settings, "t1_fallback_model", None)
        self.api_key = settings.gemini_api_key

    def _get_client(self):
        if not self.api_key:
            raise LLMError(
                code="LLM_UNAVAILABLE",
                message="GEMINI_API_KEY is not set. Please set GEMINI_API_KEY in .env",
            )
        from google import genai
        return genai.Client(api_key=self.api_key)

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_schema: Optional[Type[BaseModel]] = None,
        request_id: Optional[str] = None,
        step: str = "rag_answer",
    ) -> LLMResponse:
        """Call Gemini to generate text or structured schema output with retries and fallback."""
        start_time = time.time()
        client = self._get_client()

        # Build config
        config: dict[str, Any] = {}
        if system_prompt:
            config["system_instruction"] = system_prompt
        if response_schema:
            config["response_mime_type"] = "application/json"
            config["response_schema"] = response_schema

        # Check response cache if enabled
        cache_key = None
        schema_name = response_schema.__name__ if response_schema else None
        if getattr(settings, "llm_cache_enabled", True):
            from llm.cache import compute_cache_key, get_cached_response, set_cached_response
            cache_key = compute_cache_key(self.model_name, step, system_prompt, prompt, schema_name)
            cached_data = await get_cached_response(cache_key)
            if cached_data:
                logger.info("LLM cache hit for step '%s' (key=%s)", step, cache_key[:12])
                parsed = None
                if response_schema and cached_data.get("parsed"):
                    try:
                        parsed = response_schema.model_validate(cached_data["parsed"])
                    except Exception:
                        parsed = None
                return LLMResponse(
                    text=cached_data.get("text", ""),
                    parsed=parsed,
                    input_tokens=cached_data.get("input_tokens", 0),
                    output_tokens=cached_data.get("output_tokens", 0),
                    latency_ms=0,
                    cost_usd=0.0,
                    model=cached_data.get("model", self.model_name),
                    provider=cached_data.get("provider", "gemini"),
                )

        models_to_try = [self.model_name]
        if self.fallback_model and self.fallback_model not in models_to_try:
            models_to_try.append(self.fallback_model)

        last_error = None
        for current_model in models_to_try:
            for attempt in range(3):
                try:
                    response = client.models.generate_content(
                        model=current_model,
                        contents=prompt,
                        config=config if config else None,
                    )

                    latency_ms = int((time.time() - start_time) * 1000)
                    text = response.text or ""

                    # Extract usage metadata
                    input_tokens = 0
                    output_tokens = 0
                    if hasattr(response, "usage_metadata") and response.usage_metadata:
                        input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
                        output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

                    cost_usd = estimate_cost("gemini", current_model, input_tokens, output_tokens)

                    # Parse schema if requested
                    parsed = None
                    if response_schema:
                        try:
                            parsed = response_schema.model_validate_json(text)
                        except Exception as parse_err:
                            logger.warning("Schema parsing failed on attempt %d: %s", attempt + 1, parse_err)
                            if attempt == 0:
                                # Retry once on invalid output format
                                continue
                            raise LLMError(code="INVALID_OUTPUT", message="Failed to parse output schema", original=parse_err)

                    # Log to SQLite
                    await log_llm_call(
                        request_id=request_id,
                        step=step,
                        model=current_model,
                        provider="gemini",
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        latency_ms=latency_ms,
                        cost_usd=cost_usd,
                    )

                    # Save to cache if enabled
                    if cache_key and getattr(settings, "llm_cache_enabled", True):
                        from llm.cache import set_cached_response
                        resp_dict = {
                            "text": text,
                            "parsed": parsed.model_dump() if parsed and hasattr(parsed, "model_dump") else None,
                            "input_tokens": input_tokens,
                            "output_tokens": output_tokens,
                            "model": current_model,
                            "provider": "gemini",
                        }
                        await set_cached_response(cache_key, current_model, step, resp_dict)

                    logger.info(
                        "LLM answered using model '%s' for step '%s' (request_id=%s, latency=%dms)",
                        current_model,
                        step,
                        request_id,
                        latency_ms,
                    )

                    return LLMResponse(
                        text=text,
                        parsed=parsed,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        latency_ms=latency_ms,
                        cost_usd=cost_usd,
                        model=current_model,
                        provider="gemini",
                    )
                except Exception as e:
                    err_str = str(e).lower()
                    last_error = e
                    if isinstance(e, LLMError):
                        raise

                    # Distinguish per-day quota exhaustion (do not retry, do not switch fallback)
                    # QuotaId or metric containing 'PerDay' indicates project/model daily quota exhaustion
                    is_daily_quota = "perday" in err_str
                    if is_daily_quota:
                        logger.error("Gemini daily quota exhausted (QuotaId/metric contains PerDay): %s", e)
                        raise LLMError(
                            code="QUOTA_EXHAUSTED",
                            message=f"Gemini daily quota exhausted: {e}",
                            original=e,
                        )

                    if "404" in err_str or "not_found" in err_str:
                        logger.warning("Model '%s' returned 404 NOT_FOUND. Attempting fallback model...", current_model)
                        break
                    elif "429" in err_str or "resource_exhausted" in err_str or "503" in err_str or "unavailable" in err_str:
                        if attempt == 2 and len(models_to_try) > 1 and current_model == models_to_try[0]:
                            logger.warning(
                                "Model '%s' exhausted 3 retries under rate limit/service spike (%s). Switching to fallback model '%s'...",
                                current_model,
                                e,
                                models_to_try[1],
                            )
                            break
                        backoff = 1.0 * (2 ** attempt)
                        logger.warning("Gemini transient rate limit / service spike (%s). Retrying in %.1fs (attempt %d/3)...", e, backoff, attempt + 1)
                        await asyncio.sleep(backoff)
                        continue
                    elif "timeout" in err_str or "deadline" in err_str:
                        raise LLMError(code="TIMEOUT", message=str(e), original=e)
                    else:
                        raise LLMError(code="INTERNAL_ERROR", message=str(e), original=e)

        # All models and retries exhausted
        err_msg = str(last_error) if last_error else "LLM service unavailable"
        lower_err = err_msg.lower()
        if "perday" in lower_err:
            code = "QUOTA_EXHAUSTED"
        elif "429" in lower_err or "resource_exhausted" in lower_err:
            code = "RATE_LIMITED"
        elif "404" in lower_err or "not_found" in lower_err or "503" in lower_err or "unavailable" in lower_err:
            code = "LLM_UNAVAILABLE"
        elif "timeout" in lower_err or "deadline" in lower_err:
            code = "TIMEOUT"
        else:
            code = "INTERNAL_ERROR"

        raise LLMError(code=code, message=err_msg, original=last_error)

    async def generate_vision(
        self,
        prompt: str,
        image_bytes: bytes,
        mime_type: str = "image/png",
        request_id: Optional[str] = None,
        step: str = "image_describe",
    ) -> LLMResponse:
        """Call Gemini Vision model with prompt and image bytes."""
        start_time = time.time()
        client = self._get_client()

        from google.genai import types

        part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

        try:
            response = client.models.generate_content(
                model=settings.t1_image_model,
                contents=[prompt, part],
            )
            latency_ms = int((time.time() - start_time) * 1000)
            text = response.text or ""

            input_tokens = 0
            output_tokens = 0
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
                output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

            cost_usd = estimate_cost("gemini", settings.t1_image_model, input_tokens, output_tokens)

            await log_llm_call(
                request_id=request_id,
                step=step,
                model=settings.t1_image_model,
                provider="gemini",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                cost_usd=cost_usd,
            )

            return LLMResponse(
                text=text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                cost_usd=cost_usd,
                model=settings.t1_image_model,
                provider="gemini",
            )
        except Exception as e:
            logger.error("Gemini Vision failed: %s", e)
            raise


_health_cache: dict[str, Any] = {"status": "unchecked", "model": "", "timestamp": 0}


async def check_model_availability(model_name: Optional[str] = None) -> dict[str, Any]:
    """Check if configured model (or fallback) is available in Gemini API."""
    global _health_cache
    model = model_name or settings.t1_rag_model
    fallback = getattr(settings, "t1_fallback_model", None)

    if not settings.gemini_api_key:
        logger.error("Health check: GEMINI_API_KEY is not configured.")
        result = {"status": "unavailable", "model": model, "error": "MISSING_API_KEY"}
        _health_cache = {**result, "timestamp": time.time()}
        return result

    from google import genai
    client = genai.Client(api_key=settings.gemini_api_key)

    try:
        # Check primary model
        client.models.get(model=model)
        logger.info("Startup/Health check: Configured model '%s' is AVAILABLE.", model)
        result = {"status": "available", "model": model, "fallback": fallback}
        _health_cache = {**result, "timestamp": time.time()}
        return result
    except Exception as e:
        err_msg = str(e).lower()
        if "404" in err_msg or "not_found" in err_msg:
            logger.error("Startup/Health check: Configured model '%s' is UNAVAILABLE (404 Not Found)!", model)
            if fallback:
                try:
                    client.models.get(model=fallback)
                    logger.warning("Startup/Health check: Fallback model '%s' is AVAILABLE and active.", fallback)
                    result = {"status": "fallback_active", "model": model, "fallback": fallback, "error": "404_NOT_FOUND"}
                    _health_cache = {**result, "timestamp": time.time()}
                    return result
                except Exception as fb_err:
                    logger.error("Startup/Health check: Fallback model '%s' also failed: %s", fallback, fb_err)
            result = {"status": "unavailable", "model": model, "error": "404_NOT_FOUND"}
            _health_cache = {**result, "timestamp": time.time()}
            return result
        else:
            logger.warning("Startup/Health check: Model check returned %s", e)
            result = {"status": "available", "model": model, "note": str(e)}
            _health_cache = {**result, "timestamp": time.time()}
            return result


async def get_model_health() -> dict[str, Any]:
    """Cached health status for /health endpoint (refreshes if older than 60s)."""
    global _health_cache
    now = time.time()
    if now - _health_cache.get("timestamp", 0) > 60:
        return await check_model_availability()
    return _health_cache

