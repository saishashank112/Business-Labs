"""Vision model integration for describing screenshots and UI images.

Extracts UI elements, controls, and navigation steps from images.
Caches descriptions in SQLite by image SHA-256 hash.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

import httpx

from app.database import get_db
from app.config import settings
from llm.factory import get_llm_client

logger = logging.getLogger(__name__)

_IMAGE_PROMPT_TEMPLATE: Optional[str] = None


def load_image_prompt() -> str:
    """Read image description prompt from disk."""
    global _IMAGE_PROMPT_TEMPLATE
    if _IMAGE_PROMPT_TEMPLATE is not None:
        return _IMAGE_PROMPT_TEMPLATE

    prompt_path = Path(__file__).parent.parent / "prompts" / "image_describe_v1.md"
    if prompt_path.exists():
        _IMAGE_PROMPT_TEMPLATE = prompt_path.read_text(encoding="utf-8")
    else:
        _IMAGE_PROMPT_TEMPLATE = (
            "Analyze this screenshot from Brilliant Directories. Describe the settings, "
            "navigation paths, visible buttons, and note any uncertainty."
        )
    return _IMAGE_PROMPT_TEMPLATE


def compute_image_hash(image_bytes: bytes) -> str:
    """Deterministic SHA-256 of image binary content."""
    return hashlib.sha256(image_bytes).hexdigest()


async def get_cached_description(image_hash: str) -> Optional[dict[str, Any]]:
    """Look up previously cached image description."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT image_hash, image_url, article_id, description, uncertainty, model_used, created_at
               FROM image_descriptions WHERE image_hash = ?""",
            (image_hash,),
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return None
    finally:
        await db.close()


async def save_image_description(
    image_hash: str,
    image_url: str,
    article_id: str,
    description: str,
    uncertainty: Optional[str],
    model_used: str,
) -> None:
    """Cache description into SQLite image_descriptions table."""
    now = datetime.now(timezone.utc).isoformat()
    db = await get_db()
    try:
        await db.execute(
            """INSERT OR REPLACE INTO image_descriptions
               (image_hash, image_url, article_id, description, uncertainty, model_used, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (image_hash, image_url, article_id, description, uncertainty, model_used, now),
        )
        await db.commit()
    finally:
        await db.close()


async def process_and_describe_image(
    image_url: str,
    article_id: str,
    request_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Download image, check cache, run vision model if new, and cache description."""
    # 1. Download image
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(image_url)
            if resp.status_code != 200:
                logger.warning("Failed to fetch image %s: HTTP %d", image_url, resp.status_code)
                return None
            image_bytes = resp.content
            mime_type = resp.headers.get("content-type", "image/png").split(";")[0]
    except Exception as e:
        logger.warning("Error downloading image %s: %s", image_url, e)
        return None

    # 2. Compute hash and check cache
    img_hash = compute_image_hash(image_bytes)
    cached = await get_cached_description(img_hash)
    if cached:
        logger.debug("Cache hit for image %s (%s)", image_url, img_hash[:8])
        return cached

    # 3. Call vision model via LLM interface
    llm = get_llm_client(step="image_describe")
    prompt = load_image_prompt()

    try:
        llm_resp = await llm.generate_vision(
            prompt=prompt,
            image_bytes=image_bytes,
            mime_type=mime_type,
            request_id=request_id,
            step="image_describe",
        )
        description_text = llm_resp.text.strip()
        model_name = llm_resp.model

        # Extract uncertainty line if present
        uncertainty = None
        for line in description_text.splitlines():
            if "uncertainty:" in line.lower():
                uncertainty = line.split(":", 1)[1].strip()
                break

        # 4. Save to cache
        await save_image_description(
            image_hash=img_hash,
            image_url=image_url,
            article_id=article_id,
            description=description_text,
            uncertainty=uncertainty,
            model_used=model_name,
        )

        return {
            "image_hash": img_hash,
            "image_url": image_url,
            "article_id": article_id,
            "description": description_text,
            "uncertainty": uncertainty,
            "model_used": model_name,
        }
    except Exception as e:
        logger.error("Vision model description failed for %s: %s", image_url, e)
        return None
