"""Factory for creating LLM clients based on profile and environment."""

from __future__ import annotations

import logging
from app.config import settings
from llm.interface import LLMClient, LLMResponse
from llm.gemini_provider import GeminiProvider
from llm.claude_provider import ClaudeProvider

logger = logging.getLogger(__name__)


class MockLLMClient(LLMClient):
    """Fallback mock LLM client when no API keys are configured."""

    async def generate(self, prompt: str, system_prompt=None, response_schema=None, request_id=None, step="mock") -> LLMResponse:
        logger.info("MockLLMClient called (no API keys configured)")
        return LLMResponse(
            text="[Mock LLM Response] System configured without API key. Evidence was retrieved successfully.",
            model="mock-model",
            provider="mock",
            input_tokens=50,
            output_tokens=25,
            latency_ms=10,
            cost_usd=0.0,
        )

    async def generate_vision(self, prompt: str, image_bytes: bytes, mime_type="image/png", request_id=None, step="vision") -> LLMResponse:
        return LLMResponse(
            text="Screenshot of Brilliant Directories settings interface showing configuration options.",
            model="mock-vision",
            provider="mock",
            input_tokens=100,
            output_tokens=20,
            latency_ms=15,
            cost_usd=0.0,
        )


def get_llm_client(step: str = "rag_answer") -> LLMClient:
    """Return the appropriate LLM client based on PROFILE and available API keys."""
    profile = settings.profile.lower()

    # In "final" profile, Claude is preferred for core reasoning
    if profile == "final" and step in ("rag_answer", "core_reasoning") and settings.claude_api_key:
        logger.info("Using ClaudeProvider for step: %s (PROFILE=%s)", step, profile)
        return ClaudeProvider()

    # Otherwise default to Gemini
    if settings.gemini_api_key:
        return GeminiProvider()

    if settings.claude_api_key:
        return ClaudeProvider()

    # Neither key set — fallback to Mock client
    logger.warning("No GEMINI_API_KEY or CLAUDE_API_KEY found in .env. Using MockLLMClient.")
    return MockLLMClient()
