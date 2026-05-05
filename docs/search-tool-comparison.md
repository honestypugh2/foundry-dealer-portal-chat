# Search Tool Comparison: Agent Framework vs Foundry Agent Service

This document clarifies how each agent mode interacts with Azure AI Search,
what configuration is used at query time, and the three retrieval mechanisms available.

---

## Search Tool Architecture

### Agent Framework (`AGENT_SERVICE=agent_framework`)

The `DealerTechAgent` uses a `@tool`-decorated method that calls the Azure AI Search
SDK directly. **Full control over search parameters.**

```python
# dealer_agent.py → @tool search_technical_documents
results = client.search(
    search_text=query,                                # Keyword (BM25)
    query_type="semantic",                            # Semantic reranking
    semantic_configuration_name="dealer-semantic-config",
    top=5,                                            # Controlled top_k
    vector_queries=[
        VectorizableTextQuery(                        # Vector leg
            text=query,                               # Server-side embedding
            k_nearest_neighbors=5,
            fields="content_vector",
        )
    ],
)
```

### Foundry + MCPTool (`AGENT_SERVICE=foundry`, `AGENTIC_RETRIEVAL_ENABLED=true`) — DEFAULT

The `DealerAgentFoundry` attaches an MCPTool that connects to the Azure AI Search
Knowledge Base. **The KB model autonomously generates sub-queries and reasons over results.**

```python
# dealer_agent_foundry.py → _build_mcp_tool()
MCPTool(
    server_label="knowledge-base",
    server_url=f"{search_endpoint}/knowledgebases/dealer-knowledge-base/mcp?api-version=2025-11-01-Preview",
    require_approval="never",
    allowed_tools=["knowledge_base_retrieve"],
    project_connection_id="dealer-knowledge-mcp-connection",
)
```

The Knowledge Base has its own model (`gpt-4.1-mini`) with `extractiveData` output mode
and `medium` reasoning effort. It generates sub-queries, searches multiple times, and
returns grounded context to the agent.

### Foundry + AzureAISearchTool (`AGENT_SERVICE=foundry`, `AGENTIC_RETRIEVAL_ENABLED=false`)

Fallback mode — `DealerAgentFoundry` attaches an `AzureAISearchTool`. **Foundry manages
all search parameters internally.**

```python
# dealer_agent_foundry.py → _build_azure_ai_search_tool()
AzureAISearchTool(
    azure_ai_search=AzureAISearchToolResource(
        indexes=[
            AISearchIndexResource(
                project_connection_id=self.search_connection_id,
                index_name=self.search_index_name,
                query_type=query_type,           # Only param we control
            )
        ]
    )
)
```

---

## What You Control at Query Time

| Parameter | Agent Framework | Foundry + MCPTool | Foundry + AzureAISearchTool |
|-----------|:--------------:|:-----------------:|:---------------------------:|
| Search text (query) | ✅ Agent decides | ✅ KB generates sub-queries | ✅ Agent decides |
| `top_k` (result count) | ✅ Configurable (default 5) | ❌ KB decides | ❌ Foundry decides |
| Vector query (embedding) | ✅ VectorizableTextQuery | ❌ KB handles internally | ❌ Managed internally |
| Semantic reranking | ✅ Explicit `query_type="semantic"` | ✅ Index semantic config used | ⚠️ Only via `query_type` enum |
| Source filter (OData) | ✅ Can add dynamically | ❌ Not exposed | ❌ Not exposed |
| Field selection | ✅ Choose which fields returned | ❌ KB chooses | ❌ Foundry chooses |
| Semantic config name | ✅ Specified per query | ✅ KB uses index config | ❌ Uses index default |
| Multiple searches | ✅ Agent can call tool N times | ✅ KB autonomously multi-searches | ✅ Agent can re-invoke |
| Reasoning over results | ❌ Agent does this | ✅ KB model reasons before returning | ❌ Agent does this |

---

## What search_config.json Controls

### Index-level settings (apply to BOTH modes)

These are baked into the index at creation time by `AzureAISearchClient.create_index()`.
Once the index exists, they apply to all queries regardless of which agent path is used.

| Setting | Config Path | Effect |
|---------|-------------|--------|
| HNSW algorithm (cosine, m=4, ef=500) | `vector_search.algorithm` | Nearest neighbor search quality |
| Scalar quantization (int8) | `vector_search.compression` | 4x storage reduction |
| Rescoring (oversampling=4) | `vector_search.compression.rescoring_options` | Accuracy after compression |
| Vectorizer (text-embedding-3-large) | `vector_search.vectorizer` | Server-side query embedding |
| Semantic config (content, title, keywords) | `semantic_search` | Which fields the reranker uses |
| Field schema | `search_config.*_field` | Index structure |

### Query-level settings (Agent Framework ONLY)

| Setting | Config Path | Used By |
|---------|-------------|---------|
| `top_k: 5` | `search_config.top_k` | `hybrid_search()` only |
| `source_filter` | Runtime parameter | `hybrid_search()` and `@tool` |
| Semantic config selection | `semantic_search.configuration_name` | `@tool` search call |
| Vector field targeting | `search_config.vector_field` | `hybrid_search()` VectorizedQuery |

**Foundry Agent Service ignores query-level settings.** It can't be told which fields
to prioritize, how many results to return, or how to filter. It relies entirely on
index-level configuration.

---

## Practical Implications

### When Agent Framework search is better:
- You need **source filtering** (e.g., "search only SharePoint docs")
- You need **controlled result count** for predictable context window usage
- You need **field-specific retrieval** (return only certain metadata)
- You want to **log and inspect** exact search parameters per query
- You're **testing or comparing** search configurations

### When Foundry AzureAISearchTool is sufficient:
- Cross-source queries (no filtering needed)
- You trust Foundry's default retrieval behavior
- You want minimal code / managed infrastructure
- You're in a **production Foundry ecosystem** with monitoring via portal

---

## Is the Agent Framework Workflow Orchestrator Needed?

**No — the workflow orchestrator (`WorkflowBuilder`, `Executor`, etc.) is no longer used.**

After simplification, `DealerPortalOrchestrator` is now a thin wrapper:

```python
class DealerPortalOrchestrator:
    async def answer_question_async(self, question, ...):
        result = await self.agent.answer_question_async(question, conversation_history)
        result["processing_time_ms"] = elapsed_ms
        return result
```

It only:
1. Lazy-initializes `DealerTechAgent`
2. Delegates the question directly to it
3. Tracks execution time

### Could it be removed entirely?

**Yes.** The `_process_with_agent_framework()` method in `services/orchestrator.py`
could call `DealerTechAgent` directly instead of going through `DealerPortalOrchestrator`.

However, keeping the thin orchestrator provides:
- A single point to add future steps (e.g., logging, guardrails, rate limiting)
- Consistent naming with the Foundry path (`_get_agent_orchestrator()` / `_get_foundry_agent()`)
- Timing instrumentation without cluttering the agent code

**Recommendation:** Keep `DealerPortalOrchestrator` as a thin coordinator but do NOT
reintroduce the `WorkflowBuilder` / `Executor` pattern unless you need multi-agent
orchestration (e.g., routing to different specialized agents based on question type).

The Agent Framework `WorkflowBuilder` is designed for multi-agent sequential pipelines
(translate → validate → publish). For a single agent with tools, direct delegation
is the correct pattern — which is what we now have.

---

## Summary

```
┌────────────────────────────────────────────────────────────────┐
│                    Agent Framework Path                          │
│                                                                  │
│  OrchestrationService                                           │
│    → DealerPortalOrchestrator (timing only)                     │
│      → DealerTechAgent (FoundryChatClient)                      │
│        → @tool search_technical_documents                       │
│          → SearchClient.search(                                 │
│              search_text, query_type, semantic_config,           │
│              top, vector_queries, filter)     ← FULL CONTROL    │
│                                                                  │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│             Foundry + MCPTool Path (DEFAULT)                     │
│                                                                  │
│  OrchestrationService                                           │
│    → DealerAgentFoundry                                         │
│      → AIProjectClient.agents.create_version()                  │
│        → MCPTool(server_label="knowledge-base")                 │
│      → openai_client.responses.create(tool_choice="required")   │
│        → KB model (gpt-4.1-mini) generates sub-queries          │
│        → KB searches index (hybrid + semantic)                  │
│        → KB reasons over results (extractiveData)               │
│        → Agent generates final grounded answer                  │
│                                                                  │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│           Foundry + AzureAISearchTool Path (fallback)            │
│                                                                  │
│  OrchestrationService                                           │
│    → DealerAgentFoundry                                         │
│      → AIProjectClient.agents.create_version()                  │
│        → AzureAISearchTool(                                     │
│            connection_id, index_name, query_type)  ← THAT'S IT  │
│      → openai_client.responses.create(tool_choice="required")   │
│        → Foundry internally: decides query, top_k, fields       │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
```
