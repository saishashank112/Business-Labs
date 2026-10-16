"""Tests for RAG answering, citations, and escalation trigger."""

import pytest
from app.database import get_db, init_db
from app.models import Chunk
from ingestion.keyword_index import index_chunks_fts
from retrieval.rag import answer_query, load_rag_prompt


def test_load_rag_prompt():
    """RAG prompt template must load from disk and contain key rules."""
    prompt = load_rag_prompt()
    assert "EVIDENCE-BASED ANSWERING" in prompt
    assert "CITATIONS" in prompt
    assert "INJECTION DEFENSE" in prompt


@pytest.mark.asyncio
async def test_answer_query_creates_escalation_on_missing_evidence():
    """When no evidence matches, an escalation should be created in SQLite."""
    await init_db()

    # Query for something completely unrelated that has no docs
    resp = await answer_query(
        question="xyzabc nonexistent rocket science question 987654321",
        mode="keyword",
    )

    assert resp.status == "insufficient_evidence"
    assert resp.needs_human is True
    assert resp.escalation_id is not None

    # Check escalation in database
    db = await get_db()
    try:
        cursor = await db.execute("SELECT id, status FROM escalations WHERE id = ?", (resp.escalation_id,))
        row = await cursor.fetchone()
        assert row is not None
        assert row["status"] == "open"
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_answer_query_with_evidence(monkeypatch):
    """When evidence exists, answer_query returns citations and sources."""
    await init_db()
    from unittest.mock import AsyncMock, MagicMock
    from llm.interface import LLMResponse
    from app.models import RAGAnswerOutput

    answer_content = "Yes, Brilliant Directories provides free Let's Encrypt SSL certificates automatically [SSL & HTTPS FAQ](https://support.brilliantdirectories.com/articles/ssl-faq)."
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=LLMResponse(
        text=answer_content,
        parsed=RAGAnswerOutput(sufficient_evidence=True, answer=answer_content),
        input_tokens=100,
        output_tokens=50,
        latency_ms=150,
        model="gemini-2.5-flash",
        provider="gemini",
    ))
    monkeypatch.setattr("retrieval.rag.get_llm_client", lambda step: mock_llm)

    chunk = Chunk(
        chunk_id="c_ssl_1",
        article_id="art_ssl",
        url="https://support.brilliantdirectories.com/articles/ssl-faq",
        title="SSL & HTTPS FAQ",
        heading="Free SSL Certificates",
        content="Brilliant Directories provides free Let's Encrypt SSL certificates automatically for all domains.",
        chunk_index=0,
    )
    await index_chunks_fts([chunk])

    resp = await answer_query(
        question="Does Brilliant Directories provide free SSL?",
        mode="keyword",
    )

    assert resp.status == "answered"
    assert resp.needs_human is False
    assert len(resp.sources) >= 1
    assert "SSL & HTTPS FAQ" in [s.title for s in resp.sources]
    assert resp.request_id is not None


@pytest.mark.asyncio
async def test_rag_status_error_on_generic_llm_failure(monkeypatch):
    """When LLM generation fails, status must be 'error' (never 'answered') and no escalation ticket created."""
    await init_db()
    from unittest.mock import AsyncMock, MagicMock
    from llm.interface import LLMError

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(side_effect=LLMError(code="LLM_UNAVAILABLE", message="Provider connection refused"))
    monkeypatch.setattr("retrieval.rag.get_llm_client", lambda step: mock_llm)

    resp = await answer_query(
        question="Does Brilliant Directories provide free SSL?",
        mode="keyword",
    )

    assert resp.status == "error"
    assert resp.status != "answered"
    assert resp.error_code == "LLM_UNAVAILABLE"
    assert resp.needs_human is True
    assert resp.escalation_id is None  # Infra errors must NOT create human escalation tickets


@pytest.mark.asyncio
async def test_rag_status_error_on_429_rate_limit(monkeypatch):
    """When provider returns 429 rate limit, status must be 'error' with code RATE_LIMITED."""
    await init_db()
    from unittest.mock import AsyncMock, MagicMock
    from llm.interface import LLMError

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(side_effect=LLMError(code="RATE_LIMITED", message="429 Resource Exhausted"))
    monkeypatch.setattr("retrieval.rag.get_llm_client", lambda step: mock_llm)

    resp = await answer_query(
        question="Does Brilliant Directories provide free SSL?",
        mode="keyword",
    )

    assert resp.status == "error"
    assert resp.status != "answered"
    assert resp.error_code == "RATE_LIMITED"
    assert resp.needs_human is True
    assert resp.escalation_id is None


@pytest.mark.asyncio
async def test_rag_status_error_on_503_service_unavailable(monkeypatch):
    """When provider returns 503, status must be 'error' (never 'answered') and error_code is LLM_UNAVAILABLE."""
    await init_db()
    from unittest.mock import AsyncMock, MagicMock
    from llm.interface import LLMError

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(side_effect=LLMError(code="LLM_UNAVAILABLE", message="503 Service Unavailable"))
    monkeypatch.setattr("retrieval.rag.get_llm_client", lambda step: mock_llm)

    resp = await answer_query(
        question="Does Brilliant Directories provide free SSL?",
        mode="keyword",
    )

    assert resp.status == "error"
    assert resp.status != "answered"
    assert resp.error_code == "LLM_UNAVAILABLE"
    assert resp.needs_human is True
    assert resp.escalation_id is None


@pytest.mark.asyncio
async def test_rag_fallback_on_404_model_unavailable(monkeypatch):
    """When primary model returns 404, provider switches to fallback model. If all fail, status is error."""
    from unittest.mock import MagicMock
    from llm.gemini_provider import GeminiProvider
    from pydantic import BaseModel
    from app.config import settings

    monkeypatch.setattr(settings, "llm_cache_enabled", False)

    provider = GeminiProvider(model_name="nonexistent-primary-model")
    provider.fallback_model = "operational-fallback-model"

    mock_client = MagicMock()
    calls = []

    def mock_generate_content(model, contents, config=None):
        calls.append(model)
        if model == "nonexistent-primary-model":
            raise Exception("404 NOT_FOUND: model not found")
        # Fallback model succeeds
        mock_resp = MagicMock()
        mock_resp.text = "Answer from fallback model"
        mock_resp.usage_metadata = None
        return mock_resp

    mock_client.models.generate_content = mock_generate_content
    monkeypatch.setattr(provider, "_get_client", lambda: mock_client)

    result = await provider.generate(prompt="Test prompt", step="rag_answer")
    assert result.text == "Answer from fallback model"
    assert "nonexistent-primary-model" in calls
    assert "operational-fallback-model" in calls
    assert result.model == "operational-fallback-model"


@pytest.mark.asyncio
async def test_rag_retry_and_error_on_invalid_json_output(monkeypatch):
    """When structured JSON output is invalid, retries once and then returns status='error' with INVALID_OUTPUT."""
    await init_db()
    from unittest.mock import AsyncMock, MagicMock
    from llm.interface import LLMError

    # Simulate GeminiProvider failing schema validation after retry
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(side_effect=LLMError(code="INVALID_OUTPUT", message="Failed to parse output schema"))
    monkeypatch.setattr("retrieval.rag.get_llm_client", lambda step: mock_llm)

    resp = await answer_query(
        question="Does Brilliant Directories provide free SSL?",
        mode="keyword",
    )

    assert resp.status == "error"
    assert resp.status != "answered"
    assert resp.error_code == "INVALID_OUTPUT"
    assert resp.needs_human is True
    assert resp.escalation_id is None


@pytest.mark.asyncio
async def test_rag_insufficient_evidence_wording_1_i_dont_know(monkeypatch):
    """Model wording 1: 'I don't know' with sufficient_evidence=False sets status='insufficient_evidence'."""
    await init_db()
    from unittest.mock import AsyncMock, MagicMock
    from llm.interface import LLMResponse
    from app.models import RAGAnswerOutput

    answer_text = "I do not know based on the provided documentation."
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=LLMResponse(
        text=answer_text,
        parsed=RAGAnswerOutput(sufficient_evidence=False, answer=answer_text),
        input_tokens=80,
        output_tokens=20,
        latency_ms=120,
        model="gemini-2.5-flash",
        provider="gemini",
    ))
    monkeypatch.setattr("retrieval.rag.get_llm_client", lambda step: mock_llm)

    resp = await answer_query(question="Does Brilliant Directories provide free SSL?", mode="keyword")
    assert resp.status == "insufficient_evidence"
    assert resp.needs_human is True
    assert resp.escalation_id is not None


@pytest.mark.asyncio
async def test_rag_insufficient_evidence_wording_2_no_details(monkeypatch):
    """Model wording 2: 'Context does not contain enough details' with sufficient_evidence=False."""
    await init_db()
    from unittest.mock import AsyncMock, MagicMock
    from llm.interface import LLMResponse
    from app.models import RAGAnswerOutput

    answer_text = "The retrieved context does not contain information regarding custom kernel compilation."
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=LLMResponse(
        text=answer_text,
        parsed=RAGAnswerOutput(sufficient_evidence=False, answer=answer_text),
        input_tokens=80,
        output_tokens=20,
        latency_ms=120,
        model="gemini-2.5-flash",
        provider="gemini",
    ))
    monkeypatch.setattr("retrieval.rag.get_llm_client", lambda step: mock_llm)

    resp = await answer_query(question="Does Brilliant Directories provide free SSL?", mode="keyword")
    assert resp.status == "insufficient_evidence"
    assert resp.needs_human is True
    assert resp.escalation_id is not None


@pytest.mark.asyncio
async def test_rag_insufficient_evidence_wording_3_unable_to_answer(monkeypatch):
    """Model wording 3: 'Unable to answer' with sufficient_evidence=False."""
    await init_db()
    from unittest.mock import AsyncMock, MagicMock
    from llm.interface import LLMResponse
    from app.models import RAGAnswerOutput

    answer_text = "I am unable to answer this question because this feature is not mentioned in the documentation."
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=LLMResponse(
        text=answer_text,
        parsed=RAGAnswerOutput(sufficient_evidence=False, answer=answer_text),
        input_tokens=80,
        output_tokens=20,
        latency_ms=120,
        model="gemini-2.5-flash",
        provider="gemini",
    ))
    monkeypatch.setattr("retrieval.rag.get_llm_client", lambda step: mock_llm)

    resp = await answer_query(question="Does Brilliant Directories provide free SSL?", mode="keyword")
    assert resp.status == "insufficient_evidence"
    assert resp.needs_human is True
    assert resp.escalation_id is not None


@pytest.mark.asyncio
async def test_rag_legitimate_answer_containing_no_information_phrase(monkeypatch):
    """A legitimate answer containing the phrase 'no information' in another sense must be answered, NOT insufficient_evidence."""
    await init_db()
    from unittest.mock import AsyncMock, MagicMock
    from llm.interface import LLMResponse
    from app.models import RAGAnswerOutput

    # Notice: contains 'no information', but sufficient_evidence=True
    legitimate_answer = (
        "Brilliant Directories ensures that no information about customer credit card numbers "
        "is stored on unencrypted storage volumes [Security Best Practices](https://support.brilliantdirectories.com/articles/ssl-faq)."
    )
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=LLMResponse(
        text=legitimate_answer,
        parsed=RAGAnswerOutput(sufficient_evidence=True, answer=legitimate_answer),
        input_tokens=100,
        output_tokens=40,
        latency_ms=150,
        model="gemini-2.5-flash",
        provider="gemini",
    ))
    monkeypatch.setattr("retrieval.rag.get_llm_client", lambda step: mock_llm)

    resp = await answer_query(question="Does Brilliant Directories provide free SSL?", mode="keyword")
    assert resp.status == "answered"
    assert resp.needs_human is False
    assert resp.escalation_id is None
    assert "no information" in resp.answer.lower()


@pytest.mark.asyncio
async def test_rag_status_error_on_daily_quota_exhausted(monkeypatch):
    """When Gemini returns per-day quota exhaustion, status must be 'error' with QUOTA_EXHAUSTED."""
    await init_db()
    from unittest.mock import AsyncMock, MagicMock
    from llm.interface import LLMError

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(side_effect=LLMError(
        code="QUOTA_EXHAUSTED",
        message="Gemini daily quota exhausted: 429 RESOURCE_EXHAUSTED: Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 20",
    ))
    monkeypatch.setattr("retrieval.rag.get_llm_client", lambda step: mock_llm)

    resp = await answer_query(question="Does Brilliant Directories provide free SSL?", mode="keyword")
    assert resp.status == "error"
    assert resp.error_code == "QUOTA_EXHAUSTED"
    assert resp.needs_human is True
    assert resp.escalation_id is None


@pytest.mark.asyncio
async def test_llm_cache_toggle_and_hit():
    """Verify that LLM caching saves responses and returns cache hits when enabled."""
    from llm.cache import compute_cache_key, get_cached_response, set_cached_response, init_cache_db
    from app.config import settings

    await init_cache_db()
    key = compute_cache_key("test-model", "test-step", "sys", "hello world")
    
    # Write to cache
    await set_cached_response(key, "test-model", "test-step", {"text": "cached answer", "input_tokens": 10, "output_tokens": 5})

    # Read from cache with cache enabled
    settings.llm_cache_enabled = True
    cached = await get_cached_response(key)
    assert cached is not None
    assert cached["text"] == "cached answer"

    # Read with cache disabled
    settings.llm_cache_enabled = False
    cached_disabled = await get_cached_response(key)
    assert cached_disabled is None

    # Reset
    settings.llm_cache_enabled = True


@pytest.mark.asyncio
async def test_gemini_provider_detects_real_daily_quota_error(monkeypatch):
    """Real QuotaId GenerateRequestsPerDayPerProjectPerModel-FreeTier immediately raises QUOTA_EXHAUSTED without retries."""
    from unittest.mock import MagicMock
    from llm.gemini_provider import GeminiProvider
    from llm.interface import LLMError
    from app.config import settings

    monkeypatch.setattr(settings, "llm_cache_enabled", False)
    provider = GeminiProvider(model_name="gemini-2.5-flash")
    provider.fallback_model = "gemini-flash-latest"

    mock_client = MagicMock()
    call_count = 0

    real_error_text = (
        "429 RESOURCE_EXHAUSTED: Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, "
        "limit: 20, model: gemini-2.5-flash. QuotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier. Please retry in 13h56m."
    )

    def mock_generate_content(model, contents, config=None):
        nonlocal call_count
        call_count += 1
        raise Exception(real_error_text)

    mock_client.models.generate_content = mock_generate_content
    monkeypatch.setattr(provider, "_get_client", lambda: mock_client)

    with pytest.raises(LLMError) as exc_info:
        await provider.generate(prompt="Test prompt", step="rag_answer")

    assert exc_info.value.code == "QUOTA_EXHAUSTED"
    # Crucial: daily quota must NOT retry with backoff or switch to fallback
    assert call_count == 1


@pytest.mark.asyncio
async def test_gemini_provider_retries_per_minute_429_with_backoff(monkeypatch):
    """A per-minute 429 containing 'retry in 30 seconds' is retried with backoff and succeeds on subsequent attempt."""
    from unittest.mock import MagicMock
    from llm.gemini_provider import GeminiProvider
    from app.config import settings
    import asyncio

    monkeypatch.setattr(settings, "llm_cache_enabled", False)
    # Fast-forward asyncio.sleep to avoid waiting real seconds in unit tests
    sleep_calls = []
    async def mock_sleep(seconds):
        sleep_calls.append(seconds)
    monkeypatch.setattr(asyncio, "sleep", mock_sleep)

    provider = GeminiProvider(model_name="gemini-2.5-flash")
    mock_client = MagicMock()
    call_count = 0

    rate_limit_error_text = "429 RESOURCE_EXHAUSTED: Rate limit exceeded. Please retry in 30 seconds."

    def mock_generate_content(model, contents, config=None):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception(rate_limit_error_text)
        mock_resp = MagicMock()
        mock_resp.text = "Success on attempt 3"
        mock_resp.usage_metadata = None
        return mock_resp

    mock_client.models.generate_content = mock_generate_content
    monkeypatch.setattr(provider, "_get_client", lambda: mock_client)

    result = await provider.generate(prompt="Test prompt", step="rag_answer")
    assert result.text == "Success on attempt 3"
    assert call_count == 3
    # Confirms exponential backoff was triggered (1.0s, 2.0s)
    assert len(sleep_calls) == 2
    assert sleep_calls[0] == 1.0
    assert sleep_calls[1] == 2.0

