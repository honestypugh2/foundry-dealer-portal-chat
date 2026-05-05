"""Chat router - RAG-based conversational endpoint."""

import uuid
from fastapi import APIRouter, Depends

from app.models import ChatRequest, ChatResponse
from app.services.orchestrator import OrchestrationService

router = APIRouter()


def get_orchestrator() -> OrchestrationService:
    return OrchestrationService()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    orchestrator: OrchestrationService = Depends(get_orchestrator),
):
    """
    Process a dealer question using RAG pattern:
    1. Retrieve relevant document chunks from Azure AI Search
    2. Generate grounded answer using Azure OpenAI GPT-4o
    3. Return answer with citations
    """
    conversation_id = request.conversation_id or str(uuid.uuid4())

    response = await orchestrator.process_chat(
        message=request.message,
        conversation_id=conversation_id,
        history=request.history,
    )

    return response
