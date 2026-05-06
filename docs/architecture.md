# Company Dealer Portal - Architecture Design

## Overview

The Company Dealer Portal is an AI-powered technical support system that enables Company trailer dealers to quickly find answers to maintenance, diagnostic, and procedural questions using natural language. The system uses a **Retrieval-Augmented Generation (RAG)** pattern to ground AI responses in authoritative Company technical documentation.

---

## Demo Architecture (Current Implementation)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          DEALER BROWSER                                   │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐     │
│  │         React + TypeScript (DynamicWeb Simulation)                │     │
│  │    ┌──────────┐   ┌──────────────┐   ┌────────────────┐         │     │
│  │    │  ChatBot  │   │ Doc Search   │   │ Document List  │         │     │
│  │    └──────────┘   └──────────────┘   └────────────────┘         │     │
│  └─────────────────────────────────────────────────────────────────┘     │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ HTTP/REST
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    FastAPI API Layer (App Service)                        │
│                                                                           │
│  ┌──────────┐   ┌──────────────┐   ┌───────────────┐                   │
│  │ /api/chat│   │ /api/search  │   │/api/documents │                   │
│  └─────┬────┘   └──────┬───────┘   └───────┬───────┘                   │
│        │                │                    │                            │
│        ▼                ▼                    ▼                            │
│  ┌─────────────────────────────────────────────────────────────┐        │
│  │              AI Orchestration Layer (RAG)                      │        │
│  │   1. Retrieve → 2. Augment Context → 3. Generate Answer      │        │
│  └────────┬─────────────────────────────────────┬───────────────┘        │
│           │                                      │                        │
│           ▼                                      ▼                        │
│  ┌──────────────────┐                  ┌─────────────────────┐          │
│  │ Azure AI Search  │                  │  Azure OpenAI gpt-4.1-mini│          │
│  │ (Simulated)      │                  │  (Simulated)         │          │
│  └──────────────────┘                  └─────────────────────┘          │
│                                                                           │
│  ┌───────────────────────────────────────────────────────────────┐      │
│  │              Simulated Source Connectors                         │      │
│  │   ┌─────────────┐   ┌────────────┐   ┌──────────────────┐    │      │
│  │   │ SharePoint  │   │   Revver   │   │   DynamicWeb     │    │      │
│  │   │ Simulator   │   │  Simulator │   │   Simulator      │    │      │
│  │   └─────────────┘   └────────────┘   └──────────────────┘    │      │
│  └───────────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     Local File System (Demo)                              │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                  data/portal_docs/ (9 PDFs)                       │   │
│   │  • Axles and Suspension - Lippert Master Manual.pdf               │   │
│   │  • Hub, Drums, & Bearings Installation Instructions.pdf           │   │
│   │  • Company Axle Torque Procedures.pdf                              │   │
│   │  • IS-System-Troubleshooting-Guide_v6-1.pdf                       │   │
│   │  • Customer Advisory (Fixed Flange Nut Substitution).pdf          │   │
│   │  • Deflection Measurement Procedure.pdf                           │   │
│   │  • Equalizer Chart Drawing.pdf                                    │   │
│   │  • Jake Plate and Shock Bushing Guide.pdf                         │   │
│   │  • GM SERVICE BULLETIN FOR BRAKE DISCONNECT.pdf                   │   │
│   └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Future Architecture (Production with Azure Services)

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                            DEALER BROWSER                                       │
│   ┌─────────────────────────────────────────────────────────────────────┐     │
│   │          DynamicWeb Portal (React + TypeScript)                       │     │
│   └─────────────────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────┬────────────────────────────────────────┘
                                       │ HTTPS
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                   Azure API Management (APIM)                                 │
│   • JWT Validation (Entra ID)                                                 │
│   • Rate Limiting (100 req/min)                                               │
│   • Request/Response Logging                                                  │
│   • AI Gateway Policies (token limits)                                        │
│   • CORS Policies                                                             │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│          Azure App Service (Linux) — FastAPI Orchestrator                      │
│                                                                                │
│   ┌────────────────────────────────────────────────────────────────┐          │
│   │                    API Endpoints                                 │          │
│   │    POST /api/chat    POST /api/search    GET /api/documents     │          │
│   └────────────────────────────────────────────────────────────────┘          │
│                                       │                                        │
│   ┌────────────────────────────────────────────────────────────────┐          │
│   │              AI Orchestration (RAG Pattern)                      │          │
│   │                                                                  │          │
│   │   ┌──────────┐    ┌──────────────┐    ┌────────────────┐       │          │
│   │   │ Retrieve │───▶│ Augment Ctx  │───▶│ Generate (LLM) │       │          │
│   │   └──────────┘    └──────────────┘    └────────────────┘       │          │
│   └────────────────────────────────────────────────────────────────┘          │
│                                                                                │
│   System-Assigned Managed Identity                                             │
└───────┬──────────────────────┬─────────────────────┬─────────────────────────┘
        │                      │                     │
        ▼                      ▼                     ▼
┌───────────────┐    ┌─────────────────┐    ┌─────────────────────┐
│Azure AI Search│    │ Azure OpenAI    │    │  Azure Blob Storage │
│               │    │                 │    │                     │
│• Hybrid Search│    │• gpt-4.1-mini         │    │• Raw PDFs           │
│• Semantic Rank│    │• text-embedding │    │• Extracted Chunks   │
│• Vector Index │    │  -3-large       │    │                     │
│               │    │                 │    │                     │
└───────────────┘    └─────────────────┘    └─────────────────────┘
        ▲                                            ▲
        │                                            │
        │            ┌─────────────────┐             │
        │            │  Azure Key Vault│             │
        │            │  + Managed ID   │             │
        │            │                 │             │
        │            │ • AOAI Keys     │             │
        │            │ • Search Keys   │             │
        │            │ • Signing Secrets│            │
        │            └─────────────────┘             │
        │                                            │
        │            ┌─────────────────────┐         │
        └────────────│  Source Connectors   │─────────┘
                     │                     │
                     │ • SharePoint (Graph) │
                     │ • Revver (REST API)  │
                     │ • DynamicWeb (CMS)   │
                     └─────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                         Observability & Security                               │
│                                                                                │
│   ┌────────────────┐    ┌───────────────────┐    ┌────────────────────┐      │
│   │ App Insights   │    │ Log Analytics     │    │   Entra ID         │      │
│   │                │    │ Workspace         │    │                    │      │
│   │ • API Latency  │    │ • Audit Logs      │    │ • OAuth2/OIDC      │      │
│   │ • Error Rates  │    │ • Search Queries  │    │ • RBAC             │      │
│   │ • Request Trace│    │ • AI Usage        │    │ • Managed Identity │      │
│   └────────────────┘    └───────────────────┘    └────────────────────┘      │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Azure Service Mapping

| Component | Demo Version | Future (Production) Version |
|-----------|-------------|---------------------------|
| **Frontend** | React + TypeScript (localhost) | React on Azure Static Web Apps / DynamicWeb |
| **API Gateway** | FastAPI direct | Azure API Management (APIM) |
| **API Layer** | FastAPI on localhost | FastAPI on Azure App Service (Linux) |
| **AI Search** | Simulated in-memory search | Azure AI Search (hybrid: keyword + semantic + vector) |
| **LLM** | Simulated response generation | Azure OpenAI gpt-4.1-mini |
| **Embeddings** | N/A (demo uses keyword) | Azure OpenAI text-embedding-3-large |
| **Document Storage** | Local filesystem (`data/portal_docs/`) | Azure Blob Storage |
| **Secrets** | `.env` file | Azure Key Vault + Managed Identity |
| **Auth** | None (demo) | Microsoft Entra ID (JWT validation) |
| **Logging** | Console | Application Insights + Log Analytics |
| **Source: SharePoint** | Simulated connector (local files) | Microsoft Graph API |
| **Source: Revver** | Simulated connector (local files) | Revver REST API |
| **Source: DynamicWeb** | React frontend simulation | DynamicWeb CMS integration |

---

## Data Flow: Chat Request

```
1. Dealer types question → React Frontend
2. Frontend sends POST /api/chat → FastAPI (or APIM → FastAPI)
3. FastAPI Orchestrator (AGENT_SERVICE=foundry):
   a. Creates/reuses a Foundry Agent with MCPTool (agentic retrieval)
   b. Agent autonomously uses Knowledge Base:
      - KB model (gpt-4.1-mini) generates sub-queries
      - Searches AI Search index (hybrid: keyword + semantic + vector)
      - Returns grounded context with citations
   c. Agent model (gpt-4.1-mini) generates final answer
   d. Orchestrator extracts citations (max 5, deduplicated)
4. Response returned to Frontend
5. Frontend renders answer with source citations and document references
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | Chat with AI agent (returns answer + citations) |
| `/api/search` | POST | Hybrid document search (keyword + vector + semantic reranker) |
| `/api/documents` | GET | List available documents |
| `/api/documents/{name}` | GET | Download/view a specific PDF document |
| `/api/config` | GET | Current app config (mode, model, agent, retrieval settings) |
| `/health` | GET | Health check |
| `/docs` | GET | OpenAPI documentation |

---

## Document Sources & Mapping

| Document | Source System | Primary Topics |
|----------|--------------|----------------|
| Axles and Suspension - Lippert Master Manual.pdf | SharePoint | Axle alignment, suspension maintenance, tire wear diagnosis |
| Hub, Drums, & Bearings Installation Instructions.pdf | Revver | Bearing repack, hub installation, temperature diagnosis |
| Company Axle Torque Procedures.pdf | SharePoint | Torque specifications, U-bolt procedures |
| IS-System-Troubleshooting-Guide_v6-1.pdf | Revver | IS system troubleshooting, handling issues |
| Customer Advisory (Fixed Flange Nut Substitution) - 06-02-23.pdf | SharePoint | Safety advisory, nut replacement |
| Deflection Measurement Procedure.pdf | SharePoint | Spring deflection, load measurement |
| Equalizer Chart Drawing.pdf | SharePoint | Beam assembly identification (7K vs 8K) |
| Jake Plate and Shock Bushing Guide.pdf | Revver | Jake plate installation, bushing replacement |
| GM SERVICE BULLETIN FOR BRAKE DISCONNECT.pdf | Revver | Brake disconnect safety procedure |

---

## API Endpoints

### Demo Version (FastAPI Direct)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat` | RAG-based chat with citations |
| POST | `/api/search` | Hybrid document search |
| GET | `/api/documents` | List available documents |
| GET | `/health` | Service health check |
| GET | `/docs` | OpenAPI/Swagger UI |

### Future Version (via APIM)

| Method | APIM Path | Backend | Policy |
|--------|-----------|---------|--------|
| POST | `/dealer/api/chat` | App Service | JWT + Rate Limit (100/min) |
| POST | `/dealer/api/search` | App Service | JWT + Rate Limit |
| GET | `/dealer/api/documents` | App Service | JWT + Rate Limit |

---

## Security Design

### Demo
- CORS restricted to `localhost:5173`
- No authentication (demo mode)
- Secrets in `.env` file (gitignored)

### Production
- **Authentication**: Microsoft Entra ID (OAuth2/OIDC) via APIM JWT validation
- **Authorization**: Role-based (dealer, admin, readonly)
- **Secrets**: Azure Key Vault with Managed Identity (no keys in code/config)
- **Network**: APIM as sole public entry point; App Service restricted to APIM traffic
- **Data**: TLS 1.2+ in transit; encrypted at rest (Azure Storage, AI Search)
- **Rate Limiting**: 100 requests/minute per subscription via APIM policy

---

## Operational Excellence

### Monitoring
- **Application Insights**: API latency, error rates, dependency tracking
- **Log Analytics**: Centralized logs, KQL queries for diagnostics
- **APIM Analytics**: API usage patterns, throttling metrics
- **Custom Metrics**: RAG confidence scores, citation hit rates, search relevance

### Alerting
- P95 latency > 5s → Alert
- Error rate > 5% → Alert
- Token usage > 80% quota → Alert
- Failed auth attempts > threshold → Security alert
