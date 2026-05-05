"""Dealer Portal Agent Orchestrator

Delegates to DealerTechAgent which uses Agent Framework's Agent class
with FoundryChatClient and @tool-decorated search for autonomous retrieval.

The agent decides when and how to search Azure AI Search — no pre-retrieval step.

Reference: https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/orchestrations/sequential
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class DealerPortalOrchestrator:
    """
    Orchestrator for JAYCO Dealer Technical Support.

    Delegates to DealerTechAgent which autonomously searches Azure AI Search
    via @tool-decorated methods. The agent decides search queries based on
    the user's question — no hardcoded pre-retrieval step.

    ┌─────────────────────────────────────────────────┐
    │  DealerTechAgent (FoundryChatClient)            │
    │    ├── Receives user question                   │
    │    ├── Autonomously calls @tool search          │
    │    │   └── Azure AI Search (hybrid + semantic)  │
    │    └── Generates grounded answer + citations    │
    └─────────────────────────────────────────────────┘
    """

    def __init__(self, use_azure: bool = True):
        self.use_azure = use_azure
        self.project_endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT") or os.getenv(
            "AZURE_AI_FOUNDRY_PROJECT_ENDPOINT", ""
        )
        self._agent = None

    @property
    def agent(self):
        """Lazy-init the DealerTechAgent."""
        if self._agent is None:
            from app.agents.dealer_agent import DealerTechAgent
            self._agent = DealerTechAgent(
                project_endpoint=self.project_endpoint if self.use_azure else "",
            )
        return self._agent

    async def answer_question_async(
        self,
        question: str,
        conversation_history: Optional[list[dict[str, str]]] = None,
        source_filter: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Process a dealer technical question by delegating to DealerTechAgent.

        The agent autonomously searches Azure AI Search via its @tool method
        and generates a grounded answer with citations.

        Args:
            question: The technician's question
            conversation_history: Optional previous messages
            source_filter: Optional filter by source system (unused — agent decides queries)

        Returns:
            Dict with answer, citations, confidence, processing_time_ms
        """
        start_time = time.time()

        try:
            result = await self.agent.answer_question_async(
                question=question,
                conversation_history=conversation_history,
            )
        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            result = {
                "answer": (
                    "I don't have enough information in the available documentation. "
                    "Please consult JAYCO technical support."
                ),
                "citations": [],
                "confidence": 0.0,
            }

        elapsed_ms = int((time.time() - start_time) * 1000)
        result["processing_time_ms"] = elapsed_ms
        return result

    def answer_question(
        self,
        question: str,
        conversation_history: Optional[list[dict[str, str]]] = None,
        source_filter: Optional[str] = None,
    ) -> dict[str, Any]:
        """Synchronous wrapper."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.answer_question_async(question, conversation_history, source_filter)
            )
        else:
            future = asyncio.ensure_future(
                self.answer_question_async(question, conversation_history, source_filter),
                loop=loop,
            )
            return loop.run_until_complete(future)

