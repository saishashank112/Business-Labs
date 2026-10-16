from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional, Type
from pydantic import BaseModel


class LLMError(Exception):
    """Standardized typed LLM error with error code."""

    def __init__(self, code: str, message: str, original: Optional[Exception] = None):
        self.code = code
        self.message = message
        self.original = original
        super().__init__(f"[{code}] {message}")


class LLMResponse(BaseModel):
    text: str
    parsed: Optional[Any] = None
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0
    model: str
    provider: str


class LLMClient(ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_schema: Optional[Type[BaseModel]] = None,
        request_id: Optional[str] = None,
        step: str = "llm_generate",
    ) -> LLMResponse:
        pass
