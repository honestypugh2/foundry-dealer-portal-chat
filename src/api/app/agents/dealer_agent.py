"""Dealer Technical Support Agent - Agent Framework with FoundryChatClient (Default)

Uses Agent Framework's Agent class with FoundryChatClient and @tool-decorated
methods for Azure AI Search retrieval + RAG-based answer generation.

Set AGENT_SERVICE=foundry in .env to use the Foundry Agent Service fallback instead.

Reference: https://github.com/honestypugh2/foundry-grant-eo-validation-demo/blob/main/src/agents/compliance_agent.py
"""

import json
import logging
import os
from typing import Annotated, Any, Dict, List, Optional

from app.agents.prompts import DEALER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

try:
    from agent_framework import Agent, tool
    from agent_framework.foundry import FoundryChatClient
    AGENT_FRAMEWORK_AVAILABLE = True
except ImportError:
    AGENT_FRAMEWORK_AVAILABLE = False
    logger.warning("agent-framework not installed")

try:
    from azure.identity import AzureCliCredential
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient
    from azure.search.documents.models import VectorizableTextQuery
    SEARCH_SDK_AVAILABLE = True
except ImportError:
    SEARCH_SDK_AVAILABLE = False
    logger.warning("azure-search-documents not installed")


SYSTEM_PROMPT = DEALER_SYSTEM_PROMPT


class DealerTechAgent:
    """
    AI Agent for answering JAYCO dealer technical questions.
    Uses Agent Framework's Agent class with FoundryChatClient and
    @tool-decorated search method for Azure AI Search grounding.
    """

    def __init__(
        self,
        project_endpoint: str = "",
        model_deployment_name: str = "",
        search_index_name: str = "",
        search_endpoint: Optional[str] = None,
        search_api_key: Optional[str] = None,
        search_query_type: str = "semantic",
    ):
        self.project_endpoint = project_endpoint or os.getenv(
            "AZURE_AI_PROJECT_ENDPOINT",
            os.getenv("AZURE_AI_FOUNDRY_PROJECT_ENDPOINT", ""),
        )
        self.model_deployment_name = model_deployment_name or os.getenv(
            "AZURE_OPENAI_DEPLOYMENT", "gpt-4o"
        )
        self.search_index_name = search_index_name or os.getenv(
            "AZURE_SEARCH_INDEX_NAME", "dealer-portal-docs"
        )
        self.search_endpoint = search_endpoint or os.getenv("AZURE_SEARCH_ENDPOINT", "")
        self.search_api_key = search_api_key or os.getenv("AZURE_SEARCH_API_KEY")
        self.search_query_type = search_query_type
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the agent (idempotent)."""
        self._initialized = True

    async def close(self) -> None:
        """Release resources."""
        self._initialized = False

    # ------------------------------------------------------------------
    # Tool: Azure AI Search for dealer technical documents
    # ------------------------------------------------------------------
    @tool(
        name="search_technical_documents",
        description="Search the JAYCO dealer technical documentation knowledge base "
                    "for maintenance procedures, torque specifications, diagnostic steps, "
                    "and safety bulletins relevant to the technician's query.",
    )
    def search_technical_documents(
        self,
        query: Annotated[str, "Search query describing the technical topic, part, or procedure to find"],
    ) -> str:
        """Search the JAYCO technical documentation using Azure AI Search."""
        if not self.search_endpoint:
            return "Error: Azure AI Search endpoint not configured. Set AZURE_SEARCH_ENDPOINT."

        if not SEARCH_SDK_AVAILABLE:
            return "Error: azure-search-documents SDK not installed."

        if self.search_api_key:
            credential = AzureKeyCredential(self.search_api_key)
        else:
            credential = AzureCliCredential()

        client = SearchClient(
            endpoint=self.search_endpoint,
            index_name=self.search_index_name,
            credential=credential,
        )

        results = client.search(
            search_text=query,
            query_type=self.search_query_type,
            semantic_configuration_name="dealer-semantic-config",
            top=5,
            vector_queries=[
                VectorizableTextQuery(
                    text=query,
                    k_nearest_neighbors=5,
                    fields="content_vector",
                )
            ],
        )

        output_parts = []
        for i, result in enumerate(results, 1):
            doc_name = result.get("document_name", result.get("metadata_storage_name", "Unknown"))
            content = result.get("content", result.get("chunk", ""))
            page_number = result.get("page_number", "N/A")
            source_system = result.get("source_system", "")
            score = result.get("@search.score", 0)
            reranker_score = result.get("@search.reranker_score", "")

            score_info = f"score: {score:.2f}"
            if reranker_score:
                score_info += f", reranker: {reranker_score:.2f}"

            output_parts.append(
                f"[Result {i}] ({score_info})\n"
                f"Document: {doc_name}\n"
                f"Page: {page_number}\n"
                f"Source: {source_system}\n"
                f"{content}\n"
            )

        if not output_parts:
            return f"No results found for query: {query}"

        return "\n---\n".join(output_parts)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    async def answer_question_async(
        self,
        question: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a grounded answer using Agent Framework with FoundryChatClient.

        The agent autonomously searches Azure AI Search via its @tool method.

        Args:
            question: The technician's question
            conversation_history: Previous conversation messages

        Returns:
            Dict with answer, citations, confidence
        """
        if not self.project_endpoint or not AGENT_FRAMEWORK_AVAILABLE:
            return self._build_answer_from_results(question, [])

        try:
            return await self._generate_with_agent_framework(question, conversation_history)
        except Exception as e:
            logger.error(f"Agent Framework failed: {e}. Returning error response.")
            return {
                "answer": (
                    "I encountered an error while searching the documentation. "
                    "Please try again or consult JAYCO technical support."
                ),
                "citations": [],
                "confidence": 0.0,
            }

    async def _generate_with_agent_framework(
        self,
        question: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Generate answer using Agent Framework Agent + FoundryChatClient."""
        client = FoundryChatClient(
            project_endpoint=self.project_endpoint,
            model=self.model_deployment_name,
            credential=AzureCliCredential(),
        )

        # Build tools list: Azure AI Search function tool
        tools = [
            self.search_technical_documents,
        ]

        agent = Agent(
            client=client,
            name="DealerTechAgent",
            instructions=SYSTEM_PROMPT,
            tools=tools,
        )

        # Build prompt with conversation context
        prompt = f"Answer the following JAYCO dealer technical question:\n\n{question}"

        if conversation_history:
            history_text = "\n".join(
                f"{msg.get('role', 'user')}: {msg.get('content', '')}"
                for msg in conversation_history[-6:]
            )
            prompt += f"\n\nPREVIOUS CONVERSATION:\n{history_text}"

        prompt += (
            "\n\nPlease perform the following steps:\n"
            "1. Use the search_technical_documents tool to find relevant technical documents\n"
            "2. Analyze the retrieved documents for relevant procedures, specifications, and safety info\n"
            "3. Provide a clear, grounded answer with document citations and page numbers"
        )

        # Get response from agent via streaming
        response_text = ""
        async for chunk in agent.run(prompt, stream=True):
            if chunk.text:
                response_text += chunk.text

        # Build citations from the response (agent's tool calls would have fetched them)
        citations = self._extract_citations_from_text(response_text)

        return {
            "answer": response_text,
            "citations": citations,
            "confidence": 0.85 if response_text else 0.3,
        }

    # ------------------------------------------------------------------
    # Citation extraction helpers
    # ------------------------------------------------------------------
    def _extract_citations_from_text(self, text: str) -> List[Dict[str, Any]]:
        """Extract document citations mentioned in the agent's response."""
        import re

        citations = []
        seen = set()

        # Match patterns like "Document: XYZ.pdf" or references to specific docs
        doc_patterns = [
            r'(?:Document|Source|From)[:\s]+([^,\n]+\.pdf)',
            r'\*([^*]+\.pdf)\*',
            r'(?:from|in|see)\s+(?:the\s+)?["\']?([^"\',.]+\.pdf)["\']?',
        ]

        for pattern in doc_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                doc_name = match.group(1).strip()
                if doc_name not in seen:
                    seen.add(doc_name)
                    # Try to find page number near this mention
                    page_match = re.search(
                        rf'{re.escape(doc_name)}[^.]*?(?:page|p\.?)\s*(\d+)',
                        text, re.IGNORECASE
                    )
                    page_num = int(page_match.group(1)) if page_match else None

                    citations.append({
                        "document_name": doc_name,
                        "page_number": page_num,
                        "content": "",
                        "score": 0.0,
                    })

        return citations

    # ------------------------------------------------------------------
    # Fallback: build answer from pre-retrieved results
    # ------------------------------------------------------------------
    def _build_answer_from_results(
        self,
        question: str,
        search_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Build answer directly from search results (no agent/LLM)."""
        if not search_results:
            return {
                "answer": (
                    "I don't have enough information in the available documentation "
                    "to answer that question. Please consult the JAYCO technical support team."
                ),
                "citations": [],
                "confidence": 0.0,
            }

        answer_parts = ["Based on the JAYCO technical documentation:\n"]
        citations = []

        for i, result in enumerate(search_results[:3], 1):
            doc_name = result.get("document_name", "Unknown")
            page_num = result.get("page_number", "N/A")
            content = result.get("content", "")[:500]
            answer_parts.append(f"**{i}. {doc_name}** (Page {page_num})")
            answer_parts.append(f"{content}\n")
            citations.append({
                "document_name": doc_name,
                "page_number": page_num,
                "content": content,
                "score": result.get("reranker_score") or result.get("score", 0),
            })

        answer_parts.append(
            f"\n*Sources: {', '.join(set(r.get('document_name', '') for r in search_results[:3]))}*"
        )

        return {
            "answer": "\n".join(answer_parts),
            "citations": citations,
            "confidence": 0.7,
        }


async def main():
    """Example usage of the Dealer Tech Agent."""
    from dotenv import load_dotenv
    load_dotenv()

    logging.basicConfig(level=logging.INFO)

    agent = DealerTechAgent(
        project_endpoint=os.getenv("AZURE_AI_FOUNDRY_PROJECT_ENDPOINT")
            or os.getenv("AZURE_AI_PROJECT_ENDPOINT") or "",
        model_deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT") or "gpt-4o",
        search_index_name=os.getenv("AZURE_SEARCH_INDEX_NAME") or "dealer-portal-docs",
        search_endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
        search_api_key=os.getenv("AZURE_SEARCH_API_KEY"),
        search_query_type=os.getenv("AI_SEARCH_QUERY_TYPE", "semantic"),
    )

    await agent.initialize()

    sample_question = "What is the bearing repack procedure for a JAYCO trailer hub?"

    print("Answering question using Agent Framework + FoundryChatClient...\n")
    result = await agent.answer_question_async(sample_question)
    print(f"Answer:\n{result['answer'][:1000]}")
    print(f"\nCitations: {len(result['citations'])}")
    print(f"Confidence: {result['confidence']}")

    await agent.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
