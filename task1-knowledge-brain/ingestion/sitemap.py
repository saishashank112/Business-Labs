"""Sitemap parser — downloads the XML sitemap and extracts URLs.

The Brilliant Directories sitemap is a standard <urlset> with:
  <url>
    <loc>https://...articles/5000665570-ssl-https-faq</loc>
    <lastmod>2026-09-22T23:13:12+05:30</lastmod>
  </url>

We only want article URLs (contain "/articles/").
Folder and category pages are skipped.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import httpx

from app.models import SitemapEntry

# XML namespace used in standard sitemaps
_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


async def fetch_sitemap(sitemap_url: str) -> list[SitemapEntry]:
    """Download the sitemap XML and return a list of article entries.

    Args:
        sitemap_url: Full URL to the sitemap.xml file.

    Returns:
        List of SitemapEntry (url + lastmod) for article pages only.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(sitemap_url)
        response.raise_for_status()

    return parse_sitemap_xml(response.text)


def parse_sitemap_xml(xml_text: str) -> list[SitemapEntry]:
    """Parse raw sitemap XML into SitemapEntry objects.

    Filters to only include article URLs (contain '/articles/').
    Deduplicates by URL.
    """
    root = ET.fromstring(xml_text)
    seen: set[str] = set()
    entries: list[SitemapEntry] = []

    for url_elem in root.findall("sm:url", _NS):
        loc_elem = url_elem.find("sm:loc", _NS)
        if loc_elem is None or loc_elem.text is None:
            continue

        url = loc_elem.text.strip()

        # Only keep article pages, skip folders and category pages
        if "/articles/" not in url:
            continue

        # Deduplicate
        if url in seen:
            continue
        seen.add(url)

        # Extract lastmod if available
        lastmod_elem = url_elem.find("sm:lastmod", _NS)
        lastmod = lastmod_elem.text.strip() if lastmod_elem is not None and lastmod_elem.text else None

        entries.append(SitemapEntry(url=url, lastmod=lastmod))

    return entries
