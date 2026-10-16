"""Tests for HTML article parser."""

from ingestion.parser import parse_html_to_article, _extract_article_id


def test_parse_extracts_title(sample_article_html: str) -> None:
    """Should extract the h1 title from the article."""
    article = parse_html_to_article(
        html=sample_article_html,
        url="https://example.com/support/solutions/articles/12345-test",
    )
    assert article is not None
    assert article.title == "How to Set Up Payments"


def test_parse_extracts_headings(sample_article_html: str) -> None:
    """Should find both h2 headings."""
    article = parse_html_to_article(
        html=sample_article_html,
        url="https://example.com/support/solutions/articles/12345-test",
    )
    assert article is not None
    assert len(article.headings) == 2
    assert "Step 1: Go to Settings" in article.headings
    assert "Step 2: Test a Payment" in article.headings


def test_parse_extracts_body_text(sample_article_html: str) -> None:
    """Should include paragraph text in the body."""
    article = parse_html_to_article(
        html=sample_article_html,
        url="https://example.com/support/solutions/articles/12345-test",
    )
    assert article is not None
    assert "Navigate to Admin" in article.body


def test_parse_extracts_lists(sample_article_html: str) -> None:
    """Should extract the list items."""
    article = parse_html_to_article(
        html=sample_article_html,
        url="https://example.com/support/solutions/articles/12345-test",
    )
    assert article is not None
    assert len(article.lists) >= 1
    assert "Select your payment gateway" in article.lists[0]


def test_parse_extracts_tables(sample_article_html: str) -> None:
    """Should extract table headers and rows."""
    article = parse_html_to_article(
        html=sample_article_html,
        url="https://example.com/support/solutions/articles/12345-test",
    )
    assert article is not None
    assert len(article.tables) == 1
    table = article.tables[0]
    assert "Gateway" in table["headers"]
    assert ["Stripe", "2.9%"] in table["rows"]


def test_parse_extracts_images(sample_article_html: str) -> None:
    """Should extract image URL and alt text."""
    article = parse_html_to_article(
        html=sample_article_html,
        url="https://example.com/support/solutions/articles/12345-test",
    )
    assert article is not None
    assert len(article.images) >= 1
    assert article.images[0]["url"] == "https://example.com/screenshot.png"
    assert article.images[0]["alt"] == "Payment settings screen"


def test_parse_generates_content_hash(sample_article_html: str) -> None:
    """Content hash should be a 64-char hex string (SHA-256)."""
    article = parse_html_to_article(
        html=sample_article_html,
        url="https://example.com/support/solutions/articles/12345-test",
    )
    assert article is not None
    assert len(article.content_hash) == 64


def test_parse_returns_none_for_non_article() -> None:
    """Should return None for pages without an article body."""
    html = "<html><body><p>Not an article page</p></body></html>"
    result = parse_html_to_article(html=html, url="https://example.com")
    assert result is None


def test_extract_article_id_from_url() -> None:
    """Should pull the numeric ID from the URL."""
    url = "https://example.com/support/solutions/articles/5000665570-ssl-https-faq"
    assert _extract_article_id(url) == "5000665570"


def test_content_hash_changes_when_content_changes(sample_article_html: str) -> None:
    """Different content should produce different hashes."""
    article1 = parse_html_to_article(
        html=sample_article_html,
        url="https://example.com/support/solutions/articles/12345-test",
    )
    # Modify the HTML
    modified_html = sample_article_html.replace("How to Set Up Payments", "Updated Title")
    article2 = parse_html_to_article(
        html=modified_html,
        url="https://example.com/support/solutions/articles/12345-test",
    )
    assert article1 is not None and article2 is not None
    assert article1.content_hash != article2.content_hash
