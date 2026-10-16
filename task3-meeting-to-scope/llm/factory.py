from __future__ import annotations

import logging
from app.config import settings
from llm.interface import LLMClient, LLMResponse
from llm.gemini_provider import GeminiProvider
from llm.claude_provider import ClaudeProvider

logger = logging.getLogger(__name__)


class MockLLMClient(LLMClient):
    async def generate(self, prompt: str, system_prompt=None, response_schema=None, request_id=None, step="mock") -> LLMResponse:
        logger.info("MockLLMClient called in Task 3 for step: %s", step)
        return LLMResponse(
            text="Mock response for Task 3 agent pipeline.",
            model="mock-task3",
            provider="mock",
            input_tokens=100,
            output_tokens=50,
            latency_ms=10,
            cost_usd=0.0,
        )


def get_llm_client(step: str = "scope") -> LLMClient:
    profile = settings.profile.lower()

    if profile == "final" and settings.claude_api_key and step in ("scope", "proposal"):
        return ClaudeProvider()

    if settings.gemini_api_key:
        return GeminiProvider()

    if settings.claude_api_key:
        return ClaudeProvider()

    return MockLLMClient()
