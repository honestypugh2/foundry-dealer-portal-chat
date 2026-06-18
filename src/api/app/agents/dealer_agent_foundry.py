"""Dealer Technical Support Agent - Foundry Agent Service (Fallback)

Uses azure-ai-projects SDK (>=2.0.1) with Azure AI Search tool for
knowledge base retrieval via Foundry Agent Service.

This is the fallback implementation. The default uses Agent Framework
with FoundryChatClient (see dealer_agent.py).

Set AGENT_SERVICE=foundry in .env to use this implementation.
"""

import asyncio
import logging
import os
from typing import Any, Dict, Optional

from app.agents.prompts import DEALER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

try:
    from azure.ai.projects.aio import AIProjectClient
    from azure.ai.projects.models import (
        AzureAISearchTool,
        MCPTool,
        PromptAgentDefinition,
        AzureAISearchToolResource,
        AISearchIndexResource,
        AzureAISearchQueryType,
    )
    from azure.identity.aio import DefaultAzureCredential
    FOUNDRY_AGENT_AVAILABLE = True
except ImportError:
    FOUNDRY_AGENT_AVAILABLE = False
    logger.info("azure-ai-projects agent models not available")


class DealerAgentFoundry:
    """
    AI Agent for answering JAYCO dealer technical questions.
    Uses Azure AI Foundry Agent Service (azure-ai-projects SDK >=2.0.1)
    with Azure AI Search tool for document retrieval.
    """

    def __init__(
        self,
        project_endpoint: str = "",
        model_deployment_name: str = "",
        search_index_name: str = "",
        search_connection_id: Optional[str] = None,
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
        self.search_connection_id = search_connection_id or os.getenv(
            "AI_SEARCH_PROJECT_CONNECTION_ID", ""
        )
        self.search_query_type = search_query_type

        # Agentic retrieval config
        self.agentic_retrieval_enabled = (
            os.getenv("AGENTIC_RETRIEVAL_ENABLED", "false").lower() == "true"
        )
        self.search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT", "")
        self.mcp_connection_name = os.getenv(
            "MCP_PROJECT_CONNECTION_NAME", "dealer-knowledge-mcp-connection"
        )

        # Map query type string to enum
        self.query_type_map = {
            "simple": AzureAISearchQueryType.SIMPLE if FOUNDRY_AGENT_AVAILABLE else None,
            "semantic": AzureAISearchQueryType.SEMANTIC if FOUNDRY_AGENT_AVAILABLE else None,
            "vector": AzureAISearchQueryType.VECTOR if FOUNDRY_AGENT_AVAILABLE else None,
            "hybrid": AzureAISearchQueryType.VECTOR_SEMANTIC_HYBRID if FOUNDRY_AGENT_AVAILABLE else None,
        }

        self.instructions = DEALER_SYSTEM_PROMPT
        self.max_output_tokens = int(os.getenv("MAX_OUTPUT_TOKENS", "4096"))

    def _build_azure_ai_search_tool(self) -> "AzureAISearchTool":
        """Build the Azure AI Search tool for the agent."""
        if not self.search_connection_id:
            logger.warning(
                "AI_SEARCH_PROJECT_CONNECTION_ID not set for Azure AI Search tool. "
                "Configure the connection in your Azure AI Foundry project."
            )

        query_type = self.query_type_map.get(
            self.search_query_type.lower(),
            AzureAISearchQueryType.SEMANTIC,
        )

        return AzureAISearchTool(
            azure_ai_search=AzureAISearchToolResource(
                indexes=[
                    AISearchIndexResource(
                        project_connection_id=self.search_connection_id,
                        index_name=self.search_index_name,
                        query_type=query_type,
                    ),
                ]
            )
        )

    def _build_mcp_tool(self) -> "MCPTool":
        """Build the MCP tool for agentic retrieval."""
        # Build MCP endpoint from search endpoint + knowledge base name
        kb_name = "dealer-knowledge-base"
        api_version = "2025-11-01-Preview"
        mcp_endpoint = (
            f"{self.search_endpoint}/knowledgebases/{kb_name}/mcp"
            f"?api-version={api_version}"
        )

        return MCPTool(
            server_label="knowledge-base",
            server_url=mcp_endpoint,
            require_approval="never",
            allowed_tools=["knowledge_base_retrieve"],
            project_connection_id=self.mcp_connection_name,
        )

    def _get_tools(self) -> list:
        """Get the appropriate tools based on configuration."""
        if self.agentic_retrieval_enabled:
            logger.info("Using MCPTool (agentic retrieval) for knowledge base access")
            return [self._build_mcp_tool()]
        else:
            logger.info("Using AzureAISearchTool for knowledge base access")
            return [self._build_azure_ai_search_tool()]

    async def answer_question(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Answer a dealer technical question using Foundry Agent Service.

        Args:
            question: The technician's question
            context: Additional context (source filter, conversation history, etc.)

        Returns:
            Dictionary with answer, citations, confidence
        """
        if not FOUNDRY_AGENT_AVAILABLE:
            return {
                "answer": "Foundry Agent Service SDK not available.",
                "citations": [],
                "confidence": 0.0,
            }

        if not self.project_endpoint:
            return {
                "answer": "AZURE_AI_PROJECT_ENDPOINT not configured for Foundry Agent Service.",
                "citations": [],
                "confidence": 0.0,
            }

        credential = DefaultAzureCredential()

        async with AIProjectClient(
            endpoint=self.project_endpoint,
            credential=credential,
        ) as project_client, project_client.get_openai_client() as openai_client:

            # Build the appropriate tool (MCPTool or AzureAISearchTool)
            tools = self._get_tools()

            # Create agent with tool
            # NOTE: request an uncompressed response (Accept-Encoding: identity).
            # azure-core 1.40.0 fails to decode a gzip-compressed response body in
            # ContentDecodePolicy (UnicodeDecodeError on byte 0x8b), so we opt out of
            # compression for the agent management calls.
            agent = await project_client.agents.create_version(
                agent_name="DealerTechAgentFoundry",
                definition=PromptAgentDefinition(
                    model=self.model_deployment_name,
                    instructions=self.instructions,
                    tools=tools,
                ),
                description="Dealer technical support agent - answers maintenance and diagnostic questions",
                headers={"Accept-Encoding": "identity"},
            )
            logger.info(f"Agent created (id: {agent.id}, name: {agent.name}, version: {agent.version})")

            try:
                # Build context string
                context_str = ""
                if context:
                    import json
                    context_str = f"\n\nADDITIONAL CONTEXT:\n{json.dumps(context, indent=2, default=str)}"

                # Build prompt
                prompt = (
                    f"Answer the following JAYCO dealer technical question.\n\n"
                    f"QUESTION: {question}{context_str}\n\n"
                    f"Search the knowledge base for relevant technical documentation "
                    f"and provide a detailed answer with citations."
                )

                # Create conversation and get response
                conversation = await openai_client.conversations.create()
                logger.info(f"Created conversation (id: {conversation.id})")

                try:
                    response_text = ""
                    citations = []

                    stream = await openai_client.responses.create(
                        conversation=conversation.id,
                        extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
                        input=prompt,
                        stream=True,
                        tool_choice="required",
                        max_output_tokens=self.max_output_tokens,
                    )

                    async for event in stream:
                        if event.type == "response.output_text.delta":
                            response_text += event.delta
                        elif event.type == "response.output_item.done":
                            if hasattr(event, "item"):
                                item = event.item
                                if hasattr(item, "type") and item.type == "message":
                                    if hasattr(item, "content") and item.content:
                                        for content_item in item.content:
                                            annotations = getattr(content_item, "annotations", None)
                                            if annotations:
                                                for annotation in annotations:
                                                    annotation_type = getattr(annotation, "type", "")
                                                    if annotation_type in ("url_citation", "file_citation"):
                                                        citations.append({
                                                            "url": getattr(annotation, "url", getattr(annotation, "file_id", "")),
                                                            "title": getattr(annotation, "title", getattr(annotation, "filename", "")),
                                                            "text": getattr(annotation, "text", ""),
                                                            "type": annotation_type,
                                                        })

                    logger.info("Successfully completed answer using Foundry Agent Service")

                finally:
                    await openai_client.conversations.delete(conversation_id=conversation.id)
                    logger.info("Conversation deleted")

            finally:
                # Clean up agent (unless persistence is enabled)
                persist_agents = os.getenv("PERSIST_FOUNDRY_AGENTS", "false").lower() == "true"
                if not persist_agents:
                    await project_client.agents.delete_version(
                        agent_name=agent.name,
                        agent_version=agent.version,
                        headers={"Accept-Encoding": "identity"},
                    )
                    logger.info("Agent deleted")
                else:
                    logger.info(f"Agent persisted: {agent.name} (version: {agent.version})")

        return {
            "answer": response_text,
            "citations": citations,
            "confidence": 0.8 if response_text else 0.0,
        }

    async def cleanup(self):
        """Clean up resources."""
        logger.info("DealerAgentFoundry cleaned up")


async def main():
    """Example usage of the Dealer Agent with Foundry."""
    from dotenv import load_dotenv
    load_dotenv()

    logging.basicConfig(level=logging.INFO)

    agent = DealerAgentFoundry(
        project_endpoint=os.getenv("AZURE_AI_PROJECT_ENDPOINT", ""),
        model_deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
        search_index_name=os.getenv("AZURE_SEARCH_INDEX_NAME", "dealer-portal-docs"),
        search_connection_id=os.getenv("AI_SEARCH_PROJECT_CONNECTION_ID"),
        search_query_type=os.getenv("AI_SEARCH_QUERY_TYPE", "semantic"),
    )

    sample_question = "What is the bearing repack procedure for a JAYCO trailer hub?"

    print("Answering question using Foundry Agent Service...\n")
    result = await agent.answer_question(sample_question)
    print(f"Answer:\n{result['answer'][:1000]}")
    print(f"\nCitations: {len(result['citations'])}")
    print(f"Confidence: {result['confidence']}")

    await agent.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
