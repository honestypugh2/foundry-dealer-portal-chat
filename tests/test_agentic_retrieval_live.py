"""Live Integration Test - Foundry Agent Service + Agentic Retrieval (MCPTool)

Tests the Foundry agent with AGENTIC_RETRIEVAL_ENABLED=true, using MCPTool
to query the knowledge base via the MCP endpoint.

Logs detailed execution trace:
- Query sent to agent
- Tool calls (MCP knowledge_base_retrieve invocations / sub-queries)
- Tool results (merged retrieval results)
- Final synthesized output
- Latency breakdown per phase

Usage:
    cd dealer-portal-exp && python -m tests.test_agentic_retrieval_live

Environment variables required:
    AZURE_AI_PROJECT_ENDPOINT    - Foundry project endpoint
    AZURE_OPENAI_DEPLOYMENT      - Model deployment (gpt-5)
    AZURE_SEARCH_ENDPOINT        - Azure AI Search endpoint
    AGENTIC_RETRIEVAL_ENABLED    - Must be "true"
    MCP_PROJECT_CONNECTION_NAME  - MCP connection name (default: dealer-knowledge-mcp-connection)
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

# Force agentic retrieval mode
os.environ["AGENTIC_RETRIEVAL_ENABLED"] = "true"

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"agentic_retrieval_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

file_formatter = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
console_formatter = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

fh = logging.FileHandler(LOG_FILE)
fh.setLevel(logging.DEBUG)
fh.setFormatter(file_formatter)
root_logger.addHandler(fh)

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(console_formatter)
root_logger.addHandler(ch)

logger = logging.getLogger("test_agentic_retrieval")

# Suppress noisy SDK logs
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
# Detailed result with execution trace
# ---------------------------------------------------------------------------
class AgenticTestResult:
    def __init__(self, query: str):
        self.query = query
        self.answer: str = ""
        self.citations: List[Dict] = []
        self.confidence: float = 0.0
        self.error: str = ""
        self.success: bool = False

        # Latency breakdown (ms)
        self.total_latency_ms: int = 0
        self.agent_creation_ms: int = 0
        self.tool_execution_ms: int = 0
        self.response_generation_ms: int = 0

        # Execution trace
        self.tool_calls: List[Dict] = []  # MCP tool invocations (sub-queries)
        self.tool_results: List[Dict] = []  # Merged results from knowledge base
        self.stream_events: List[Dict] = []  # All captured events with timestamps

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "success": self.success,
            "latency": {
                "total_ms": self.total_latency_ms,
                "agent_creation_ms": self.agent_creation_ms,
                "tool_execution_ms": self.tool_execution_ms,
                "response_generation_ms": self.response_generation_ms,
            },
            "answer_length": len(self.answer),
            "answer_preview": self.answer[:800] + ("..." if len(self.answer) > 800 else ""),
            "citations_count": len(self.citations),
            "citations": self.citations[:10],
            "tool_calls_count": len(self.tool_calls),
            "tool_calls": self.tool_calls,
            "tool_results_count": len(self.tool_results),
            "tool_results_preview": [
                {k: v[:200] if isinstance(v, str) and len(v) > 200 else v for k, v in r.items()}
                for r in self.tool_results[:5]
            ],
            "stream_events_count": len(self.stream_events),
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Direct Retrieve API call (outside MCP) to capture sub-queries/activity
# ---------------------------------------------------------------------------
async def retrieve_with_activity(query: str) -> Dict[str, Any]:
    """Call the knowledge base retrieve action directly with include_activity=true.

    This shows the sub-queries generated by the reasoning engine.
    """
    import aiohttp

    search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT", "")
    api_key = os.getenv("AZURE_SEARCH_API_KEY", "")
    kb_name = "dealer-knowledge-base"
    api_version = "2025-11-01-Preview"

    url = f"{search_endpoint}/knowledgebases/{kb_name}/retrieve?api-version={api_version}"
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "messages": [{"role": "user", "content": [{"type": "text", "text": query}]}],
        "includeActivity": True,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data
                else:
                    text = await resp.text()
                    logger.warning(f"    Retrieve API returned {resp.status}: {text[:200]}")
                    return {"error": f"HTTP {resp.status}", "detail": text[:200]}
    except Exception as e:
        logger.warning(f"    Retrieve API call failed: {e}")
        return {"error": str(e)}


def log_activity_trace(activity: list, query: str):
    """Log the sub-queries and search operations from the activity array."""
    if not activity:
        logger.info("    📋 No activity trace returned")
        return

    logger.info(f"    📋 Activity Trace ({len(activity)} steps) for: \"{query[:60]}\"")
    for idx, step in enumerate(activity):
        step_type = step.get("type", "unknown")

        if step_type == "modelQueryPlanning":
            tokens_in = step.get("inputTokens", "?")
            tokens_out = step.get("outputTokens", "?")
            elapsed = step.get("elapsedMs", "?")
            logger.info(f"      [{idx+1}] MODEL QUERY PLANNING: in={tokens_in} out={tokens_out} tokens ({elapsed}ms)")

        elif step_type == "searchIndex":
            args = step.get("searchIndexArguments", {})
            search_query = args.get("search", "?")
            doc_count = step.get("count", "?")
            elapsed = step.get("elapsedMs", "?")
            ks_name = step.get("knowledgeSourceName", "")
            logger.info(f"      [{idx+1}] SEARCH: \"{search_query}\" → {doc_count} docs ({elapsed}ms) [source: {ks_name}]")

        elif step_type == "agenticReasoning":
            effort = step.get("retrievalReasoningEffort", {})
            effort_kind = effort.get("kind", "?") if isinstance(effort, dict) else effort
            reasoning_tokens = step.get("reasoningTokens", "?")
            logger.info(f"      [{idx+1}] AGENTIC REASONING: effort={effort_kind}, reasoning_tokens={reasoning_tokens}")

        elif step_type in ("synthesis", "answer", "generate"):
            tokens_in = step.get("inputTokens", "?")
            tokens_out = step.get("outputTokens", "?")
            elapsed = step.get("elapsedMs", "?")
            logger.info(f"      [{idx+1}] {step_type.upper()}: in={tokens_in} out={tokens_out} tokens ({elapsed}ms)")

        else:
            # Log unknown step types with raw data
            logger.info(f"      [{idx+1}] {step_type.upper()}: {json.dumps(step)[:250]}")


# ---------------------------------------------------------------------------
# Foundry Agent with Agentic Retrieval - detailed execution
# ---------------------------------------------------------------------------
async def test_agentic_retrieval(query: str, query_idx: int) -> AgenticTestResult:
    """Test a query using Foundry Agent + MCPTool with detailed execution logging."""
    from azure.ai.projects.aio import AIProjectClient
    from azure.ai.projects.models import MCPTool, PromptAgentDefinition
    from azure.identity.aio import DefaultAzureCredential
    from app.agents.prompts import DEALER_SYSTEM_PROMPT

    result = AgenticTestResult(query=query)

    logger.info(f"\n{'='*100}")
    logger.info(f"  QUERY {query_idx + 1}/{len(TEST_QUERIES)}: {query}")
    logger.info(f"{'='*100}")

    total_start = time.time()

    try:
        # --- Phase 1: Agent Creation ---
        phase_start = time.time()

        project_endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT", "")
        model = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5")
        search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT", "")
        mcp_connection_name = os.getenv("MCP_PROJECT_CONNECTION_NAME", "dealer-knowledge-mcp-connection")
        kb_name = "dealer-knowledge-base"
        api_version = "2025-11-01-Preview"
        mcp_endpoint = f"{search_endpoint}/knowledgebases/{kb_name}/mcp?api-version={api_version}"

        logger.info(f"  [Config]")
        logger.info(f"    Model:          {model}")
        logger.info(f"    MCP Endpoint:   {mcp_endpoint}")
        logger.info(f"    Connection:     {mcp_connection_name}")

        # --- Direct Retrieve API call to capture sub-queries ---
        logger.info(f"  [Direct Retrieve - Activity Trace]")
        retrieve_start = time.time()
        retrieve_data = await retrieve_with_activity(query)
        retrieve_elapsed = int((time.time() - retrieve_start) * 1000)
        logger.info(f"    Retrieve API completed in {retrieve_elapsed}ms")

        activity = retrieve_data.get("activity", [])
        log_activity_trace(activity, query)

        # Log reference count from direct retrieve
        references = retrieve_data.get("references", [])
        if references:
            logger.info(f"    References: {len(references)} docs returned")

        mcp_tool = MCPTool(
            server_label="knowledge-base",
            server_url=mcp_endpoint,
            require_approval="never",
            allowed_tools=["knowledge_base_retrieve"],
            project_connection_id=mcp_connection_name,
        )

        credential = DefaultAzureCredential()

        async with AIProjectClient(
            endpoint=project_endpoint,
            credential=credential,
        ) as project_client, project_client.get_openai_client() as openai_client:

            agent = await project_client.agents.create_version(
                agent_name="DealerTechAgent-AgenticRetrieval",
                definition=PromptAgentDefinition(
                    model=model,
                    instructions=DEALER_SYSTEM_PROMPT,
                    tools=[mcp_tool],
                ),
                description="JAYCO dealer agent with agentic retrieval via MCPTool",
            )

            result.agent_creation_ms = int((time.time() - phase_start) * 1000)
            logger.info(f"  [Phase 1: Agent Creation] {result.agent_creation_ms}ms")
            logger.info(f"    Agent: {agent.name} (version: {agent.version})")

            try:
                # --- Phase 2: Query Execution (tool calls + response) ---
                phase_start = time.time()

                prompt = (
                    f"Answer the following JAYCO dealer technical question.\n\n"
                    f"QUESTION: {query}\n\n"
                    f"Search the knowledge base for relevant technical documentation "
                    f"and provide a detailed answer with citations."
                )

                conversation = await openai_client.conversations.create()
                logger.info(f"  [Phase 2: Query Execution]")
                logger.info(f"    Conversation: {conversation.id}")
                logger.info(f"    Sending query to agent with tool_choice='required'...")

                try:
                    response_text = ""
                    citations = []
                    tool_call_start = None
                    current_tool_args = ""

                    stream = await openai_client.responses.create(
                        conversation=conversation.id,
                        extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
                        input=prompt,
                        stream=True,
                        tool_choice="required",
                    )

                    first_text_token_time = None
                    event_count = 0

                    async for event in stream:
                        event_time = time.time()
                        event_count += 1
                        event_type = getattr(event, "type", "unknown")

                        # Track all events
                        result.stream_events.append({
                            "idx": event_count,
                            "type": event_type,
                            "elapsed_ms": int((event_time - phase_start) * 1000),
                        })

                        # --- Tool call detection ---
                        if event_type == "response.mcp_call.in_progress":
                            tool_call_start = event_time
                            logger.info(f"    ⚡ MCP tool call started (event {event_count})")

                        elif event_type == "response.mcp_call.completed":
                            tool_elapsed = int((event_time - (tool_call_start or phase_start)) * 1000)
                            result.tool_execution_ms += tool_elapsed
                            # Try to extract call details
                            call_data = {}
                            if hasattr(event, "call"):
                                call = event.call
                                call_data = {
                                    "tool": getattr(call, "tool_name", getattr(call, "name", "knowledge_base_retrieve")),
                                    "latency_ms": tool_elapsed,
                                }
                                if hasattr(call, "arguments"):
                                    try:
                                        args = json.loads(call.arguments) if isinstance(call.arguments, str) else call.arguments
                                        call_data["arguments"] = args
                                        logger.info(f"    ⚡ MCP tool call completed ({tool_elapsed}ms)")
                                        logger.info(f"      Arguments: {json.dumps(args, indent=2)[:300]}")
                                    except (json.JSONDecodeError, TypeError):
                                        call_data["arguments_raw"] = str(call.arguments)[:200]
                                if hasattr(call, "output"):
                                    output = call.output
                                    if isinstance(output, str):
                                        try:
                                            parsed = json.loads(output)
                                            call_data["result_keys"] = list(parsed.keys()) if isinstance(parsed, dict) else f"list[{len(parsed)}]"
                                            result.tool_results.append(parsed if isinstance(parsed, dict) else {"data": parsed})
                                            logger.info(f"      Result keys: {call_data['result_keys']}")

                                            # --- Log sub-queries from activity array ---
                                            activity = parsed.get("activity", [])
                                            if activity:
                                                logger.info(f"      Sub-queries ({len(activity)} iterations):")
                                                for act_idx, act in enumerate(activity):
                                                    act_type = act.get("type", "unknown")
                                                    if act_type == "queryPlan":
                                                        queries = act.get("queries", [])
                                                        logger.info(f"        [{act_idx+1}] Query Plan — {len(queries)} sub-query(ies):")
                                                        for sq_idx, sq in enumerate(queries):
                                                            sq_text = sq.get("text", sq.get("query", ""))
                                                            sq_type = sq.get("type", "")
                                                            sq_fields = sq.get("searchFields", [])
                                                            logger.info(f"            Sub-query {sq_idx+1}: \"{sq_text}\" (type={sq_type}, fields={sq_fields})")
                                                    elif act_type == "search":
                                                        sq_text = act.get("query", act.get("text", ""))
                                                        doc_count = act.get("documentCount", act.get("resultsCount", "?"))
                                                        logger.info(f"        [{act_idx+1}] Search: \"{sq_text}\" → {doc_count} docs")
                                                    elif act_type == "synthesis" or act_type == "answer":
                                                        tokens = act.get("outputTokens", act.get("tokens", "?"))
                                                        logger.info(f"        [{act_idx+1}] {act_type.title()}: output_tokens={tokens}")
                                                    else:
                                                        logger.info(f"        [{act_idx+1}] {act_type}: {json.dumps(act)[:200]}")
                                                call_data["sub_queries"] = activity

                                            # Log references
                                            refs = parsed.get("references", parsed.get("results", []))
                                            if isinstance(refs, list) and refs:
                                                logger.info(f"      Retrieved {len(refs)} reference(s)")
                                                for ref_idx, ref in enumerate(refs[:5]):
                                                    ref_name = ref.get("document_name", ref.get("title", ref.get("id", "?")))
                                                    logger.info(f"        [{ref_idx+1}] {ref_name}")
                                        except (json.JSONDecodeError, TypeError):
                                            call_data["output_preview"] = str(output)[:300]
                                            result.tool_results.append({"raw": str(output)[:500]})
                                            logger.info(f"      Result preview: {str(output)[:200]}...")
                            result.tool_calls.append(call_data)
                            tool_call_start = None

                        # --- Function call arguments (fallback for older event format) ---
                        elif event_type == "response.function_call_arguments.delta":
                            delta = getattr(event, "delta", "")
                            current_tool_args += delta

                        elif event_type == "response.function_call_arguments.done":
                            if current_tool_args:
                                try:
                                    args = json.loads(current_tool_args)
                                    logger.info(f"    🔍 Tool arguments: {json.dumps(args, indent=2)[:300]}")
                                    result.tool_calls.append({
                                        "tool": "knowledge_base_retrieve",
                                        "arguments": args,
                                        "elapsed_ms": int((event_time - phase_start) * 1000),
                                    })
                                except json.JSONDecodeError:
                                    logger.info(f"    🔍 Tool arguments (raw): {current_tool_args[:200]}")
                                current_tool_args = ""

                        # --- Output item done (contains tool results or message) ---
                        elif event_type == "response.output_item.done":
                            if hasattr(event, "item"):
                                item = event.item
                                item_type = getattr(item, "type", "")

                                # MCP tool result item
                                if item_type in ("mcp_call", "function_call_output", "tool_call"):
                                    output = getattr(item, "output", getattr(item, "result", ""))
                                    if output:
                                        elapsed = int((event_time - phase_start) * 1000)
                                        try:
                                            parsed = json.loads(output) if isinstance(output, str) else output
                                            if isinstance(parsed, dict):
                                                result.tool_results.append(parsed)

                                                # --- Log sub-queries from activity array ---
                                                activity = parsed.get("activity", [])
                                                if activity:
                                                    logger.info(f"    📋 Activity trace ({len(activity)} steps):")
                                                    for act_idx, act in enumerate(activity):
                                                        act_type = act.get("type", "unknown")
                                                        if act_type == "queryPlan":
                                                            queries = act.get("queries", [])
                                                            logger.info(f"        [{act_idx+1}] Query Plan — {len(queries)} sub-query(ies):")
                                                            for sq_idx, sq in enumerate(queries):
                                                                sq_text = sq.get("text", sq.get("query", ""))
                                                                sq_type = sq.get("type", "")
                                                                sq_fields = sq.get("searchFields", [])
                                                                logger.info(f"              Sub-query {sq_idx+1}: \"{sq_text}\" (type={sq_type}, fields={sq_fields})")
                                                        elif act_type == "search":
                                                            sq_text = act.get("query", act.get("text", ""))
                                                            doc_count = act.get("documentCount", act.get("resultsCount", "?"))
                                                            logger.info(f"        [{act_idx+1}] Search: \"{sq_text}\" → {doc_count} docs")
                                                        elif act_type in ("synthesis", "answer"):
                                                            tokens = act.get("outputTokens", act.get("tokens", "?"))
                                                            logger.info(f"        [{act_idx+1}] {act_type.title()}: output_tokens={tokens}")
                                                        else:
                                                            logger.info(f"        [{act_idx+1}] {act_type}: {json.dumps(act)[:200]}")

                                                refs = parsed.get("references", parsed.get("results", parsed.get("data", [])))
                                                if isinstance(refs, list) and refs:
                                                    logger.info(f"    📦 Tool result ({elapsed}ms): {len(refs)} items retrieved")
                                                    for ref_idx, ref in enumerate(refs[:5]):
                                                        doc_name = ref.get("document_name", ref.get("metadata_storage_name", ref.get("title", "?")))
                                                        score = ref.get("score", ref.get("@search.score", ""))
                                                        logger.info(f"        [{ref_idx+1}] {doc_name} (score: {score})")
                                                else:
                                                    logger.info(f"    📦 Tool result ({elapsed}ms): keys={list(parsed.keys())[:10]}")
                                            elif isinstance(parsed, list):
                                                result.tool_results.append({"data": parsed})
                                                logger.info(f"    📦 Tool result ({elapsed}ms): {len(parsed)} items")
                                        except (json.JSONDecodeError, TypeError):
                                            result.tool_results.append({"raw": str(output)[:2000]})
                                            # For non-JSON output (answerSynthesis mode), log the text
                                            output_preview = str(output)[:500]
                                            logger.info(f"    📦 Tool result ({elapsed}ms) [text]: {output_preview[:200]}...")
                                            # Try to extract "Retrieved N documents" count
                                            if "Retrieved" in output_preview:
                                                logger.info(f"    📋 Raw output (first 500 chars): {output_preview}")

                                # Message with annotations (citations)
                                elif item_type == "message":
                                    if hasattr(item, "content") and item.content:
                                        for content_item in item.content:
                                            annotations = getattr(content_item, "annotations", None)
                                            if annotations:
                                                for annotation in annotations:
                                                    ann_type = getattr(annotation, "type", "")
                                                    if ann_type in ("url_citation", "file_citation"):
                                                        citations.append({
                                                            "url": getattr(annotation, "url", getattr(annotation, "file_id", "")),
                                                            "title": getattr(annotation, "title", getattr(annotation, "filename", "")),
                                                            "text": getattr(annotation, "text", ""),
                                                            "type": ann_type,
                                                        })

                        # --- Text output ---
                        elif event_type == "response.output_text.delta":
                            if first_text_token_time is None:
                                first_text_token_time = event_time
                                ttft = int((first_text_token_time - phase_start) * 1000)
                                logger.info(f"    ✏️  First text token received ({ttft}ms from query start)")
                            response_text += event.delta

                        elif event_type == "response.output_text.done":
                            pass  # final text captured via deltas

                        # --- Catch-all for interesting events ---
                        elif "tool" in event_type or "mcp" in event_type or "function" in event_type:
                            logger.debug(f"    [event {event_count}] {event_type}")

                    # Phase 2 complete
                    phase2_elapsed = int((time.time() - phase_start) * 1000)
                    result.response_generation_ms = phase2_elapsed - result.tool_execution_ms

                    logger.info(f"\n  [Phase 2 Summary]")
                    logger.info(f"    Total query execution: {phase2_elapsed}ms")
                    logger.info(f"    Tool execution time:   {result.tool_execution_ms}ms")
                    logger.info(f"    Response generation:   {result.response_generation_ms}ms")
                    logger.info(f"    Stream events:         {event_count}")
                    logger.info(f"    Tool calls:            {len(result.tool_calls)}")
                    logger.info(f"    Tool results:          {len(result.tool_results)}")

                finally:
                    await openai_client.conversations.delete(conversation_id=conversation.id)

            finally:
                persist = os.getenv("PERSIST_FOUNDRY_AGENTS", "false").lower() == "true"
                if not persist:
                    await project_client.agents.delete_version(
                        agent_name=agent.name,
                        agent_version=agent.version,
                    )

        # --- Final results ---
        result.total_latency_ms = int((time.time() - total_start) * 1000)
        result.answer = response_text
        result.citations = citations
        result.confidence = 0.85 if response_text else 0.0
        result.success = bool(response_text and len(response_text) > 50)

        logger.info(f"\n  [Final Output]")
        logger.info(f"    Total latency:  {result.total_latency_ms}ms")
        logger.info(f"    Answer length:  {len(result.answer)} chars")
        logger.info(f"    Citations:      {len(result.citations)}")
        if result.citations:
            for i, cit in enumerate(result.citations[:5], 1):
                logger.info(f"      [{i}] {cit.get('title', cit.get('url', '?'))}")
        logger.info(f"    Answer preview:")
        for line in result.answer[:600].split("\n")[:10]:
            logger.info(f"      {line}")

    except Exception as e:
        result.error = str(e)
        result.total_latency_ms = int((time.time() - total_start) * 1000)
        logger.error(f"  ❌ FAILED ({result.total_latency_ms}ms): {e}", exc_info=True)

    return result


# ---------------------------------------------------------------------------
# Main test runner
# ---------------------------------------------------------------------------
async def run_tests():
    """Run all test queries against Foundry Agent + Agentic Retrieval."""
    logger.info("=" * 100)
    logger.info("  JAYCO Dealer Portal - Agentic Retrieval Integration Test")
    logger.info("  Mode: FOUNDRY AGENT SERVICE + MCPTool (knowledge_base_retrieve)")
    logger.info("=" * 100)
    logger.info(f"  Started:  {datetime.now().isoformat()}")
    logger.info(f"  Log file: {LOG_FILE}")
    logger.info(f"  Queries:  {len(TEST_QUERIES)}")
    logger.info("")

    # Verify config
    required_vars = ["AZURE_AI_PROJECT_ENDPOINT", "AZURE_SEARCH_ENDPOINT"]
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        logger.error(f"Missing required environment variables: {missing}")
        return

    search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT", "")
    mcp_endpoint = f"{search_endpoint}/knowledgebases/dealer-knowledge-base/mcp?api-version=2025-11-01-Preview"

    logger.info("  Configuration:")
    logger.info(f"    Project Endpoint:  {os.getenv('AZURE_AI_PROJECT_ENDPOINT', '')[:60]}...")
    logger.info(f"    Search Endpoint:   {search_endpoint}")
    logger.info(f"    MCP Endpoint:      {mcp_endpoint}")
    logger.info(f"    Model:             {os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-5')}")
    logger.info(f"    MCP Connection:    {os.getenv('MCP_PROJECT_CONNECTION_NAME', 'dealer-knowledge-mcp-connection')}")
    logger.info(f"    Agentic Retrieval: {os.getenv('AGENTIC_RETRIEVAL_ENABLED', 'true')}")
    logger.info("")

    all_results: List[AgenticTestResult] = []

    for idx, query in enumerate(TEST_QUERIES):
        result = await test_agentic_retrieval(query, idx)
        all_results.append(result)

    # ---------------------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------------------
    logger.info(f"\n{'='*100}")
    logger.info("  TEST SUMMARY - Agentic Retrieval (MCPTool)")
    logger.info(f"{'='*100}")

    success_count = sum(1 for r in all_results if r.success)
    avg_total = sum(r.total_latency_ms for r in all_results) / max(len(all_results), 1)
    avg_tool = sum(r.tool_execution_ms for r in all_results) / max(len(all_results), 1)
    avg_response = sum(r.response_generation_ms for r in all_results) / max(len(all_results), 1)
    avg_citations = sum(len(r.citations) for r in all_results) / max(len(all_results), 1)
    avg_tool_calls = sum(len(r.tool_calls) for r in all_results) / max(len(all_results), 1)

    logger.info(f"\n  Overall: {success_count}/{len(all_results)} succeeded")
    logger.info(f"  Avg total latency:      {avg_total:.0f}ms")
    logger.info(f"  Avg tool execution:     {avg_tool:.0f}ms")
    logger.info(f"  Avg response generation:{avg_response:.0f}ms")
    logger.info(f"  Avg citations:          {avg_citations:.1f}")
    logger.info(f"  Avg MCP tool calls:     {avg_tool_calls:.1f}")

    logger.info(f"\n  {'Query':<60} {'Total':<10} {'Tool':<10} {'Resp':<10} {'Cit':<6} {'Calls':<6}")
    logger.info(f"  {'-'*102}")
    for r in all_results:
        q_short = r.query[:57] + "..." if len(r.query) > 57 else r.query
        status = "✓" if r.success else "✗"
        logger.info(
            f"  {status} {q_short:<58} "
            f"{r.total_latency_ms:>6}ms "
            f"{r.tool_execution_ms:>6}ms "
            f"{r.response_generation_ms:>6}ms "
            f"{len(r.citations):>4} "
            f"{len(r.tool_calls):>4}"
        )

    # Failures
    failures = [r for r in all_results if not r.success]
    if failures:
        logger.info(f"\n  FAILURES ({len(failures)}):")
        for f in failures:
            logger.info(f"    {f.query[:60]}...")
            logger.info(f"      Error: {f.error[:200]}")

    # Save detailed results
    results_file = LOG_DIR / f"agentic_retrieval_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, "w") as fp:
        json.dump(
            {
                "test_run": datetime.now().isoformat(),
                "mode": "foundry_agentic_retrieval",
                "config": {
                    "project_endpoint": os.getenv("AZURE_AI_PROJECT_ENDPOINT", "")[:60],
                    "search_endpoint": search_endpoint,
                    "mcp_endpoint": mcp_endpoint,
                    "model": os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5"),
                    "mcp_connection": os.getenv("MCP_PROJECT_CONNECTION_NAME", "dealer-knowledge-mcp-connection"),
                },
                "summary": {
                    "success": success_count,
                    "total": len(all_results),
                    "avg_total_latency_ms": round(avg_total),
                    "avg_tool_execution_ms": round(avg_tool),
                    "avg_response_generation_ms": round(avg_response),
                    "avg_citations": round(avg_citations, 1),
                    "avg_tool_calls": round(avg_tool_calls, 1),
                },
                "results": [r.to_dict() for r in all_results],
            },
            fp,
            indent=2,
        )
    logger.info(f"\n  Detailed results: {results_file}")
    logger.info(f"  Full log:         {LOG_FILE}")
    logger.info(f"\n  Completed: {datetime.now().isoformat()}")


if __name__ == "__main__":
    asyncio.run(run_tests())
