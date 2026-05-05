"""Live Integration Test - Agent Framework vs Foundry Agent Service

Runs test queries against both agent modes using actual Azure services:
- Azure AI Search (hybrid + semantic reranking)
- Azure OpenAI (GPT-5)
- Azure AI Foundry Project (Agent Service)

Usage:
    cd src && python -m tests.test_agents_live

    # Or from project root:
    cd dealer-portal-exp && python tests/test_agents_live.py

Environment variables required:
    AZURE_AI_PROJECT_ENDPOINT - Foundry project endpoint
    AZURE_OPENAI_DEPLOYMENT  - GPT-5 deployment name
    AZURE_SEARCH_ENDPOINT    - Azure AI Search endpoint
    AZURE_SEARCH_INDEX_NAME  - Index name (default: dealer-portal-docs)
    AI_SEARCH_PROJECT_CONNECTION_ID - Foundry connection ID for Search (Foundry mode)
    AZURE_SEARCH_API_KEY     - Search admin/query key (Agent Framework mode)
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Ensure src/api is on the path so app.* imports resolve
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "api"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"agent_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Create formatters
file_formatter = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
console_formatter = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)

# Root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# File handler (captures everything)
fh = logging.FileHandler(LOG_FILE)
fh.setLevel(logging.DEBUG)
fh.setFormatter(file_formatter)
root_logger.addHandler(fh)

# Console handler (key events only)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(console_formatter)
root_logger.addHandler(ch)

logger = logging.getLogger("test_agents_live")

# Suppress noisy HTTP-level logs from azure SDK (keep WARNING+)
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
logging.getLogger("azure.identity").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai._base_client").setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# Test queries
# ---------------------------------------------------------------------------
TEST_QUERIES: List[str] = [
    "My trailer has excessive tire wear—what could be causing this and how do I fix it?",
    "I'm noticing high hub temperature and unusual noise from the wheel—what could be wrong?",
    "How do I repack the bearings step by step?",
    "What maintenance should I regularly perform on the suspension system?",
    "How do I identify whether I have a 7K or 8K beam assembly?",
]

# ---------------------------------------------------------------------------
# Results collector
# ---------------------------------------------------------------------------
class TestResult:
    def __init__(self, query: str, mode: str):
        self.query = query
        self.mode = mode
        self.answer: str = ""
        self.citations: List[Dict] = []
        self.confidence: float = 0.0
        self.processing_time_ms: int = 0
        self.error: str = ""
        self.success: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "mode": self.mode,
            "success": self.success,
            "processing_time_ms": self.processing_time_ms,
            "confidence": self.confidence,
            "answer_length": len(self.answer),
            "answer_preview": self.answer[:500] + ("..." if len(self.answer) > 500 else ""),
            "citations_count": len(self.citations),
            "citations": self.citations[:5],
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Agent Framework test
# ---------------------------------------------------------------------------
async def test_agent_framework(query: str, query_idx: int) -> TestResult:
    """Test a query using Agent Framework (DealerTechAgent + FoundryChatClient)."""
    result = TestResult(query=query, mode="agent_framework")
    logger.info(f"{'='*80}")
    logger.info(f"[Agent Framework] Query {query_idx + 1}: {query}")
    logger.info(f"{'='*80}")

    start = time.time()
    try:
        from app.agents.orchestrator import DealerPortalOrchestrator

        orchestrator = DealerPortalOrchestrator(use_azure=True)

        logger.info("[Agent Framework] Step 1: Initializing DealerPortalOrchestrator")
        logger.info(f"  Project Endpoint: {orchestrator.project_endpoint[:50]}...")
        logger.info(f"  Agent: DealerTechAgent (FoundryChatClient)")

        logger.info("[Agent Framework] Step 2: Sending query to agent")
        logger.info(f"  The agent will autonomously decide search queries via @tool")

        response = await orchestrator.answer_question_async(
            question=query,
            conversation_history=[],
        )

        elapsed_ms = int((time.time() - start) * 1000)
        result.processing_time_ms = response.get("processing_time_ms", elapsed_ms)
        result.answer = response.get("answer", "")
        result.citations = response.get("citations", [])
        result.confidence = response.get("confidence", 0.0)
        result.success = bool(result.answer and result.confidence > 0)

        logger.info("[Agent Framework] Step 3: Response received")
        logger.info(f"  Processing time: {result.processing_time_ms}ms")
        logger.info(f"  Confidence: {result.confidence}")
        logger.info(f"  Answer length: {len(result.answer)} chars")
        logger.info(f"  Citations: {len(result.citations)}")

        if result.citations:
            for i, cit in enumerate(result.citations[:3], 1):
                logger.info(f"  Citation {i}: {cit}")

        logger.info(f"  Answer preview: {result.answer[:300]}...")

    except Exception as e:
        result.error = str(e)
        result.processing_time_ms = int((time.time() - start) * 1000)
        logger.error(f"[Agent Framework] FAILED: {e}", exc_info=True)

    return result


# ---------------------------------------------------------------------------
# Foundry Agent Service test
# ---------------------------------------------------------------------------
async def test_foundry_agent(query: str, query_idx: int) -> TestResult:
    """Test a query using Foundry Agent Service (AIProjectClient + AzureAISearchTool)."""
    result = TestResult(query=query, mode="foundry")
    logger.info(f"{'='*80}")
    logger.info(f"[Foundry Agent] Query {query_idx + 1}: {query}")
    logger.info(f"{'='*80}")

    start = time.time()
    try:
        from app.agents.dealer_agent_foundry import DealerAgentFoundry

        agent = DealerAgentFoundry(
            project_endpoint=os.getenv("AZURE_AI_PROJECT_ENDPOINT", ""),
            model_deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5"),
            search_index_name=os.getenv("AZURE_SEARCH_INDEX_NAME", "dealer-portal-docs"),
            search_connection_id=os.getenv("AI_SEARCH_PROJECT_CONNECTION_ID"),
            search_query_type=os.getenv("AI_SEARCH_QUERY_TYPE", "semantic"),
        )

        logger.info("[Foundry Agent] Step 1: Initializing DealerAgentFoundry")
        logger.info(f"  Project Endpoint: {agent.project_endpoint[:50]}...")
        logger.info(f"  Model: {agent.model_deployment_name}")
        logger.info(f"  Index: {agent.search_index_name}")
        logger.info(f"  Connection ID: {agent.search_connection_id[:30]}..." if agent.search_connection_id else "  Connection ID: NOT SET")
        logger.info(f"  Query Type: {agent.search_query_type}")

        logger.info("[Foundry Agent] Step 2: Creating agent + AzureAISearchTool via AIProjectClient")
        logger.info("  Foundry manages: agent creation → search tool invocation → streaming response")

        response = await agent.answer_question(
            question=query,
            context={"conversation_history": []},
        )

        elapsed_ms = int((time.time() - start) * 1000)
        result.processing_time_ms = elapsed_ms
        result.answer = response.get("answer", "")
        result.citations = response.get("citations", [])
        result.confidence = response.get("confidence", 0.0)
        result.success = bool(result.answer and result.confidence > 0)

        logger.info("[Foundry Agent] Step 3: Response received")
        logger.info(f"  Processing time: {result.processing_time_ms}ms")
        logger.info(f"  Confidence: {result.confidence}")
        logger.info(f"  Answer length: {len(result.answer)} chars")
        logger.info(f"  Citations: {len(result.citations)}")

        if result.citations:
            for i, cit in enumerate(result.citations[:3], 1):
                logger.info(f"  Citation {i}: {cit}")

        logger.info(f"  Answer preview: {result.answer[:300]}...")

    except Exception as e:
        result.error = str(e)
        result.processing_time_ms = int((time.time() - start) * 1000)
        logger.error(f"[Foundry Agent] FAILED: {e}", exc_info=True)

    return result


# ---------------------------------------------------------------------------
# Main test runner
# ---------------------------------------------------------------------------
async def run_tests():
    """Run all test queries against both agent modes."""
    logger.info("=" * 80)
    logger.info("JAYCO Dealer Portal - Agent Integration Test")
    logger.info("=" * 80)
    logger.info(f"Test started: {datetime.now().isoformat()}")
    logger.info(f"Log file: {LOG_FILE}")
    logger.info(f"Queries: {len(TEST_QUERIES)}")
    logger.info("")

    # Verify required env vars
    required_vars = [
        "AZURE_AI_PROJECT_ENDPOINT",
        "AZURE_SEARCH_ENDPOINT",
        "AZURE_SEARCH_INDEX_NAME",
    ]
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        logger.error(f"Missing required environment variables: {missing}")
        logger.error("Set these in .env or export them before running.")
        return

    logger.info("Azure Service Configuration:")
    logger.info(f"  AI Foundry Project: {os.getenv('AZURE_AI_PROJECT_ENDPOINT', '')[:60]}...")
    logger.info(f"  Azure AI Search:    {os.getenv('AZURE_SEARCH_ENDPOINT', '')}")
    logger.info(f"  Search Index:       {os.getenv('AZURE_SEARCH_INDEX_NAME', 'dealer-portal-docs')}")
    logger.info(f"  OpenAI Deployment:  {os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-5')}")
    logger.info(f"  Search Connection:  {os.getenv('AI_SEARCH_PROJECT_CONNECTION_ID', 'NOT SET')[:40]}")
    logger.info("")

    all_results: List[TestResult] = []

    # Run Agent Framework tests
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 1: AGENT FRAMEWORK (FoundryChatClient + @tool search)")
    logger.info("  Uses: Azure AI Search SDK → SearchClient.search()")
    logger.info("  Control: Full (top_k, vector query, semantic config, filters)")
    logger.info("=" * 80 + "\n")

    for idx, query in enumerate(TEST_QUERIES):
        result = await test_agent_framework(query, idx)
        all_results.append(result)
        logger.info("")

    # Run Foundry Agent Service tests
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 2: FOUNDRY AGENT SERVICE (AIProjectClient + AzureAISearchTool)")
    logger.info("  Uses: Foundry-managed agent with AzureAISearchTool")
    logger.info("  Control: Limited (connection_id, index_name, query_type only)")
    logger.info("=" * 80 + "\n")

    for idx, query in enumerate(TEST_QUERIES):
        result = await test_foundry_agent(query, idx)
        all_results.append(result)
        logger.info("")

    # ---------------------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------------------
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)

    af_results = [r for r in all_results if r.mode == "agent_framework"]
    foundry_results = [r for r in all_results if r.mode == "foundry"]

    af_success = sum(1 for r in af_results if r.success)
    foundry_success = sum(1 for r in foundry_results if r.success)
    af_avg_time = sum(r.processing_time_ms for r in af_results) / max(len(af_results), 1)
    foundry_avg_time = sum(r.processing_time_ms for r in foundry_results) / max(len(foundry_results), 1)

    logger.info(f"\n{'Mode':<25} {'Success':<12} {'Avg Time':<12} {'Avg Confidence':<15}")
    logger.info(f"{'-'*64}")
    logger.info(
        f"{'Agent Framework':<25} "
        f"{af_success}/{len(af_results):<10} "
        f"{af_avg_time:.0f}ms{'':>5} "
        f"{sum(r.confidence for r in af_results) / max(len(af_results), 1):.2f}"
    )
    logger.info(
        f"{'Foundry Agent Service':<25} "
        f"{foundry_success}/{len(foundry_results):<10} "
        f"{foundry_avg_time:.0f}ms{'':>5} "
        f"{sum(r.confidence for r in foundry_results) / max(len(foundry_results), 1):.2f}"
    )

    # Per-query comparison
    logger.info(f"\n{'Query':<60} {'AF Time':<10} {'Foundry Time':<12} {'AF Cit':<8} {'F Cit':<8}")
    logger.info(f"{'-'*98}")
    for i, query in enumerate(TEST_QUERIES):
        af = af_results[i]
        fr = foundry_results[i]
        q_short = query[:57] + "..." if len(query) > 57 else query
        logger.info(
            f"{q_short:<60} "
            f"{af.processing_time_ms}ms{'':>4} "
            f"{fr.processing_time_ms}ms{'':>6} "
            f"{len(af.citations):<8} "
            f"{len(fr.citations):<8}"
        )

    # Failures
    failures = [r for r in all_results if not r.success]
    if failures:
        logger.info(f"\nFAILURES ({len(failures)}):")
        for f in failures:
            logger.info(f"  [{f.mode}] {f.query[:50]}... → {f.error[:100]}")

    # Save detailed results to JSON
    results_file = LOG_DIR / f"agent_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, "w") as fp:
        json.dump(
            {
                "test_run": datetime.now().isoformat(),
                "config": {
                    "project_endpoint": os.getenv("AZURE_AI_PROJECT_ENDPOINT", "")[:60],
                    "search_endpoint": os.getenv("AZURE_SEARCH_ENDPOINT", ""),
                    "index_name": os.getenv("AZURE_SEARCH_INDEX_NAME", ""),
                    "model": os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5"),
                },
                "summary": {
                    "agent_framework": {"success": af_success, "total": len(af_results), "avg_time_ms": af_avg_time},
                    "foundry": {"success": foundry_success, "total": len(foundry_results), "avg_time_ms": foundry_avg_time},
                },
                "results": [r.to_dict() for r in all_results],
            },
            fp,
            indent=2,
        )
    logger.info(f"\nDetailed results saved to: {results_file}")
    logger.info(f"Full log saved to: {LOG_FILE}")
    logger.info(f"\nTest completed: {datetime.now().isoformat()}")


if __name__ == "__main__":
    asyncio.run(run_tests())
