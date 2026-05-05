"""Pydantic models for request/response schemas."""

from pydantic import BaseModel, Field
from typing import Optional


class ChatRequest(BaseModel):
    """Chat request from the dealer portal."""

    message: str = Field(..., min_length=1, max_length=2000, description="User question")
    conversation_id: Optional[str] = Field(None, description="Conversation thread ID")
    history: list[dict] = Field(default_factory=list, description="Previous messages")


class Citation(BaseModel):
    """A citation reference from a source document."""

    document_name: str
    page_number: Optional[int] = None
    chunk_text: str
    relevance_score: float
    source_system: str = "AI Search"  # SharePoint, Revver, or AI Search
    blob_url: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat response with grounded answer and citations."""

    answer: str
    citations: list[Citation] = []
    conversation_id: str
    confidence_score: float = 0.0


class SearchRequest(BaseModel):
    """Search request for document retrieval."""

    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)
    source_filter: Optional[str] = Field(None, description="Filter by source: sharepoint, revver, all")


class SearchResult(BaseModel):
    """Individual search result."""

    document_name: str
    chunk_text: str
    page_number: Optional[int] = None
    relevance_score: float
    reranker_score: Optional[float] = None
    source_system: str
    metadata: dict = {}


class SearchResponse(BaseModel):
    """Search response with results."""

    results: list[SearchResult]
    total_count: int
    query: str


class DocumentInfo(BaseModel):
    """Document metadata."""

    name: str
    source_system: str
    size_bytes: Optional[int] = None
    page_count: Optional[int] = None
    last_modified: Optional[str] = None
    tags: list[str] = []


class DocumentListResponse(BaseModel):
    """List of available documents."""

    documents: list[DocumentInfo]
    total_count: int
