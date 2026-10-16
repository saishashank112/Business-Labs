"""Gemini LLM Provider using the google-genai SDK."""

from __future__ import annotations

import time
import logging
from typing import Optional, Type, Any
from pydantic import BaseModel

from app.config import settings
from llm.interface import LLMClient, LLMResponse
from llm.logger import log_llm_call, estimate_cost

logger = logging.getLogger(__name__)


class GeminiProvider(LLMClient):
    """Google Gemini model provider using google-genai SDK."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.t1_rag_model
        self.api_key = settings.gemini_api_key

    def _get_client(self):
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Please set GEMINI_API_KEY in .env"
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
        """Call Gemini to generate text or structured schema output."""
        start_time = time.time()
        client = self._get_client()

        # Build config
        config: dict[str, Any] = {}
        if system_prompt:
            config["system_instruction"] = system_prompt
        if response_schema:
            config["response_mime_type"] = "application/json"
            config["response_schema"] = response_schema

        try:
            # google-genai SDK synchronous or async call
            response = client.models.generate_content(
                model=self.model_name,
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

            cost_usd = estimate_cost("gemini", self.model_name, input_tokens, output_tokens)

            # Parse schema if requested
            parsed = None
            if response_schema:
                try:
                    parsed = response_schema.model_validate_json(text)
                except Exception as parse_err:
                    logger.warning("Could not parse response into schema: %s", parse_err)

            # Log to SQLite
            await log_llm_call(
                request_id=request_id,
                step=step,
                model=self.model_name,
                provider="gemini",
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
                provider="gemini",
            )
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error("Gemini generation failed: %s", e)
            raise

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
