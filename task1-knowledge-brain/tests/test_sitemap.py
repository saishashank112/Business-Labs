"""Tests for sitemap parser."""

from ingestion.sitemap import parse_sitemap_xml


def test_parse_extracts_article_urls(sample_sitemap_xml: str) -> None:
    """Should find exactly 3 article URLs, skipping the folder."""
    entries = parse_sitemap_xml(sample_sitemap_xml)
    assert len(entries) == 3
    # All entries should be article URLs
    for entry in entries:
        assert "/articles/" in entry.url


def test_parse_extracts_lastmod(sample_sitemap_xml: str) -> None:
    """Each entry should have a lastmod date."""
    entries = parse_sitemap_xml(sample_sitemap_xml)
    for entry in entries:
        assert entry.lastmod is not None
        assert "2026" in entry.lastmod


def test_parse_deduplicates() -> None:
    """Duplicate URLs should be removed."""
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.com/support/solutions/articles/123-test</loc></url>
      <url><loc>https://example.com/support/solutions/articles/123-test</loc></url>
    </urlset>"""
    entries = parse_sitemap_xml(xml)
    assert len(entries) == 1


def test_parse_skips_non_articles() -> None:
    """Folder and category URLs should be filtered out."""
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.com/support/home</loc></url>
      <url><loc>https://example.com/support/solutions</loc></url>
      <url><loc>https://example.com/support/solutions/folders/12345</loc></url>
    </urlset>"""
    entries = parse_sitemap_xml(xml)
    assert len(entries) == 0


def test_parse_handles_empty_sitemap() -> None:
    """An empty sitemap should return an empty list, not crash."""
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    </urlset>"""
    entries = parse_sitemap_xml(xml)
    assert entries == []
