# Agent Architecture & Modes

This document details the two agent modes available in the JAYCO Dealer Portal
and how they differ in implementation, capabilities, and trade-offs.

---

## Agent Routing

The `AGENT_SERVICE` environment variable controls which agent implementation handles queries:

```
AGENT_SERVICE=agent_framework   → DealerPortalOrchestrator → DealerTechAgent (autonomous search)
AGENT_SERVICE=foundry           → DealerAgentFoundry (Foundry Agent Service)
```

When `SIMULATED_MODE=true`, neither agent is invoked — the system uses direct
in-memory search + LLM generation for zero-dependency local development.

---

## Mode 1: Agent Framework (`agent_framework`)

### Architecture

The orchestrator delegates directly to `DealerTechAgent`, which autonomously
searches Azure AI Search via its `@tool`-decorated method. There is no
pre-retrieval step — the model decides when and how to search.

```
┌─────────────────────────────────────────────────────────────┐
│                 DealerPortalOrchestrator                      │
│                                                               │
│  Delegates to DealerTechAgent (FoundryChatClient)            │
│    ├── Receives user question                                │
│    ├── Autonomously calls @tool search_technical_documents   │
│    │   └── Azure AI Search (hybrid + semantic reranking)     │
│    └── Generates grounded answer with citations              │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | File | Role |
|-----------|------|------|
| `DealerPortalOrchestrator` | `agents/orchestrator.py` | Delegates to agent, tracks timing |
| `DealerTechAgent` | `agents/dealer_agent.py` | Agent with FoundryChatClient + @tool |
| `search_technical_documents` | `agents/dealer_agent.py` | @tool: Azure AI Search (semantic) |
| `DEALER_SYSTEM_PROMPT` | `agents/prompts.py` | Shared system instructions |

### Characteristics

- **Model-driven retrieval** — agent decides search queries (may be better than raw user query)
- **Autonomous tool use** — agent searches as many times as needed
- **Aligned with Microsoft pattern** — same as Foundry path (model + instructions + tools)
- **Transparent** — tool calls are logged for debugging
- **Fallback** — returns error message if agent/endpoint unavailable

---

## Mode 2: Foundry Agent Service (`foundry`)

### Architecture

A single-turn agent lifecycle using Azure AI Foundry Agent Service.
The retrieval tool is selected by `AGENTIC_RETRIEVAL_ENABLED`:

```
┌─────────────────────────────────────────────────────────────┐
│                    DealerAgentFoundry                         │
│                                                               │
│  1. Create agent                                              │
│     ├── Model: gpt-4.1-mini                                  │
│     ├── Instructions: system prompt from prompts.py          │
│     └── Tools: _get_tools() →                                │
│         ├── AGENTIC_RETRIEVAL_ENABLED=true → MCPTool         │
│         └── AGENTIC_RETRIEVAL_ENABLED=false → AzureAISearch  │
│                                                               │
│  2. Create conversation                                       │
│                                                               │
│  3. Stream response (tool_choice="required")                  │
│     ├── Foundry orchestrates tool calls automatically        │
│     ├── MCPTool → Knowledge Base (sub-queries + retrieval)   │
│     └── Model generates grounded response                    │
│                                                               │
│  4. Extract answer + inline citations (regex + annotations)   │
│                                                               │
│  5. Cleanup (delete conversation + agent unless persisted)    │
└─────────────────────────────────────────────────────────────┘
```

### MCPTool (Agentic Retrieval) — Primary Path

When `AGENTIC_RETRIEVAL_ENABLED=true` (default), the agent uses an MCPTool
connected to the Azure AI Search Knowledge Base:

```python
MCPTool(
    server_label="knowledge-base",
    server_url="{search_endpoint}/knowledgebases/dealer-knowledge-base/mcp?api-version=2025-11-01-Preview",
    require_approval="never",
    allowed_tools=["knowledge_base_retrieve"],
    project_connection_id="dealer-knowledge-mcp-connection",
)
```

The Knowledge Base uses its own model (`gpt-4.1-mini`, `extractiveData` output mode)
to autonomously generate sub-queries, search the index, and reason over results.

### AzureAISearchTool — Fallback Path

When `AGENTIC_RETRIEVAL_ENABLED=false`, falls back to the standard tool:

```python
AzureAISearchTool(indexes=[AISearchIndexResource(
    project_connection_id=...,
    index_name="dealer-portal-docs",
    query_type=AzureAISearchQueryType.SEMANTIC,
)])
```

### Key Components

| Component | File | Role |
|-----------|------|------|
| `DealerAgentFoundry` | `agents/dealer_agent_foundry.py` | Full agent lifecycle |
| `_build_mcp_tool` | `agents/dealer_agent_foundry.py` | MCPTool for agentic retrieval |
| `_build_azure_ai_search_tool` | `agents/dealer_agent_foundry.py` | Fallback AI Search tool |
| `_get_tools` | `agents/dealer_agent_foundry.py` | Selects tool based on config |
| `AGENTIC_RETRIEVAL_ENABLED` | `.env` | Toggle MCPTool vs AzureAISearchTool |
| `PERSIST_FOUNDRY_AGENTS` | `.env` | Keep agent between requests |
| `MAX_OUTPUT_TOKENS` | `.env` | Cap agent response length (default 4096) |

### Characteristics

- **Managed infrastructure** — Foundry handles tool orchestration
- **Forced grounding** — `tool_choice="required"` ensures search before answering
- **Agentic retrieval** — KB model generates sub-queries for better recall
- **Simpler code** — no manual retrieval logic
- **Less control** — can't customize individual search parameters with MCPTool
- **Cost** — agent creation/deletion per request (unless persisted)

---

## Comparison

| Aspect | Agent Framework | Foundry + MCPTool | Foundry + AzureAISearchTool |
|--------|----------------|-------------------|----------------------------|
| Retrieval | Model-driven via @tool | KB model generates sub-queries | Model-driven via Foundry |
| Search control | Custom SDK params | KB config (outputMode, reasoning) | Connection-based |
| Forced grounding | Agent prompt instructs | `tool_choice="required"` | `tool_choice="required"` |
| Multiple searches | Agent calls tool N times | KB autonomously multi-searches | Agent re-invokes tool |
| Debugging | Tool call logs in app | Agent logs + KB traces in portal | Agent run logs |
| Latency | Single agent call | ~10-30s (KB retrieval + generation) | Agent create + run + cleanup |
| Code complexity | Moderate | Lower (single class) | Lower (single class) |
| Dependencies | `agent-framework` + `azure-search-documents` | `azure-ai-projects` SDK | `azure-ai-projects` SDK |
| Best for | Custom search logic | Production (best recall) | Simple production setup |

---

## Simulated Mode

When `SIMULATED_MODE=true`, the system bypasses both agent paths:

1. `AISearchService` performs in-memory keyword matching against 11 hardcoded chunks
2. `OpenAIService` generates an answer using the matched chunks as context
3. No Azure resources required — fully local development

This mode uses the same `ChatResponse` schema, so the frontend works identically
regardless of which backend mode is active.

---

## Configuration Reference

```bash
# Route to agent framework (autonomous agent with @tool search)
AGENT_SERVICE=agent_framework

# Route to Foundry Agent Service (recommended)
AGENT_SERVICE=foundry
AI_SEARCH_PROJECT_CONNECTION_ID=<connection-id-from-foundry-portal>
AGENTIC_RETRIEVAL_ENABLED=true          # MCPTool + Knowledge Base (default)
AZURE_OPENAI_KB_MODEL_DEPLOYMENT=gpt-4.1-mini  # KB query-planning model
MAX_OUTPUT_TOKENS=4096                   # Cap agent response length
MAX_CITATIONS=5                          # Max citations per response
PERSIST_FOUNDRY_AGENTS=true              # Keep agent between requests

# Skip agents entirely (local dev)
SIMULATED_MODE=true
```
