import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import BaseModel

from llm.claude_provider import ClaudeProvider
from llm.interface import LLMError


class DummySchema(BaseModel):
    summary: str
    status: str


@pytest.mark.asyncio
async def test_task3_claude_success(monkeypatch):
    monkeypatch.setattr("app.config.settings.claude_api_key", "mock-key")
    monkeypatch.setattr("app.config.settings.llm_cache_enabled", False)
    provider = ClaudeProvider(model_name="claude-test")

    mock_resp = MagicMock()
    mock_block = MagicMock()
    mock_block.text = "Hello from Task 3 Claude"
    mock_resp.content = [mock_block]
    mock_resp.usage.input_tokens = 120
    mock_resp.usage.output_tokens = 60

    mock_client = AsyncMock()
    mock_client.messages.create.return_value = mock_resp

    with patch("anthropic.AsyncAnthropic", return_value=mock_client):
        res = await provider.generate(prompt="Hi Success Task 3")
        assert res.text == "Hello from Task 3 Claude"
        assert res.input_tokens == 120
        assert res.output_tokens == 60
        assert res.provider == "claude"


@pytest.mark.asyncio
async def test_task3_claude_rate_limit(monkeypatch):
    monkeypatch.setattr("app.config.settings.claude_api_key", "mock-key")
    monkeypatch.setattr("app.config.settings.llm_cache_enabled", False)
    provider = ClaudeProvider(model_name="claude-test")

    mock_client = AsyncMock()
    mock_client.messages.create.side_effect = Exception("429 rate_limit: requests per minute exceeded")

    with patch("anthropic.AsyncAnthropic", return_value=mock_client):
        with pytest.raises(LLMError) as exc_info:
            await provider.generate(prompt="Hi Rate Limit Task 3")
        assert exc_info.value.code == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_task3_claude_quota_exhausted(monkeypatch):
    monkeypatch.setattr("app.config.settings.claude_api_key", "mock-key")
    monkeypatch.setattr("app.config.settings.llm_cache_enabled", False)
    provider = ClaudeProvider(model_name="claude-test")

    mock_client = AsyncMock()
    mock_client.messages.create.side_effect = Exception("429 credit balance too low, quota exceeded")

    with patch("anthropic.AsyncAnthropic", return_value=mock_client):
        with pytest.raises(LLMError) as exc_info:
            await provider.generate(prompt="Hi Quota Task 3")
        assert exc_info.value.code == "QUOTA_EXHAUSTED"


@pytest.mark.asyncio
async def test_task3_claude_overloaded_unavailable(monkeypatch):
    monkeypatch.setattr("app.config.settings.claude_api_key", "mock-key")
    monkeypatch.setattr("app.config.settings.llm_cache_enabled", False)
    provider = ClaudeProvider(model_name="claude-test")

    mock_client = AsyncMock()
    mock_client.messages.create.side_effect = Exception("529 Overloaded: Anthropic is temporarily overloaded")

    with patch("anthropic.AsyncAnthropic", return_value=mock_client):
        with pytest.raises(LLMError) as exc_info:
            await provider.generate(prompt="Hi Overloaded Task 3")
        assert exc_info.value.code == "LLM_UNAVAILABLE"


@pytest.mark.asyncio
async def test_task3_claude_invalid_json(monkeypatch):
    monkeypatch.setattr("app.config.settings.claude_api_key", "mock-key")
    monkeypatch.setattr("app.config.settings.llm_cache_enabled", False)
    provider = ClaudeProvider(model_name="claude-test")

    mock_resp = MagicMock()
    mock_block = MagicMock()
    mock_block.text = "This is not valid json at all"
    mock_resp.content = [mock_block]
    mock_resp.usage.input_tokens = 50
    mock_resp.usage.output_tokens = 20

    mock_client = AsyncMock()
    mock_client.messages.create.return_value = mock_resp

    with patch("anthropic.AsyncAnthropic", return_value=mock_client):
        with pytest.raises(LLMError) as exc_info:
            await provider.generate(prompt="Hi Invalid JSON Task 3", response_schema=DummySchema)
        assert exc_info.value.code == "INVALID_OUTPUT"


@pytest.mark.asyncio
async def test_task3_claude_timeout(monkeypatch):
    monkeypatch.setattr("app.config.settings.claude_api_key", "mock-key")
    monkeypatch.setattr("app.config.settings.llm_cache_enabled", False)
    provider = ClaudeProvider(model_name="claude-test")

    mock_client = AsyncMock()
    mock_client.messages.create.side_effect = Exception("Request timeout: connection dropped after 30s")

    with patch("anthropic.AsyncAnthropic", return_value=mock_client):
        with pytest.raises(LLMError) as exc_info:
            await provider.generate(prompt="Hi Timeout Task 3")
        assert exc_info.value.code == "TIMEOUT"
