"""POST /query — Knowledge Brain query endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.dependencies import verify_api_key
from app.models import QueryRequest, QueryResponse
from retrieval.rag import answer_query

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def query_knowledge_base(
    request: QueryRequest,
    raw_request: Request,
    _: str = Depends(verify_api_key),
) -> QueryResponse:
    """Query the Brilliant Directories knowledge base using hybrid retrieval and RAG.
    
    Headers:
        X-API-Key: required authentication key
        X-Request-Id: optional tracking UUID
        
    Body:
        question: user's query string
        context: optional additional context
        mode: vector | keyword | hybrid (default)
        
    Returns:
        QueryResponse with answer, inline citations, image links, and escalation status.
    """
    request_id = getattr(raw_request.state, "request_id", None)
    response = await answer_query(
        question=request.question,
        context_extra=request.context,
        mode=request.mode,
        request_id=request_id,
    )
    return response
