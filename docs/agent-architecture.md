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

A single-turn agent lifecycle using Azure AI Foundry Agent Service:

```
┌─────────────────────────────────────────────────────────────┐
│                    DealerAgentFoundry                         │
│                                                               │
│  1. Create agent                                              │
│     ├── Model: GPT deployment                                │
│     ├── Instructions: system prompt from prompts.py          │
│     └── Tools: [AzureAISearchTool(index, connection)]        │
│                                                               │
│  2. Create conversation                                       │
│                                                               │
│  3. Stream response (tool_choice="required")                  │
│     ├── Foundry orchestrates tool calls automatically        │
│     ├── AzureAISearchTool queries the index                  │
│     └── Model generates grounded response                    │
│                                                               │
│  4. Extract answer + annotations → citations                  │
│                                                               │
│  5. Cleanup (delete conversation + agent)                     │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | File | Role |
|-----------|------|------|
| `DealerAgentFoundry` | `agents/dealer_agent_foundry.py` | Full agent lifecycle |
| `_build_azure_ai_search_tool` | `agents/dealer_agent_foundry.py` | Configures AI Search tool |
| `AI_SEARCH_PROJECT_CONNECTION_ID` | `.env` | Connects agent to search index |
| `PERSIST_FOUNDRY_AGENTS` | `.env` | Keep agent between requests |

### Characteristics

- **Managed infrastructure** — Foundry handles tool orchestration
- **Forced grounding** — `tool_choice="required"` ensures search before answering
- **Simpler code** — no manual retrieval logic
- **Less control** — can't customize search parameters
- **Cost** — agent creation/deletion per request (unless persisted)

---

## Comparison

| Aspect | Agent Framework | Foundry Agent Service |
|--------|----------------|----------------------|
| Retrieval | Model-driven via @tool | Model-driven via AzureAISearchTool |
| Search control | Custom SDK params (query_type, top, semantic_config) | Managed by Foundry (connection-based) |
| Forced grounding | Agent prompt instructs search | `tool_choice="required"` enforces it |
| Multiple searches | Agent can call tool multiple times | Agent can re-invoke tool |
| Debugging | Tool call logging in app | Agent run logs in Foundry portal |
| Latency | Single agent call | Agent create + run + cleanup overhead |
| Code complexity | Moderate (orchestrator + agent) | Lower (single class) |
| Dependencies | `agent-framework` + `azure-search-documents` | `azure-ai-projects` SDK |
| Best for | Custom search logic, local development | Production with Foundry ecosystem |

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

# Route to Foundry Agent Service
AGENT_SERVICE=foundry
AI_SEARCH_PROJECT_CONNECTION_ID=<connection-id-from-foundry-portal>
PERSIST_FOUNDRY_AGENTS=false

# Skip agents entirely (local dev)
SIMULATED_MODE=true
```
