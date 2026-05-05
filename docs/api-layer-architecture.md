# API Layer Architecture — Dev vs Prod

## 1. High-Level Architecture

```mermaid
flowchart TB
    subgraph CLIENT["Client Layer"]
        FE_DEV["Frontend (localhost:5173)"]
        FE_PROD["Frontend (dealer-portal.jayco.com)"]
    end

    subgraph PROD_GATEWAY["PROD: API Management Gateway"]
        APIM["Azure APIM\n(Developer SKU)\nRate Limit: 100 req/min\nJWT Auth via Entra ID"]
    end

    subgraph API["FastAPI Application (Port 8000)"]
        MAIN["main.py\nCORS Middleware\nHealth Endpoints"]
        
        subgraph ROUTERS["Routers"]
            CHAT["POST /api/chat\n(RAG Pipeline)"]
            SEARCH["POST /api/search\n(Hybrid Retrieval)"]
            DOCS["GET /api/documents\n(Document Listing)"]
        end

        subgraph SERVICES["Services Layer"]
            ORCH["OrchestrationService\n(Mode Router)"]
            AIS["AISearchService\n(Hybrid: Keyword + Semantic + Vector)"]
            OAI["OpenAIService\n(GPT-4o, temp=0.1)"]
        end

        subgraph AGENTS["Agent Layer"]
            AF["DealerTechAgent\n(Agent Framework)\n@tool decorator"]
            FA["DealerAgentFoundry\n(Foundry Agent Service)\nMCPTool / AzureAISearchTool"]
        end
    end

    subgraph AZURE["Azure Backend Services"]
        AISEARCH["Azure AI Search\nIndex: dealer-portal-docs\nSemantic Config"]
        OPENAI["Azure OpenAI\nGPT-5 / text-embedding-3-large"]
        BLOB["Azure Blob Storage\nContainer: dealer-portal-docs"]
        KV["Azure Key Vault"]
        APPINS["Application Insights"]
    end

    FE_DEV -->|"HTTP (no auth)"| MAIN
    FE_PROD --> APIM
    APIM -->|"Authenticated"| MAIN
    MAIN --> ROUTERS
    CHAT --> ORCH
    SEARCH --> AIS
    ORCH -->|"simulated"| AIS
    ORCH -->|"agent_framework"| AF
    ORCH -->|"foundry"| FA
    ORCH --> OAI
    AF --> AISEARCH
    FA --> AISEARCH
    AIS --> AISEARCH
    OAI --> OPENAI
    AIS -.->|"DEV: in-memory chunks"| AIS
    DOCS --> BLOB

    style CLIENT fill:#e1f5fe
    style PROD_GATEWAY fill:#fff3e0
    style API fill:#e8f5e9
    style AZURE fill:#f3e5f5
```

### Entry Points

- **Dev** → Frontend at `localhost:5173` hits the FastAPI app directly over HTTP (no auth, no gateway)
- **Prod** → Frontend at `dealer-portal.jayco.com` routes through **Azure API Management** which enforces JWT authentication (Entra ID) and rate limiting (100 req/min)

### FastAPI Application (`src/api/app/main.py`)

- Runs on port 8000 via Gunicorn with 4 Uvicorn workers
- Three main endpoints:
  - `POST /api/chat` — RAG pipeline (retrieval + generation)
  - `POST /api/search` — Direct hybrid search
  - `GET /api/documents` — Document listing/download

### Services Layer

- **OrchestrationService** — Routes requests to one of three modes based on the `AGENT_SERVICE` env var
- **AISearchService** — Performs hybrid retrieval (keyword + semantic + vector)
- **OpenAIService** — Generates grounded answers using GPT with `temperature=0.1`

### Agent Layer (Two Implementations)

- **Agent Framework** (`dealer_agent.py`) — Uses `@tool` decorator; agent autonomously decides when to search
- **Foundry Agent** (`dealer_agent_foundry.py`) — Uses MCPTool with a knowledge base or falls back to AzureAISearchTool

---

## 2. Dev vs Prod Infrastructure Comparison

```mermaid
flowchart LR
    subgraph DEV["DEV Environment"]
        direction TB
        D1["App Service: NOT DEPLOYED\n(local dev only)"]
        D2["APIM: NOT DEPLOYED\n(direct access)"]
        D3["Search: Basic SKU\n1 Replica"]
        D4["Storage: Standard_LRS\n(no geo-redundancy)"]
        D5["Network: PUBLIC\n(no isolation)"]
        D6["Mode: SIMULATED\n(in-memory data)"]
        D7["OpenAI Capacity: 30"]
        D8["Monitoring: 30-day retention"]
        D9["Key Vault: No purge protection\n7-day soft delete"]
    end

    subgraph PROD["PROD Environment"]
        direction TB
        P1["App Service: P1v3 Premium\n(auto-scale, 4 workers)"]
        P2["APIM: Developer SKU\n(rate limiting + auth)"]
        P3["Search: Standard SKU\n2 Replicas (99.95% SLA)"]
        P4["Storage: Standard_GRS\n(geo-redundant)"]
        P5["Network: VNET ISOLATED\n(private endpoints)"]
        P6["Mode: LIVE\n(Azure services)"]
        P7["OpenAI Capacity: 80"]
        P8["Monitoring: 90-day retention"]
        P9["Key Vault: Purge protection\n90-day soft delete"]
    end

    style DEV fill:#fff9c4
    style PROD fill:#c8e6c9
```

| Dimension | Dev | Prod |
|-----------|-----|------|
| **Compute** | Local only (App Service not deployed) | P1v3 Premium with auto-scale |
| **API Gateway** | None — direct access | APIM with rate limiting + JWT auth |
| **Search** | Basic SKU, 1 replica | Standard SKU, 2 replicas (HA) |
| **Data Mode** | `SIMULATED=true` — in-memory chunks | `SIMULATED=false` — live Azure AI Search |
| **Network** | Public, no isolation | VNet-integrated, private endpoints only |
| **Storage** | LRS (local redundancy) | GRS (geo-redundant) |
| **OpenAI Capacity** | 30 TPM | 80 TPM |
| **Secrets** | No purge protection, 7-day soft delete | Purge protection enabled, 90-day retention |
| **CORS** | `localhost:5173`, `localhost:3000` | `https://dealer-portal.jayco.com` |

**Key insight:** In dev, `SIMULATED_MODE=true` means the AISearchService uses 11 preloaded in-memory document chunks with keyword scoring — no Azure services needed. In prod, everything is live with managed identity auth.

---

## 3. Request Flow — Chat Endpoint (RAG Pipeline)

```mermaid
sequenceDiagram
    participant U as User/Frontend
    participant APIM as APIM (Prod Only)
    participant API as FastAPI /api/chat
    participant ORCH as OrchestrationService
    participant AIS as AISearchService
    participant SEARCH as Azure AI Search
    participant OAI as OpenAIService
    participant GPT as Azure OpenAI GPT

    U->>+APIM: POST /api/chat (Prod: JWT token)
    Note over APIM: Rate limit check (100/min)
    APIM->>+API: Forward request
    API->>+ORCH: process_chat(message, history)
    
    alt Mode: Simulated (Dev)
        ORCH->>+AIS: search(query, top_k=5)
        AIS->>AIS: In-memory keyword matching
        AIS-->>-ORCH: SearchResults[]
        ORCH->>+OAI: generate(context, question)
        OAI-->>-ORCH: Formatted response
    else Mode: Agent Framework
        ORCH->>+AIS: Agent calls @tool
        AIS->>+SEARCH: Hybrid query (semantic + vector)
        SEARCH-->>-AIS: Ranked results
        AIS-->>-ORCH: SearchResults[]
        ORCH->>+OAI: Agent generates answer
        OAI->>+GPT: Chat completion (temp=0.1)
        GPT-->>-OAI: Grounded response
        OAI-->>-ORCH: Answer + confidence
    else Mode: Foundry Agent
        ORCH->>+SEARCH: MCPTool (knowledge base)
        Note over SEARCH: Sub-query generation<br/>via gpt-4.1-mini
        SEARCH-->>-ORCH: Extractive data + refs
        ORCH->>+GPT: Stream response
        GPT-->>-ORCH: Answer with inline citations
    end
    
    ORCH-->>-API: ChatResponse
    API-->>-APIM: {answer, citations[], confidence}
    APIM-->>-U: 200 OK
```

### Mode Descriptions

1. **Simulated (Dev default):** Query → in-memory keyword search → format response from top chunk. Fast, zero-cost, offline-capable.

2. **Agent Framework:** The `DealerTechAgent` receives the query and autonomously calls its `search_technical_documents` tool against live Azure AI Search. The agent generates a grounded answer via GPT-4o.

3. **Foundry Agent (Prod default):** Creates a temporary agent in Azure AI Foundry, uses the MCPTool to query a knowledge base (which generates sub-queries via `gpt-4.1-mini`), streams the response with inline citations, then cleans up the agent.

---

## 4. API Endpoints Detail

### `POST /api/chat`

| Field | Type | Description |
|-------|------|-------------|
| `message` | string (max 2000) | User's question |
| `conversation_id` | string (optional) | For multi-turn context |
| `history` | array (optional) | Previous messages |

**Response:** `{ answer, citations[], conversation_id, confidence_score }`

### `POST /api/search`

| Field | Type | Description |
|-------|------|-------------|
| `query` | string | Search query |
| `top_k` | int (1-20, default 5) | Number of results |
| `source_filter` | string (optional) | Filter by source system |

**Response:** `{ results[], total_count }`

### `GET /api/documents`

| Param | Type | Description |
|-------|------|-------------|
| `source` | string | `"all"`, `"sharepoint"`, or `"revver"` |

**Response:** `{ documents[], total_count }`

### Health & Config Endpoints

- `GET /` — Service info (mode, version, status)
- `GET /health` — Health check
- `GET /api/config` — Max citations config

---

## 5. Deployment Configuration

### Dev (`azure.yaml`)

```yaml
name: mydealer-portal
infra:
  provider: bicep
  path: ./infra
  module: main
# No services section — manual local management
```

### Prod (`azure.yaml.prod`)

```yaml
name: mydealer-portal
infra:
  provider: bicep
  path: ./infra
  module: main
services:
  api:
    project: ./src/api
    language: python
    host: appservice
```

### Docker (`src/api/Dockerfile`)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker",
     "--bind", "0.0.0.0:8000", "app.main:app"]
```

---

## 6. Security Differences

| Layer | Dev | Prod |
|-------|-----|------|
| **Authentication** | None (Azure CLI credential) | Entra ID JWT at APIM |
| **Network** | Public access enabled | VNet + Private Endpoints |
| **TLS** | HTTP (localhost) | HTTPS enforced (TLS 1.2+) |
| **Rate Limiting** | None | APIM: 100 req/min |
| **Identity** | User principal | System-assigned Managed Identity |
| **Key Vault** | Relaxed (7-day soft delete) | Strict (purge protection + 90-day) |

---

## 7. Key Files Reference

| File | Purpose |
|------|---------|
| `src/api/app/main.py` | App entry, routes, CORS, health checks |
| `src/api/app/config.py` | Environment variable loading |
| `src/api/app/models/schemas.py` | Request/response Pydantic models |
| `src/api/app/routers/chat.py` | Chat endpoint (RAG pipeline) |
| `src/api/app/routers/search.py` | Search endpoint (hybrid retrieval) |
| `src/api/app/routers/documents.py` | Document listing/download |
| `src/api/app/services/orchestrator.py` | Mode routing (simulated/agent/foundry) |
| `src/api/app/services/ai_search.py` | Hybrid search (sim + live) |
| `src/api/app/services/openai_service.py` | LLM answer generation |
| `src/api/app/agents/dealer_agent.py` | Agent Framework implementation |
| `src/api/app/agents/dealer_agent_foundry.py` | Foundry Agent implementation |
| `src/api/app/agents/prompts.py` | Shared system prompt |
| `src/config/search_config.json` | Index schema, vectorization, agentic retrieval |
| `infra/parameters/dev.bicepparam` | Dev environment config |
| `infra/parameters/prod.bicepparam` | Prod environment config |
| `infra/modules/appservice.bicep` | App Service infrastructure |
| `infra/modules/apim.bicep` | API Management (prod gateway) |
