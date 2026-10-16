"""Tests for the crawler module — unit tests that don't hit the network."""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from ingestion.crawler import CrawlResult, load_robots_txt


def test_crawl_result_creation() -> None:
    """CrawlResult should store url, status, and optional fields."""
    result = CrawlResult(url="https://example.com", status="fetched", html="<html></html>")
    assert result.url == "https://example.com"
    assert result.status == "fetched"
    assert result.html == "<html></html>"
    assert result.error is None


def test_crawl_result_failed() -> None:
    """A failed CrawlResult should store the error message."""
    result = CrawlResult(url="https://example.com", status="failed", error="timeout")
    assert result.status == "failed"
    assert result.error == "timeout"
    assert result.html is None


@pytest.mark.asyncio
async def test_load_robots_txt_handles_failure() -> None:
    """If robots.txt can't be fetched, the parser should allow all URLs."""
    with patch("ingestion.crawler.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Network error")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        rp = await load_robots_txt("https://example.com")
        # Should not crash — and should have allow_all set
        assert rp is not None
