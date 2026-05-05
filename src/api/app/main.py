"""FastAPI application entry point."""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.config import env, env_bool
from app.routers import chat, search, documents

load_dotenv()

# Maximum citations to return per response
MAX_CITATIONS = int(os.getenv("MAX_CITATIONS", "5"))

app = FastAPI(
    title="JAYCO Dealer Portal API",
    description="AI-powered dealer support portal for JAYCO trailer documentation",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=env("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(search.router, prefix="/api", tags=["Search"])
app.include_router(documents.router, prefix="/api", tags=["Documents"])


@app.get("/", tags=["Health"])
async def root():
    return {
        "service": "JAYCO Dealer Portal API",
        "version": "1.0.0",
        "status": "healthy",
        "mode": "simulated" if env_bool("SIMULATED_MODE", True) else "live",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "environment": env("APP_ENV", "development"),
        "simulated_mode": env_bool("SIMULATED_MODE", True),
    }


@app.get("/api/config", tags=["Config"])
async def get_config():
    """Return current application configuration for the frontend."""
    return {
        "mode": "simulated" if env_bool("SIMULATED_MODE", True) else "live",
        "agent_service": env("AGENT_SERVICE", "agent_framework"),
        "agentic_retrieval_enabled": env_bool("AGENTIC_RETRIEVAL_ENABLED", False),
        "model_deployment": env("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini"),
        "kb_model": env("AZURE_OPENAI_KB_MODEL_DEPLOYMENT", "gpt-4.1-mini"),
        "search_index": env("AZURE_SEARCH_INDEX_NAME", "dealer-portal-docs"),
        "max_citations": MAX_CITATIONS,
    }
