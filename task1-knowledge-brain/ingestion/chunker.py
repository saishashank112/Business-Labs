"""Heading-based chunking with section hierarchy preserved.

Rules from PRD FR-1.4:
  - Heading-based chunking with section hierarchy preserved (H1 > H2 > H3)
  - Target chunk size: 400-800 tokens with 10-20% overlap when natural breaks don't exist
  - Stable chunk IDs: deterministic hash of (article_url + heading_path + chunk_index)
  - Tables kept intact as markdown
  - Lists kept intact
  - Image references retained with surrounding context
"""

from __future__ import annotations

import hashlib
import re
from typing import List

from app.models import ParsedArticle, Chunk


def estimate_tokens(text: str) -> int:
    """Rough estimate of token count (approx 1 token per 0.75 words / 4 chars)."""
    words = len(text.split())
    return max(1, int(words * 1.3))


def generate_chunk_id(url: str, heading_path: list[str], chunk_index: int) -> str:
    """Deterministic, stable chunk ID.
    
    Re-ingesting the exact same article with identical structure yields identical chunk IDs.
    """
    key = f"{url}::/{'/'.join(heading_path)}::{chunk_index}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def split_text_with_overlap(text: str, max_chars: int = 2500, overlap_chars: int = 350) -> list[str]:
    """Split long text by paragraphs with overlap to avoid cutting sentences."""
    if len(text) <= max_chars:
        return [text]

    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current_chunk: list[str] = []
    current_len = 0

    for para in paragraphs:
        para_clean = para.strip()
        if not para_clean:
            continue
        para_len = len(para_clean)

        if current_len + para_len > max_chars and current_chunk:
            combined = "\n\n".join(current_chunk)
            chunks.append(combined)

            # Keep trailing paragraphs for overlap
            overlap_parts: list[str] = []
            overlap_len = 0
            for prev_para in reversed(current_chunk):
                if overlap_len + len(prev_para) <= overlap_chars:
                    overlap_parts.insert(0, prev_para)
                    overlap_len += len(prev_para)
                else:
                    break
            current_chunk = overlap_parts
            current_len = overlap_len

        current_chunk.append(para_clean)
        current_len += para_len + 2

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks or [text]


def chunk_article(article: ParsedArticle) -> list[Chunk]:
    """Chunk a parsed article into semantic chunks preserving hierarchy and metadata."""
    chunks: list[Chunk] = []
    
    # Format tables as markdown if present
    table_texts: list[str] = []
    for t in article.tables:
        headers = t.get("headers", [])
        rows = t.get("rows", [])
        if headers:
            header_line = "| " + " | ".join(headers) + " |"
            sep_line = "| " + " | ".join(["---"] * len(headers)) + " |"
            row_lines = ["| " + " | ".join(row) + " |" for row in rows]
            table_md = "\n".join([header_line, sep_line] + row_lines)
            table_texts.append(table_md)

    # Format lists if present
    list_texts: list[str] = []
    for lst in article.lists:
        list_lines = [f"- {item}" for item in lst]
        list_texts.append("\n".join(list_lines))

    # Collect image URLs
    all_image_urls = [img.get("url", "") for img in article.images if img.get("url")]

    # Split body by headings if headings exist in the text
    # In Brilliant Directories, headings are extracted in article.headings
    sections: list[tuple[str, str]] = []  # (heading, section_text)

    if article.headings:
        # Build regex to split body on headings
        # Escape each heading for regex
        escaped_headings = [re.escape(h) for h in article.headings if h.strip()]
        if escaped_headings:
            pattern = re.compile(r"(?:\n|^)(" + "|".join(escaped_headings) + r")(?:\n|$)", re.IGNORECASE)
            parts = pattern.split(article.body)
            # parts will alternate: [pre-heading-text, heading1, text1, heading2, text2, ...]
            if parts:
                intro = parts[0].strip()
                if intro:
                    sections.append(("Overview", intro))
                i = 1
                while i < len(parts):
                    h_name = parts[i].strip()
                    h_text = parts[i + 1].strip() if i + 1 < len(parts) else ""
                    if h_name or h_text:
                        sections.append((h_name, h_text))
                    i += 2
    
    if not sections:
        # No heading breakdown found, treat entire body as Main section
        sections = [("Overview", article.body.strip())]

    # Now create chunks from sections
    chunk_idx = 0
    for heading, sec_text in sections:
        heading_path = [article.title]
        if heading and heading != "Overview" and heading != article.title:
            heading_path.append(heading)

        # Match relevant image refs
        sec_images: list[str] = []
        for img in article.images:
            img_url = img.get("url", "")
            nearby = img.get("nearby_text", "")
            if img_url and nearby and nearby.lower() in sec_text.lower():
                sec_images.append(img_url)
        if not sec_images and all_image_urls and len(sections) == 1:
            sec_images = all_image_urls[:3]

        # Break section text if long
        text_slices = split_text_with_overlap(sec_text, max_chars=2200, overlap_chars=300)

        for slice_idx, slice_text in enumerate(text_slices):
            # Header prefix for semantic grounding
            prefix = f"# {article.title}\n"
            if heading and heading != "Overview":
                prefix += f"## {heading}\n\n"
            else:
                prefix += "\n"

            content = (prefix + slice_text).strip()

            # Attach tables or lists if this is the overview/first chunk and they haven't been attached
            if chunk_idx == 0 and table_texts:
                content += "\n\n### Tables\n" + "\n\n".join(table_texts)
            if chunk_idx == 0 and list_texts and not article.headings:
                content += "\n\n### Key Lists\n" + "\n\n".join(list_texts)

            c_id = generate_chunk_id(article.url, heading_path, chunk_idx)
            tok_count = estimate_tokens(content)

            chunk = Chunk(
                chunk_id=c_id,
                article_id=article.id,
                url=article.url,
                title=article.title,
                heading=heading,
                heading_path=heading_path,
                content=content,
                image_refs=sec_images,
                chunk_index=chunk_idx,
                token_count=tok_count,
            )
            chunks.append(chunk)
            chunk_idx += 1

    return chunks
