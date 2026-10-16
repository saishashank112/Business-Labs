"""HTML parser — converts a raw help-center page into clean article JSON.

The Brilliant Directories articles have this structure:
  <article class="article-body" id="article-body">
    <h1 class="post-title heading">Title</h1>
    <h2>Section heading</h2>
    <p>Body text...</p>
    <ul><li>List items</li></ul>
    <table>...</table>
    <img src="..." alt="...">
  </article>

We strip navigation, banners, footer, scripts, and styles.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup, Tag

from app.models import ParsedArticle


def parse_html_to_article(
    html: str,
    url: str,
    lastmod: str | None = None,
) -> ParsedArticle | None:
    """Parse one HTML page into a structured ParsedArticle.

    Args:
        html:    Raw HTML string.
        url:     The URL this page was fetched from.
        lastmod: Last-modified date from the sitemap.

    Returns:
        A ParsedArticle, or None if no article content was found.
    """
    soup = BeautifulSoup(html, "lxml")

    # Find the main article body
    article_el = soup.find("article", class_="article-body")
    if article_el is None:
        return None

    # ── Extract article ID from the URL ─────────────────────
    # URL pattern: /articles/5000665570-ssl-https-faq
    article_id = _extract_article_id(url)

    # ── Title ───────────────────────────────────────────────
    title_el = article_el.find("h1")
    title = title_el.get_text(strip=True) if title_el else "Untitled"

    # ── Headings ────────────────────────────────────────────
    headings: list[str] = []
    for h in article_el.find_all(["h2", "h3", "h4", "h5", "h6"]):
        text = h.get_text(strip=True)
        if text:
            headings.append(text)

    # ── Body text ───────────────────────────────────────────
    # Get all text from paragraphs, excluding script/style
    for tag in article_el.find_all(["script", "style"]):
        tag.decompose()

    body_parts: list[str] = []
    for p in article_el.find_all(["p", "div", "span"]):
        text = p.get_text(strip=True)
        if text and len(text) > 5:  # skip tiny fragments
            body_parts.append(text)

    body = "\n".join(body_parts)

    # ── Lists ───────────────────────────────────────────────
    lists: list[list[str]] = []
    for ul in article_el.find_all(["ul", "ol"]):
        items = [li.get_text(strip=True) for li in ul.find_all("li") if li.get_text(strip=True)]
        if items:
            lists.append(items)

    # ── Tables ──────────────────────────────────────────────
    tables: list[dict] = []
    for table in article_el.find_all("table"):
        table_data = _parse_table(table)
        if table_data:
            tables.append(table_data)

    # ── Images ──────────────────────────────────────────────
    images: list[dict] = []
    for img in article_el.find_all("img"):
        src = img.get("src", "")
        if not src or "spacer.gif" in src:
            continue  # skip spacer images

        alt = img.get("alt", "")
        nearby_text = _get_nearby_text(img)
        images.append({
            "url": src,
            "alt": alt,
            "nearby_text": nearby_text,
        })

    # ── Content hash ────────────────────────────────────────
    # Hash the cleaned text so we can detect changes on re-crawl
    clean_text = title + "\n" + body
    content_hash = hashlib.sha256(clean_text.encode()).hexdigest()

    return ParsedArticle(
        id=article_id,
        url=url,
        title=title,
        headings=headings,
        body=body,
        lists=lists,
        tables=tables,
        images=images,
        lastmod=lastmod,
        content_hash=content_hash,
        ingested_at=datetime.now(timezone.utc).isoformat(),
    )


# ── Helper functions ────────────────────────────────────────

def _extract_article_id(url: str) -> str:
    """Pull the numeric article ID from a URL like .../articles/5000665570-slug."""
    match = re.search(r"/articles/(\d+)", url)
    if match:
        return match.group(1)
    # Fallback: hash the URL
    return hashlib.md5(url.encode()).hexdigest()[:12]


def _parse_table(table: Tag) -> dict | None:
    """Convert an HTML <table> to {headers: [...], rows: [[...]]}."""
    headers: list[str] = []
    rows: list[list[str]] = []

    # Try to find header row
    thead = table.find("thead")
    if thead:
        headers = [th.get_text(strip=True) for th in thead.find_all(["th", "td"])]

    # Body rows
    for tr in table.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if cells:
            # First row might be headers if no <thead>
            if not headers and tr.find("th"):
                headers = cells
            else:
                rows.append(cells)

    if not rows and not headers:
        return None
    return {"headers": headers, "rows": rows}


def _get_nearby_text(img: Tag) -> str:
    """Get text from the nearest sibling or parent paragraph.

    This gives context about what the screenshot is showing.
    """
    # Try previous sibling
    prev = img.find_previous_sibling(["p", "span", "div"])
    if prev:
        text = prev.get_text(strip=True)
        if text and len(text) > 10:
            return text[:200]

    # Try parent
    parent = img.find_parent(["p", "div", "li"])
    if parent:
        text = parent.get_text(strip=True)
        if text and len(text) > 10:
            return text[:200]

    return ""
