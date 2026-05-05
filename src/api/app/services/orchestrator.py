"""Orchestration service - Coordinates retrieval and generation (RAG pattern).

Supports two agent modes (set AGENT_SERVICE env var):
1. "agent_framework" (default) - Agent Framework with FoundryChatClient
2. "foundry" - Azure AI Foundry Agent Service with AI Search tool
"""

import os
import uuid
from app.config import env, env_bool
from app.models import ChatResponse, Citation
from app.services.ai_search import AISearchService
from app.services.openai_service import OpenAIService

MAX_CITATIONS = int(os.getenv("MAX_CITATIONS", "5"))


class OrchestrationService:
    """
    AI Orchestration Layer - Implements the RAG (Retrieval-Augmented Generation) pattern:
    1. Receive user question
    2. Retrieve relevant document chunks from Azure AI Search
    3. Pass context + question to Azure OpenAI for grounded generation
    4. Return answer with citations

    When not in simulated_mode, routes through the Agent Framework orchestrator
    or Foundry Agent Service based on AGENT_SERVICE setting.
    """

    def __init__(self):
        self.simulated_mode = env_bool("SIMULATED_MODE", True)
        self.agent_service = env("AGENT_SERVICE", "agent_framework")
        self.project_endpoint = env("AZURE_AI_PROJECT_ENDPOINT")
        self.openai_deployment = env("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
        self.search_index_name = env("AZURE_SEARCH_INDEX_NAME", "dealer-portal-docs")
        self.search_connection_id = env("AI_SEARCH_PROJECT_CONNECTION_ID")
        self.search_service = AISearchService()
        self.openai_service = OpenAIService()
        self._orchestrator = None
        self._foundry_agent = None

    def _get_agent_orchestrator(self):
        """Lazy-init the Agent Framework orchestrator."""
        if self._orchestrator is None:
            from app.agents.orchestrator import DealerPortalOrchestrator
            self._orchestrator = DealerPortalOrchestrator(
                use_azure=not self.simulated_mode,
            )
        return self._orchestrator

    def _get_foundry_agent(self):
        """Lazy-init the Foundry Agent Service agent."""
        if self._foundry_agent is None:
            from app.agents.dealer_agent_foundry import DealerAgentFoundry
            self._foundry_agent = DealerAgentFoundry(
                project_endpoint=self.project_endpoint,
                model_deployment_name=self.openai_deployment,
                search_index_name=self.search_index_name,
                search_connection_id=self.search_connection_id,
            )
        return self._foundry_agent

    async def process_chat(
        self,
        message: str,
        conversation_id: str,
        history: list[dict] | None = None,
    ) -> ChatResponse:
        """Process a chat message through the full RAG pipeline."""

        # Use Agent Framework / Foundry Agent when not in simulated mode
        if not self.simulated_mode and self.agent_service == "foundry":
            return await self._process_with_foundry_agent(message, conversation_id, history)
        elif not self.simulated_mode and self.agent_service == "agent_framework":
            return await self._process_with_agent_framework(message, conversation_id, history)

        # Default/simulated path: direct search + generation
        # Step 1: Retrieve relevant chunks from AI Search
        search_results = await self.search_service.search(
            query=message,
            top_k=5,
            source_filter=None,
        )

        # Step 2: Prepare context for generation
        context_chunks = [
            {
                "document_name": r.document_name,
                "chunk_text": r.chunk_text,
                "page_number": r.page_number,
                "source_system": r.source_system,
                "relevance_score": r.relevance_score,
            }
            for r in search_results
        ]

        # Step 3: Generate grounded answer
        generation_result = await self.openai_service.generate_answer(
            question=message,
            context_chunks=context_chunks,
            history=history,
        )

        # Step 4: Build citations
        citations = [
            Citation(
                document_name=r.document_name,
                page_number=r.page_number,
                chunk_text=r.chunk_text[:300],
                relevance_score=r.relevance_score,
                source_system=r.source_system,
            )
            for r in search_results[:3]
        ]

        return ChatResponse(
            answer=generation_result["answer"],
            citations=citations,
            conversation_id=conversation_id,
            confidence_score=generation_result.get("confidence", 0.0),
        )

    async def _process_with_agent_framework(
        self,
        message: str,
        conversation_id: str,
        history: list[dict] | None = None,
    ) -> ChatResponse:
        """Process using Agent Framework (FoundryChatClient)."""
        orchestrator = self._get_agent_orchestrator()

        conversation_history = []
        if history:
            conversation_history = [
                {"role": h.get("role", "user"), "content": h.get("content", "")}
                for h in history
            ]

        result = await orchestrator.answer_question_async(
            question=message,
            conversation_history=conversation_history,
        )

        citations = [
            Citation(
                document_name=c.get("document_name", ""),
                page_number=c.get("page_number"),
                chunk_text=c.get("content", "")[:300],
                relevance_score=c.get("score", 0.0),
                source_system="AI Search",
            )
            for c in result.get("citations", [])
        ]

        return ChatResponse(
            answer=result.get("answer", ""),
            citations=citations,
            conversation_id=conversation_id,
            confidence_score=result.get("confidence", 0.0),
        )

    async def _process_with_foundry_agent(
        self,
        message: str,
        conversation_id: str,
        history: list[dict] | None = None,
    ) -> ChatResponse:
        """Process using Foundry Agent Service (fallback)."""
        agent = self._get_foundry_agent()

        context = {}
        if history:
            context["conversation_history"] = history

        result = await agent.answer_question(question=message, context=context)

        # Extract document names from inline citations like 【7:2†Document Name.pdf】
        import re
        answer_text = result.get("answer", "")
        inline_pattern = re.compile(r'【[\d:]+†([^】]+)】')
        inline_docs = list(dict.fromkeys(inline_pattern.findall(answer_text)))  # deduplicate, preserve order

        # Build citations from inline references (preferred — has real doc names)
        citations = []
        if inline_docs:
            for doc_name in inline_docs[:MAX_CITATIONS]:
                citations.append(
                    Citation(
                        document_name=doc_name,
                        page_number=None,
                        chunk_text="",
                        relevance_score=0.0,
                        source_system="Foundry Agent",
                        blob_url=None,
                    )
                )
        else:
            # Fallback to annotation-based citations
            seen_titles = set()
            for c in result.get("citations", []):
                title = c.get("title", "")
                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)
                citations.append(
                    Citation(
                        document_name=title,
                        page_number=None,
                        chunk_text=c.get("text", "")[:300],
                        relevance_score=0.0,
                        source_system="Foundry Agent",
                        blob_url=c.get("url", ""),
                    )
                )
                if len(citations) >= MAX_CITATIONS:
                    break

        return ChatResponse(
            answer=result.get("answer", ""),
            citations=citations,
            conversation_id=conversation_id,
            confidence_score=result.get("confidence", 0.0),
        )
