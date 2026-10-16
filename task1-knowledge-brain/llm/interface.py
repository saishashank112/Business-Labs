"""Provider-agnostic LLM interface.

Allows switching between Gemini and Claude via .env settings
without modifying caller logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional, Type
from pydantic import BaseModel


class LLMResponse(BaseModel):
    """Normalized response from any LLM provider."""
    text: str
    parsed: Optional[Any] = None
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0
    model: str
    provider: str


class LLMError(Exception):
    """Structured LLM exception with standard error code."""
    def __init__(self, code: str, message: str, original: Optional[Exception] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.original = original


class LLMClient(ABC):
    """Abstract base class for all LLM providers."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_schema: Optional[Type[BaseModel]] = None,
        request_id: Optional[str] = None,
        step: str = "llm_generate",
    ) -> LLMResponse:
        """Generate text from a prompt, optionally enforcing a Pydantic schema."""
        pass

    @abstractmethod
    async def generate_vision(
        self,
        prompt: str,
        image_bytes: bytes,
        mime_type: str = "image/png",
        request_id: Optional[str] = None,
        step: str = "vision",
    ) -> LLMResponse:
        """Analyze an image with vision capabilities."""
        pass
