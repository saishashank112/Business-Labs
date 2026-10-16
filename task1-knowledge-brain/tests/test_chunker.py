"""Tests for the heading-based chunker."""

from app.models import ParsedArticle
from ingestion.chunker import chunk_article, generate_chunk_id, estimate_tokens


def test_chunk_id_stability():
    """Deterministic chunk ID generation should produce identical output for same inputs."""
    id1 = generate_chunk_id("https://example.com/art1", ["Title", "Section"], 0)
    id2 = generate_chunk_id("https://example.com/art1", ["Title", "Section"], 0)
    id3 = generate_chunk_id("https://example.com/art1", ["Title", "Section"], 1)

    assert id1 == id2
    assert id1 != id3
    assert len(id1) == 16


def test_chunk_article_heading_hierarchy():
    """Chunking an article with headings should preserve heading path and metadata."""
    article = ParsedArticle(
        id="123",
        url="https://support.brilliantdirectories.com/articles/123-payments",
        title="Payment Gateways",
        headings=["Supported Gateways", "How to Configure PayPal"],
        body=(
            "Overview of payments in Brilliant Directories.\n\n"
            "Supported Gateways\n"
            "We support Stripe, PayPal, Authorize.net, and 2Checkout.\n\n"
            "How to Configure PayPal\n"
            "Go to Settings > Payment Settings and enter your PayPal API credentials."
        ),
        lists=[["Stripe", "PayPal", "Authorize.net"]],
        tables=[],
        images=[{"url": "https://example.com/paypal.png", "nearby_text": "Payment Settings"}],
        content_hash="abc123hash",
        ingested_at="2026-10-16T10:00:00Z",
    )

    chunks = chunk_article(article)
    assert len(chunks) >= 2

    # Check first chunk is overview or section
    assert any("Supported Gateways" in c.heading for c in chunks)
    assert any("How to Configure PayPal" in c.heading for c in chunks)

    # Check stable IDs and token counts
    for c in chunks:
        assert c.chunk_id is not None
        assert c.article_id == "123"
        assert c.url == article.url
        assert c.token_count > 0


def test_chunk_article_preserves_tables_and_images():
    """Tables and image references must be attached to chunks."""
    article = ParsedArticle(
        id="456",
        url="https://support.brilliantdirectories.com/articles/456-pricing",
        title="Pricing Plans",
        headings=[],
        body="Here are the available plans and features for directory members.",
        lists=[],
        tables=[{
            "headers": ["Plan", "Price"],
            "rows": [["Basic", "$10"], ["Premium", "$20"]],
        }],
        images=[{"url": "https://example.com/pricing-chart.png", "nearby_text": "plans and features"}],
        content_hash="def456hash",
        ingested_at="2026-10-16T10:00:00Z",
    )

    chunks = chunk_article(article)
    assert len(chunks) >= 1
    c = chunks[0]
    assert "| Plan | Price |" in c.content
    assert "| Basic | $10 |" in c.content
    assert "https://example.com/pricing-chart.png" in c.image_refs
