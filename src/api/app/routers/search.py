"""Search router - Document search endpoint."""

from fastapi import APIRouter, Depends

from app.models import SearchRequest, SearchResponse
from app.services.ai_search import AISearchService

router = APIRouter()


def get_search_service() -> AISearchService:
    return AISearchService()


@router.post("/search", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest,
    search_service: AISearchService = Depends(get_search_service),
):
    """
    Search indexed documents using Azure AI Search (hybrid retrieval).
    Supports keyword + semantic/vector search.
    """
    results = await search_service.search(
        query=request.query,
        top_k=request.top_k,
        source_filter=request.source_filter,
    )

    return SearchResponse(
        results=results,
        total_count=len(results),
        query=request.query,
    )
