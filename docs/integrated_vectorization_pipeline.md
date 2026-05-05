# Integrated Vectorization Pipeline

## Overview

The integrated vectorization pipeline delegates document extraction, chunking, and embedding entirely to Azure AI Search's indexer + skillset infrastructure. Instead of manually processing PDFs and uploading documents, the pipeline watches a blob container and automatically processes new/changed documents.

```
Azure Blob Storage ──► Indexer ──► Skillset ──► Index
                                      │
                         ┌─────────────┼─────────────┐
                         ▼             ▼             ▼
              DocumentIntelligence  SplitSkill  EmbeddingSkill
              LayoutSkill           (chunking)  (vectorization)
```

## Why Consider It for Production

| Benefit | Description |
|---------|-------------|
| **Automatic re-indexing** | When blobs are added/modified/deleted, the indexer detects changes and reprocesses only affected documents |
| **No manual embedding generation** | AzureOpenAIEmbeddingSkill handles vectorization server-side — no OpenAI API calls from your code |
| **No rate-limit management** | Azure Search handles retry/throttling for embedding calls internally |
| **Consistent chunking** | ContentUnderstandingSkill provides document-aware chunking with layout preservation |
| **Index projections** | Parent-child document relationships are maintained automatically via `includeIndexingParentDocuments` mode |
| **Scheduled runs** | Indexer can run on a schedule (e.g., every 5 minutes) for near-real-time updates |

## Current Approach (Document Intelligence + Manual Upload)

The current `document_intelligence` extraction mode:

1. Reads PDFs from a local directory
2. Calls Azure Document Intelligence (prebuilt-layout) for text extraction
3. Chunks text with configurable size/overlap
4. Generates embeddings via Azure OpenAI API (with retry logic)
5. Uploads batches to the search index

This works well for development and one-time bulk indexing but requires manual re-runs when documents change.

## Relationship to Agentic Retrieval

**Integrated vectorization and agentic retrieval are orthogonal.**

```
┌─────────────────────────────────────────────────────┐
│  HOW documents get into the index (indexing layer)  │
│                                                     │
│  Option A: document_intelligence (manual)           │
│  Option B: integrated_vectorization (automatic)     │
└──────────────────────────┬──────────────────────────┘
                           │
                    populated index
                           │
┌──────────────────────────▼──────────────────────────┐
│  HOW the agent retrieves from the index (query layer)│
│                                                     │
│  Option A: AzureAISearchTool (agent makes N calls)  │
│  Option B: MCPTool + Agentic Retrieval (1 call,     │
│            server-side query planning + synthesis)   │
└─────────────────────────────────────────────────────┘
```

- **Agentic retrieval** works with any populated index regardless of how it was indexed
- The knowledge source references index **field names**, not how those fields were populated
- You can switch indexing methods without changing the agentic retrieval configuration
- Both indexing methods produce the same index schema (`content`, `content_vector`, `document_name`, etc.)

## When to Migrate

Consider switching to integrated vectorization when:

- Documents are uploaded to blob storage by external systems (SharePoint sync, Revver export)
- You need automatic incremental updates without manual re-indexing
- You want to eliminate the embedding generation cost/complexity from your application code
- You're moving to production and need a hands-off document pipeline

You do **not** need integrated vectorization to use agentic retrieval. The `--provision-agentic` flag works with either indexing method.

## Usage

```bash
# Current: manual indexing (development)
python -m indexer.index_documents --extraction-type document_intelligence --dir ./data/portal_docs

# Production: integrated vectorization (requires blobs in Azure Storage)
python -m indexer.index_documents --extraction-type integrated_vectorization

# Agentic retrieval (works with either indexing method)
python -m indexer.index_documents --provision-agentic
```
