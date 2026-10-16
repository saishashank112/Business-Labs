from __future__ import annotations

import time
import logging
from typing import Optional, Type, Any
from pydantic import BaseModel

from app.config import settings
from llm.interface import LLMClient, LLMResponse
from llm.logger import log_llm_call, estimate_cost

logger = logging.getLogger(__name__)


class ClaudeProvider(LLMClient):
    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or "claude-3-5-sonnet-20241022"
        self.api_key = settings.claude_api_key

    def _get_client(self):
        if not self.api_key:
            raise ValueError("CLAUDE_API_KEY is not set.")
        from anthropic import AsyncAnthropic
        return AsyncAnthropic(api_key=self.api_key)

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_schema: Optional[Type[BaseModel]] = None,
        request_id: Optional[str] = None,
        step: str = "llm_generate",
    ) -> LLMResponse:
        start_time = time.time()
        client = self._get_client()

        sys_msg = system_prompt or ""
        if response_schema:
            sys_msg += f"\nReturn strictly valid JSON matching schema:\n{response_schema.model_json_schema()}"

        try:
            kwargs: dict[str, Any] = {
                "model": self.model_name,
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}],
            }
            if sys_msg.strip():
                kwargs["system"] = sys_msg.strip()

            response = await client.messages.create(**kwargs)
            latency_ms = int((time.time() - start_time) * 1000)

            text = "".join([b.text for b in response.content if hasattr(b, "text")])
            input_tokens = response.usage.input_tokens if hasattr(response, "usage") else 0
            output_tokens = response.usage.output_tokens if hasattr(response, "usage") else 0
            cost_usd = estimate_cost("claude", self.model_name, input_tokens, output_tokens)

            parsed = None
            if response_schema:
                try:
                    cleaned = text.strip()
                    if cleaned.startsWith("```"):
                        lines = cleaned.split("\n")
                        cleaned = "\n".join(lines[1:-1])
                    parsed = response_schema.model_validate_json(cleaned)
                except Exception as err:
                    logger.warning("Could not parse Claude response into schema: %s", err)

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
            logger.error("Claude call failed in Task 3: %s", e)
            raise
