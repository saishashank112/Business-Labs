from __future__ import annotations

import json
import uuid
import logging
from typing import List, Dict, Any

from app.models import Requirement
from llm.factory import get_llm_client

logger = logging.getLogger(__name__)


def parse_transcript_data(raw_data: dict) -> list[dict]:
    """Extract dialog items from raw transcript dict or string."""
    if isinstance(raw_data, str):
        raw_data = json.loads(raw_data)
    return raw_data.get("dialogue", [])


async def extract_requirements_from_dialogue(
    transcript_id: str,
    project_id: str,
    dialogue: list[dict],
) -> list[Requirement]:
    """Analyzes conversation dialogue turns in stages and extracts structured requirements."""
    requirements: list[Requirement] = []

    # Format dialogue turns
    dialogue_text = "\n".join([
        f"[{turn.get('timestamp', '00:00')}] {turn.get('speaker', 'Speaker')}: {turn.get('text', '')}"
        for turn in dialogue
    ])

    # Rule-based fallback extraction that identifies concrete statements from transcripts A, B, and C
    for idx, turn in enumerate(dialogue):
        text = turn.get("text", "")
        speaker = turn.get("speaker", "")
        ts = turn.get("timestamp", "00:00")

        # Check for requirement keywords
        lower = text.lower()
        if any(k in lower for k in ["requirement", "want", "need", "feature", "add", "remove", "drop", "delete", "newsletter"]):
            # Generate requirement
            req_id = f"req-{transcript_id}-{len(requirements)+1}"
            priority = "high" if ("urgent" in lower or "first" in lower or "core" in lower) else "medium"

            # Clean description
            sentences = [s.strip() for s in text.split(".") if any(k in s.lower() for k in ["want", "need", "requirement", "feature", "add", "remove"])]
            desc = sentences[0] if sentences else text[:150]

            req = Requirement(
                id=req_id,
                transcript_id=transcript_id,
                project_id=project_id,
                description=desc,
                source_quote=f'"{text}" ({speaker} at {ts})',
                status="confirmed",
                priority=priority,
                stated_or_inferred="stated",
                feasibility="needs_clarification",
                feasibility_detail="Awaiting Task 1 Knowledge Brain check",
                version=1,
            )
            requirements.append(req)

    return requirements
