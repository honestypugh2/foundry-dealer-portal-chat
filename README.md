# Company Dealer Portal — AI-Powered Technical Support

> **Proof of Concept** — An AI-powered dealer support chatbot that answers technical questions about Company trailer maintenance using Retrieval-Augmented Generation (RAG) grounded in 9 authoritative service documents. The default agent uses **Azure AI Foundry Agent Service** with agentic retrieval.

⚠️ **CAUTION: Development Use Only**

> **This codebase is intended for development and proof-of-concept purposes only. It is NOT production-ready.**
>
> This project does not implement the security hardening, reliability patterns, networking isolation, or operational controls required for production workloads. Before deploying to production, follow the [Microsoft Azure Well-Architected Framework (WAF)](https://learn.microsoft.com/azure/well-architected/) guidance — including the Security, Reliability, Performance Efficiency, Cost Optimization, and Operational Excellence pillars.
>
> Key gaps include (but are not limited to):
> - Network isolation (Private Endpoints, VNet integration)
> - Managed identity everywhere (no API keys in environment variables)
> - Threat protection and input validation hardening
> - Disaster recovery and high availability
> - Load testing and performance benchmarking
> - Production-grade monitoring, alerting, and incident response

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [Infrastructure Deployment (azd)](#infrastructure-deployment-azd)
- [Architecture Overview](#architecture-overview)
- [Repository Structure](#repository-structure)
- [Azure Services](#azure-services)
- [Demo Mode (No Azure Required)](#demo-mode-no-azure-required)
- [Sample Queries](#sample-queries)
- [Demo vs Future Architecture](#demo-vs-future-architecture)
- [Document Indexing](#document-indexing)
- [API Reference](#api-reference)
- [Testing](#testing)

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | FastAPI backend + indexer |
| Node.js | 20+ | React frontend (Vite dev server) |
| npm | 10+ | Frontend dependency management |
| Azure CLI | 2.60+ | Authentication and resource management |
| Azure Developer CLI (`azd`) | latest | Infrastructure provisioning and deployment |
| Docker | 24+ | (Optional) Container builds for App Service |

**Azure Subscription Requirements:**

- An active Azure subscription with Owner or Contributor + User Access Administrator roles
- Azure AI Foundry project (with AI Services endpoint)
- Azure OpenAI model deployments (`gpt-4.1-mini` for chat, `text-embedding-3-large` for embeddings)
- Azure AI Search service (Basic SKU or higher)
- Azure Blob Storage account (for document source)

**Required RBAC Roles** (on your AI Services resource):

| Role | Purpose |
|------|---------|
| Cognitive Services OpenAI User | Model inference |
| Search Index Data Reader | Querying the search index |
| Search Service Contributor | Managing agentic retrieval knowledge base |

---

## Quick Start

The fastest path to running locally with Azure AI Foundry Agent Service:

### 1. Provision Infrastructure

```bash
az login
azd auth login
azd init
azd up
```

This deploys all required Azure resources (AI Search, OpenAI, Storage, Key Vault, Monitoring) using the Bicep templates in `infra/`.

### 2. Install Dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r src/api/requirements.txt
pip install -r src/indexer/requirements.txt

cd src/frontend && npm install && cd ../..
```

### 3. Configure Environment

Create a `.env` file in the repo root (gitignored):

```bash
# Core mode settings
SIMULATED_MODE=false
AGENT_SERVICE=foundry
AGENTIC_RETRIEVAL_ENABLED=true

# Azure AI Foundry
AZURE_AI_PROJECT_ENDPOINT=https://<your-ai-services>.services.ai.azure.com/api/projects/<your-project>

# Azure OpenAI
AZURE_OPENAI_DEPLOYMENT=gpt-4.1-mini
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large

# Azure AI Search
AZURE_SEARCH_ENDPOINT=https://<your-search>.search.windows.net
AZURE_SEARCH_INDEX_NAME=dealer-portal-docs
AZURE_SEARCH_API_KEY=<your-search-admin-key>

# Agent persistence (avoids re-creation cost between requests)
PERSIST_FOUNDRY_AGENTS=true
```

### 4. Index Documents & Start

```bash
# Index documents into Azure AI Search
source .venv/bin/activate
cd src && python -m indexer.index_documents && cd ..

# Start both backend and frontend
./start.sh
```

The app is now available at:
- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8000
- **Swagger UI:** http://localhost:8000/docs

For the full local development workflow (manual start, debugging, testing), see the [Development Guide](docs/development-guide.md).

---

## Environment Variables

All configuration is managed via environment variables (loaded from `.env`). The defaults below are configured for **Foundry Agent** mode:

| Variable | Description | Default |
|----------|-------------|---------|
| `SIMULATED_MODE` | Use simulated backends (no Azure needed) | `false` |
| `AGENT_SERVICE` | Agent implementation: `foundry` or `agent_framework` | `foundry` |
| `AGENTIC_RETRIEVAL_ENABLED` | Enable knowledge base + MCP agentic retrieval | `true` |
| `AZURE_AI_PROJECT_ENDPOINT` | Azure AI Foundry project endpoint | *(required)* |
| `AZURE_OPENAI_DEPLOYMENT` | Chat model deployment name | `gpt-4.1-mini` |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | Embedding model deployment | `text-embedding-3-large` |
| `AZURE_OPENAI_KB_MODEL_DEPLOYMENT` | Knowledge base reasoning model | `gpt-4.1-mini` |
| `AZURE_SEARCH_ENDPOINT` | Azure AI Search service endpoint | *(required)* |
| `AZURE_SEARCH_INDEX_NAME` | Search index name | `dealer-portal-docs` |
| `AZURE_SEARCH_API_KEY` | Search admin key (or use managed identity) | *(required)* |
| `AI_SEARCH_PROJECT_CONNECTION_ID` | Foundry project connection ID for search | *(auto-detected)* |
| `AI_SEARCH_QUERY_TYPE` | Query type: `simple`, `semantic` | `semantic` |
| `MCP_PROJECT_CONNECTION_NAME` | MCP connection for agentic retrieval | `dealer-knowledge-mcp-connection` |
| `PERSIST_FOUNDRY_AGENTS` | Reuse agents across requests | `true` |
| `MAX_CITATIONS` | Max citations returned per response | `5` |
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) | `http://localhost:5173` |
| `APP_ENV` | Environment label | `development` |

> **Simulated mode:** Set `SIMULATED_MODE=true` to run without any Azure credentials. The chatbot uses pre-indexed chunks and simulated responses for demonstration purposes.

---

## Infrastructure Deployment (azd)

The project uses [Azure Developer CLI (`azd`)](https://learn.microsoft.com/azure/developer/azure-developer-cli/) with Bicep templates for infrastructure-as-code.

### First-Time Setup

```bash
# Install azd (if not already installed)
curl -fsSL https://aka.ms/install-azd.sh | bash

# Login
az login
azd auth login

# Initialize the project (uses azure.yaml)
azd init

# Provision infrastructure + deploy app
azd up
```

### Deploy Dev Environment (No APIM)

```bash
azd up --environment dev
```

This uses `infra/parameters/dev.bicepparam` which deploys:
- Azure AI Search (Basic SKU)
- Azure OpenAI (gpt-4.1-mini + text-embedding-3-large)
- Azure Blob Storage
- Azure Key Vault
- Application Insights + Log Analytics

### Deploy Production (With APIM)

```bash
azd up --environment prod
```

Uses `infra/parameters/prod.bicepparam` with additional:
- Azure API Management (AI Gateway policies, JWT validation, rate limiting)
- Higher SKU tiers and replica counts

### Manual Bicep Deployment (Alternative)

```bash
# Dev
az deployment group create \
  --resource-group rg-company-dealer-dev \
  --template-file infra/main.bicep \
  --parameters infra/parameters/dev.bicepparam

# Prod
az deployment group create \
  --resource-group rg-company-dealer-prod \
  --template-file infra/main.bicep \
  --parameters infra/parameters/prod.bicepparam
```

### Deploy App Code to App Service

```bash
az webapp up \
  --name app-company-dealer-dev \
  --resource-group rg-company-dealer-dev \
  --runtime "PYTHON:3.11" \
  --src-path src/api
```

---

## Architecture Overview

### Demo Architecture (Simulated Backends)

```
Frontend (DynamicWeb Simulation - React/TS)
        ↓
FastAPI API Layer (App Service equivalent)
        ↓
AI Orchestration Layer (RAG Pattern)
        ↓
┌────────────┬───────────┬──────────────┐
│ SharePoint │  Revver   │  AI Index    │
│ (Simulated)│(Simulated)│ (Simulated)  │
└────────────┴───────────┴──────────────┘
```

### Future Architecture (Azure Services)

```
DynamicWeb Portal (React/TS)
        ↓
Azure API Management (APIM)
  • JWT validation • Rate limiting • AI Gateway policies
        ↓
Azure App Service (FastAPI Orchestrator)
  • /api/chat  • /api/search  • /api/documents
        ↓
┌───────────────┬──────────────────┬─────────────────┐
│ Azure AI      │ Azure OpenAI     │ Azure Blob      │
│ Search        │ (GPT-4o +        │ Storage         │
│ (Hybrid)      │  Embeddings)     │ (PDFs + Chunks) │
└───────────────┴──────────────────┴─────────────────┘
        +
┌──────────────────────────────────────────────────────┐
│ Key Vault • Entra ID • App Insights • Log Analytics  │
└──────────────────────────────────────────────────────┘
```

For the full architecture diagrams and details, see [docs/architecture.md](docs/architecture.md).

For the local development guide (running the React app + API with real Azure), see [docs/development-guide.md](docs/development-guide.md).

---

## Repository Structure

```
dealer-portal-exp/
├── README.md                          # This file
├── .env.example                       # Environment variable template
├── .gitignore
│
├── data/
│   └── portal_docs/                   # 9 Company source PDFs
│       ├── Axles and Suspension - Lippert Master Manual.pdf
│       ├── Customer Advisory (Fixed Flange Nut Substitution) - 06-02-23.pdf
│       ├── Deflection Measurement Procedure.pdf
│       ├── Equalizer Chart Drawing.pdf
│       ├── GM SERVICE BULLETIN FOR BRAKE DISCONNECT.pdf
│       ├── Hub, Drums, & Bearings Installation Instructions.pdf
│       ├── IS-System-Troubleshooting-Guide_v6-1.pdf
│       ├── Jake Plate and Shock Bushing Guide.pdf
│       └── Jayco Axle Torque Procedures.pdf
│
├── docs/
│   └── architecture.md                # Full architecture design document
│
├── infra/                             # Azure Bicep IaC templates
│   ├── main.bicep                     # Main orchestration template
│   ├── modules/
│   │   ├── apim.bicep                 # API Management (Future)
│   │   ├── appservice.bicep           # App Service (FastAPI host)
│   │   ├── keyvault.bicep             # Key Vault + diagnostics
│   │   ├── monitoring.bicep           # Log Analytics + App Insights
│   │   ├── openai.bicep               # Azure OpenAI (GPT-4o + embeddings)
│   │   ├── search.bicep               # Azure AI Search
│   │   └── storage.bicep              # Blob Storage
│   └── parameters/
│       ├── dev.bicepparam             # Dev parameters (no APIM)
│       └── prod.bicepparam            # Prod parameters (with APIM)
│
├── src/
│   ├── api/                           # FastAPI Backend (Demo + Future)
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── main.py                # FastAPI app entry point
│   │       ├── config.py              # Settings (pydantic-settings)
│   │       ├── models/
│   │       │   └── __init__.py        # Pydantic request/response schemas
│   │       ├── routers/
│   │       │   ├── chat.py            # POST /api/chat
│   │       │   ├── search.py          # POST /api/search
│   │       │   └── documents.py       # GET /api/documents
│   │       ├── services/
│   │       │   ├── ai_search.py       # Azure AI Search (+ simulated)
│   │       │   ├── openai_service.py  # Azure OpenAI GPT-4o (+ simulated)
│   │       │   └── orchestrator.py    # RAG orchestration pipeline
│   │       └── connectors/
│   │           ├── sharepoint_sim.py  # Simulated SharePoint connector
│   │           └── revver_sim.py      # Simulated Revver connector
│   │
│   ├── frontend/                      # React + TypeScript (DynamicWeb sim)
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   ├── vite.config.ts
│   │   ├── index.html
│   │   ├── public/
│   │   └── src/
│   │       ├── main.tsx
│   │       ├── App.tsx
│   │       ├── types/index.ts         # TypeScript interfaces
│   │       ├── services/api.ts        # API client
│   │       ├── styles/globals.css     # Company-branded styling
│   │       └── components/
│   │           ├── Layout.tsx          # App shell + navigation
│   │           ├── ChatBot.tsx         # Chat interface
│   │           ├── ChatMessage.tsx     # Message bubble + citations
│   │           ├── DocumentList.tsx    # Document library view
│   │           └── SearchPanel.tsx     # Document search view
│   │
│   └── indexer/                       # Document indexing pipeline
│       ├── index_documents.py         # PDF → chunks → AI Search index
│       └── requirements.txt
│
├── scripts/
│   ├── setup.sh                       # Local dev environment setup
│   └── deploy.sh                      # Azure deployment script
│
└── tests/
    ├── test_chat.py                   # Chat endpoint tests
    └── test_search.py                 # Search + documents tests
```

---

## Azure Services

| Component | Azure Service | Purpose |
|-----------|---------------|---------|
| API Gateway | **Azure API Management** | Public entry, JWT auth, rate limiting, AI Gateway policies |
| API Layer | **Azure App Service** (Linux) | Hosts FastAPI orchestrator |
| AI Search | **Azure AI Search** | Hybrid retrieval (keyword + semantic + vector) |
| LLM | **Azure OpenAI** (GPT-4o) | Grounded answer generation |
| Embeddings | **Azure OpenAI** (text-embedding-3-large) | Document vectorization |
| Storage | **Azure Blob Storage** | Raw PDFs + extracted chunks |
| Secrets | **Azure Key Vault** | API keys, secrets (Managed Identity) |
| Auth | **Microsoft Entra ID** | OAuth2/OIDC, RBAC |
| Monitoring | **Application Insights** | API latency, errors, traces |
| Logging | **Log Analytics Workspace** | Centralized audit + diagnostic logs |

---

## Demo Mode (No Azure Required)

To run without Azure credentials, set `SIMULATED_MODE=true` in `.env`. The chatbot uses pre-indexed document chunks and simulated responses to demonstrate the RAG pattern. See the [Development Guide](docs/development-guide.md) for details.

---

## Sample Queries

These queries demonstrate the chatbot's capabilities across the 9 source documents:

| Query | Expected Source Document |
|-------|-------------------------|
| My trailer has excessive tire wear—what could be causing this and how do I fix it? | Axles and Suspension - Lippert Master Manual |
| I'm noticing high hub temperature and unusual noise from the wheel—what could be wrong? | Hub, Drums, & Bearings Installation Instructions |
| How do I repack the bearings step by step? | Hub, Drums, & Bearings Installation Instructions |
| What maintenance should I regularly perform on the suspension system? | Axles and Suspension - Lippert Master Manual |
| How do I identify whether I have a 7K or 8K beam assembly? | Equalizer Chart Drawing |
| What are the torque specs for U-bolt nuts? | Jayco Axle Torque Procedures |
| What is the customer advisory about flange nut substitution? | Customer Advisory (Fixed Flange Nut Substitution) |
| How do I install a Jake plate? | Jake Plate and Shock Bushing Guide |
| What's the procedure for brake disconnect during service? | GM SERVICE BULLETIN FOR BRAKE DISCONNECT |

---

## Demo vs Future Architecture

### Version 1: Demo (FastAPI Direct)

| Feature | Implementation |
|---------|---------------|
| Entry Point | FastAPI direct (port 8000) |
| Authentication | None |
| Search | Simulated keyword matching (in-memory) |
| LLM | Simulated response from pre-built chunks |
| Source Systems | Local file system connectors |
| Deployment | `uvicorn` local |

### Version 2: Future (APIM + Full Azure)

| Feature | Implementation |
|---------|---------------|
| Entry Point | Azure APIM → App Service |
| Authentication | Entra ID JWT validation |
| Search | Azure AI Search (hybrid + semantic + vector) |
| LLM | Azure OpenAI GPT-4o (grounded generation) |
| Source Systems | Microsoft Graph (SharePoint) + Revver API |
| Deployment | Bicep IaC → `az deployment group create` |

To switch from Demo to Future mode:
1. Set `SIMULATED_MODE=false` in `.env`
2. Provide Azure credentials (or use Managed Identity)
3. Run the document indexer: `python src/indexer/index_documents.py`
4. Deploy APIM: set `deployApim=true` in Bicep parameters

---

## Document Indexing

To index documents into Azure AI Search (requires Azure credentials):

```bash
cd src/indexer
pip install -r requirements.txt

# Index all documents
python index_documents.py ../../data/portal_docs SharePoint
```

This will:
1. Create the search index with vector + semantic configuration
2. Extract text from each PDF (chunked by page, ~400 words per chunk)
3. Generate embeddings using `text-embedding-3-large`
4. Upload documents to Azure AI Search

---

## API Reference

### POST /api/chat

Send a question and receive a grounded answer with citations.

**Request:**
```json
{
  "message": "How do I repack the bearings step by step?",
  "conversation_id": "optional-uuid",
  "history": []
}
```

**Response:**
```json
{
  "answer": "Based on the Company technical documentation...",
  "citations": [
    {
      "document_name": "Hub, Drums, & Bearings Installation Instructions.pdf",
      "page_number": 3,
      "chunk_text": "Bearing Repack Procedure...",
      "relevance_score": 0.95,
      "source_system": "Revver"
    }
  ],
  "conversation_id": "uuid",
  "confidence_score": 0.87
}
```

### POST /api/search

Search documents directly.

**Request:**
```json
{
  "query": "torque specifications",
  "top_k": 5,
  "source_filter": "SharePoint"
}
```

### GET /api/documents

List all available documents.

**Query Parameters:** `source` = `all` | `sharepoint` | `revver`

---

## Testing

```bash
# From repo root
cd src/api && source .venv/bin/activate && cd ../..

# Run all tests
python -m pytest tests/ -v

# Run specific test
python -m pytest tests/test_chat.py -v
```

---

## License

Internal use — Microsoft / Company engagement.
