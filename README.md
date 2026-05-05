# Company Dealer Portal — AI-Powered Technical Support

> **Proof of Concept** — An AI-powered dealer support chatbot that answers technical questions about Company trailer maintenance using Retrieval-Augmented Generation (RAG) grounded in 9 authoritative service documents.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Repository Structure](#repository-structure)
- [Azure Services](#azure-services)
- [Quick Start (Demo Mode)](#quick-start-demo-mode)
- [Sample Queries](#sample-queries)
- [Demo vs Future Architecture](#demo-vs-future-architecture)
- [Infrastructure Deployment](#infrastructure-deployment)
- [Document Indexing](#document-indexing)
- [API Reference](#api-reference)
- [Testing](#testing)
- [Configuration](#configuration)

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

## Quick Start (Demo Mode)

### Prerequisites

- Python 3.11+
- Node.js 20+
- npm 10+

### 1. Setup

```bash
# Clone and enter the repo
cd dealer-portal-exp

# Run setup script (creates venv, installs deps)
chmod +x scripts/setup.sh
./scripts/setup.sh
```

### 2. Start the Application

The easiest way to launch both backend and frontend together:

```bash
./start.sh
```

This starts:
- **Backend** (FastAPI) on http://localhost:8000
- **Frontend** (React/Vite) on http://localhost:5173

Logs are written to `logs/backend.log` and `logs/frontend.log`.

To stop both services:

```bash
./stop.sh
```

#### Manual Start (Alternative)

**Backend:**
```bash
cd src/api
source ../../.venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend** (separate terminal):
```bash
cd src/frontend
npm run dev
```

The API will be available at:
- **Swagger UI**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Frontend**: http://localhost:5173

### 3. Try It Out

The demo runs in **simulated mode** — no Azure credentials needed. The chatbot uses pre-indexed document chunks to demonstrate the RAG pattern with realistic responses.

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

## Infrastructure Deployment

### Deploy Demo (No APIM)

```bash
# Login to Azure
az login

# Deploy infrastructure (dev - no APIM)
az deployment group create \
  --resource-group rg-company-dealer-dev \
  --template-file infra/main.bicep \
  --parameters infra/parameters/dev.bicepparam
```

### Deploy Production (With APIM)

```bash
# Deploy infrastructure (prod - with APIM)
az deployment group create \
  --resource-group rg-company-dealer-prod \
  --template-file infra/main.bicep \
  --parameters infra/parameters/prod.bicepparam
```

### Deploy App Code

```bash
# Deploy FastAPI to App Service
az webapp up \
  --name app-company-dealer-dev \
  --resource-group rg-company-dealer-dev \
  --runtime "PYTHON:3.11" \
  --src-path src/api
```

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

## Configuration

All configuration is via environment variables (see `.env.example`):

| Variable | Description | Demo Default |
|----------|-------------|--------------|
| `SIMULATED_MODE` | Use simulated backends | `true` |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint | (not needed in demo) |
| `AZURE_OPENAI_DEPLOYMENT` | Model deployment name | `gpt-4o` |
| `AZURE_SEARCH_ENDPOINT` | Azure AI Search endpoint | (not needed in demo) |
| `AZURE_SEARCH_INDEX_NAME` | Search index name | `company-dealer-docs` |
| `CORS_ORIGINS` | Allowed CORS origins | `http://localhost:5173` |

---

## License

Internal use — Microsoft / Company engagement.
