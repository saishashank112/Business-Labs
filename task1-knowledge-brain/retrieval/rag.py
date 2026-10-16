"""RAG Answerer — evidence-only answering, citations, injection defense, and escalation."""

from __future__ import annotations

import os
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.database import get_db
from app.models import QueryResponse, Source, ImageRef
from retrieval.search import hybrid_search
from llm.factory import get_llm_client

logger = logging.getLogger(__name__)

# Cache loaded prompt
_PROMPT_TEMPLATE: Optional[str] = None


def load_rag_prompt() -> str:
    """Read prompt markdown file from disk."""
    global _PROMPT_TEMPLATE
    if _PROMPT_TEMPLATE is not None:
        return _PROMPT_TEMPLATE

    prompt_path = Path(__file__).parent.parent / "prompts" / "rag_answer_v1.md"
    if prompt_path.exists():
        _PROMPT_TEMPLATE = prompt_path.read_text(encoding="utf-8")
    else:
        _PROMPT_TEMPLATE = (
            "You are an expert technical consultant for Brilliant Directories. "
            "Answer the question using only the provided context. Cite sources with markdown links."
        )
    return _PROMPT_TEMPLATE


async def create_escalation(
    question: str,
    evidence: str,
    reason: str,
    request_id: Optional[str] = None,
) -> str:
    """Create a new escalation row in the database when evidence is insufficient."""
    escalation_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO escalations
               (id, question, evidence, reason, status, created_at, request_id)
               VALUES (?, ?, ?, ?, 'open', ?, ?)""",
            (escalation_id, question, evidence, reason, now, request_id),
        )
        await db.commit()
        logger.info("Created escalation %s for question: %s", escalation_id, question[:50])
        return escalation_id
    finally:
        await db.close()


async def answer_query(
    question: str,
    context_extra: Optional[str] = None,
    mode: str = "hybrid",
    request_id: Optional[str] = None,
) -> QueryResponse:
    """Answer a user query with hybrid retrieval, RAG, citations, and fallback escalation."""
    req_id = request_id or str(uuid.uuid4())

    # 1. Retrieve evidence chunks
    retrieved_chunks = await hybrid_search(query=question, mode=mode, top_k=5)

    # 2. Check if we found any evidence
    if not retrieved_chunks:
        reason = "No relevant documentation articles were found for this query."
        esc_id = await create_escalation(
            question=question,
            evidence="No matching chunks retrieved.",
            reason=reason,
            request_id=req_id,
        )
        return QueryResponse(
            answer=(
                "I could not find sufficient information in the Brilliant Directories documentation "
                "to answer your question accurately. This has been escalated to a human expert."
            ),
            status="insufficient_evidence",
            sources=[],
            images=[],
            needs_human=True,
            escalation_id=esc_id,
            request_id=req_id,
        )

    # 3. Format context from chunks
    context_blocks: list[str] = []
    sources_dict: dict[str, Source] = {}
    images_list: list[ImageRef] = []
    seen_images: set[str] = set()

    for idx, c in enumerate(retrieved_chunks, start=1):
        c_title = c.get("title", "Article")
        c_url = c.get("url", "")
        c_content = c.get("content", "")
        c_score = c.get("score", 0.0)

        context_blocks.append(
            f"--- [Document {idx}] ---\n"
            f"Title: {c_title}\n"
            f"URL: {c_url}\n\n"
            f"{c_content}\n"
        )

        if c_url and c_url not in sources_dict:
            sources_dict[c_url] = Source(title=c_title, url=c_url, relevance=c_score)

        # Collect image references
        for img_url in c.get("image_refs", []):
            if img_url and img_url not in seen_images:
                seen_images.add(img_url)
                images_list.append(
                    ImageRef(
                        url=img_url,
                        description=f"Screenshot from {c_title}",
                        article_url=c_url,
                    )
                )

    combined_context = "\n".join(context_blocks)
    if context_extra:
        combined_context = f"ADDITIONAL CONTEXT:\n{context_extra}\n\n" + combined_context

    system_instruction = load_rag_prompt()

    user_prompt = (
        f"DOCUMENTATION CONTEXT:\n{combined_context}\n\n"
        f"USER QUESTION:\n{question}\n\n"
        f"Please provide an accurate, evidence-based answer with inline markdown citations."
    )

    # 4. Generate answer with LLM
    llm = get_llm_client(step="rag_answer")
    try:
        response = await llm.generate(
            prompt=user_prompt,
            system_prompt=system_instruction,
            request_id=req_id,
            step="rag_answer",
        )
        answer_text = response.text.strip()
    except Exception as e:
        logger.error("LLM answering failed: %s", e)
        answer_text = (
            "An error occurred while generating the answer. Retrieved documentation sources "
            "are provided below for your reference."
        )

    # Check for keywords indicating insufficient evidence in answer
    lower_ans = answer_text.lower()
    insufficient = any(phrase in lower_ans for phrase in [
        "not mentioned in the context",
        "context does not contain",
        "insufficient information",
        "cannot confirm from the documentation",
        "not specified in the provided documents",
    ])

    esc_id = None
    if insufficient:
        esc_id = await create_escalation(
            question=question,
            evidence=combined_context[:1000],
            reason="Documentation context did not contain enough details to fully answer the question.",
            request_id=req_id,
        )

    return QueryResponse(
        answer=answer_text,
        status="insufficient_evidence" if insufficient else "answered",
        sources=list(sources_dict.values()),
        images=images_list[:3],
        needs_human=insufficient,
        escalation_id=esc_id,
        request_id=req_id,
    )
