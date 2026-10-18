"""Anthropic Claude LLM Provider in Task 3."""

from __future__ import annotations

import json
import time
import logging
from typing import Optional, Type, Any
from pydantic import BaseModel

from app.config import settings
from llm.interface import LLMClient, LLMResponse, LLMError
from llm.logger import log_llm_call, estimate_cost
from llm.cache import compute_cache_key, get_cached_response, set_cached_response
from llm.claude_budget import check_claude_budget, record_claude_call, get_claude_budget_summary

logger = logging.getLogger(__name__)


async def verify_claude_models(api_key: str, model_ids: list[str]) -> dict:
    """Check configured Claude model IDs against Anthropic models list endpoint."""
    if not api_key:
        return {"status": "unconfigured", "models": {m: "no_key" for m in model_ids}}
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key)
        models_resp = await client.models.list()
        available_ids = {m.id for m in models_resp.data}
        return {
            "status": "verified",
            "models": {m: (m in available_ids) for m in model_ids},
            "available_count": len(available_ids),
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "models": {m: "unverified" for m in model_ids}}


class ClaudeProvider(LLMClient):
    """Anthropic Claude model provider using anthropic SDK."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or getattr(settings, "t3_claude_model", "claude-haiku-placeholder")
        self.api_key = getattr(settings, "anthropic_api_key", "") or getattr(settings, "claude_api_key", "")

    def _get_client(self):
        if not self.api_key:
            raise LLMError(
                code="LLM_UNAVAILABLE",
                message="ANTHROPIC_API_KEY is not set. Please configure ANTHROPIC_API_KEY in .env",
            )
        import anthropic
        return anthropic.AsyncAnthropic(api_key=self.api_key)

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_schema: Optional[Type[BaseModel]] = None,
        request_id: Optional[str] = None,
        step: str = "llm_generate",
    ) -> LLMResponse:
        start_time = time.time()
        sys_msg = system_prompt or ""
        schema_name = response_schema.__name__ if response_schema else None

        # Check response cache
        cache_key = None
        if getattr(settings, "llm_cache_enabled", True):
            cache_key = compute_cache_key(self.model_name, step, sys_msg, prompt, schema_name)
            cached_data = await get_cached_response(cache_key)
            if cached_data:
                logger.info("Task 3 Claude cache hit for step '%s' [%s]", step, cache_key[:8])
                parsed = None
                if response_schema and cached_data.get("parsed"):
                    try:
                        parsed = response_schema.model_validate(cached_data["parsed"])
                    except Exception:
                        pass
                return LLMResponse(
                    text=cached_data.get("text", ""),
                    parsed=parsed,
                    input_tokens=cached_data.get("input_tokens", 0),
                    output_tokens=cached_data.get("output_tokens", 0),
                    latency_ms=cached_data.get("latency_ms", 5),
                    cost_usd=cached_data.get("cost_usd", 0.0),
                    model=cached_data.get("model", self.model_name),
                    provider="claude",
                )

        client = self._get_client()

        formatted_system = sys_msg
        if response_schema:
            formatted_system += (
                f"\nYou must output strictly valid JSON conforming to this schema:\n"
                f"{json.dumps(response_schema.model_json_schema(), indent=2)}\n"
                "Do NOT wrap in markdown formatting or code blocks. Output raw JSON only."
            )

        last_error = None
        for attempt in range(2):
            try:
                kwargs: dict[str, Any] = {
                    "model": self.model_name,
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}],
                }
                if formatted_system.strip():
                    kwargs["system"] = formatted_system.strip()

                check_claude_budget()
                response = await client.messages.create(**kwargs)
                latency_ms = int((time.time() - start_time) * 1000)

                text = "".join([b.text for b in response.content if hasattr(b, "text")])
                input_tokens = response.usage.input_tokens if hasattr(response, "usage") else 0
                output_tokens = response.usage.output_tokens if hasattr(response, "usage") else 0
                cost_usd = record_claude_call("task3", step, self.model_name, input_tokens, output_tokens, request_id)

                parsed = None
                if response_schema:
                    cleaned_text = text.strip()
                    if cleaned_text.startswith("```"):
                        lines = cleaned_text.split("\n")
                        cleaned_text = "\n".join(lines[1:-1]).strip()
                    try:
                        parsed = response_schema.model_validate_json(cleaned_text)
                    except Exception as parse_err:
                        logger.warning("Claude JSON parsing failed (attempt %d/2): %s", attempt + 1, parse_err)
                        if attempt == 0:
                            prompt += f"\nYour previous output was invalid JSON: {parse_err}. Re-output strictly valid JSON."
                            continue
                        raise LLMError(
                            code="INVALID_OUTPUT",
                            message=f"Failed to parse Claude response into schema: {parse_err}",
                            original=parse_err,
                        )

                # Store in cache
                if cache_key and getattr(settings, "llm_cache_enabled", True):
                    resp_dict = {
                        "text": text,
                        "parsed": parsed.model_dump() if parsed else None,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "latency_ms": latency_ms,
                        "cost_usd": cost_usd,
                        "model": self.model_name,
                    }
                    await set_cached_response(cache_key, self.model_name, step, resp_dict)

                await log_llm_call(
                    request_id=request_id,
                    step=step,
                    model=self.model_name,
                    provider="claude",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    cost_usd=cost_usd,
                )

                return LLMResponse(
                    text=text,
                    parsed=parsed,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    cost_usd=cost_usd,
                    model=self.model_name,
                    provider="claude",
                )

            except Exception as e:
                last_error = e
                err_str = str(e).lower()

                if isinstance(e, LLMError):
                    raise

                if "rate_limit" in err_str or "429" in err_str:
                    if "credit" in err_str or "balance" in err_str or "quota" in err_str or "perday" in err_str:
                        raise LLMError(code="QUOTA_EXHAUSTED", message=str(e), original=e)
                    raise LLMError(code="RATE_LIMITED", message=str(e), original=e)

                if "overloaded" in err_str or "529" in err_str or "503" in err_str or "unavailable" in err_str:
                    raise LLMError(code="LLM_UNAVAILABLE", message=str(e), original=e)

                if "timeout" in err_str or "connection" in err_str:
                    raise LLMError(code="TIMEOUT", message=str(e), original=e)

                if "invalid json" in err_str:
                    raise LLMError(code="INVALID_OUTPUT", message=str(e), original=e)

                logger.error("Claude call failed in Task 3: %s", e)
                raise LLMError(code="INTERNAL_ERROR", message=str(e), original=e)

        raise LLMError(code="INTERNAL_ERROR", message=f"Claude call failed: {last_error}", original=last_error)
