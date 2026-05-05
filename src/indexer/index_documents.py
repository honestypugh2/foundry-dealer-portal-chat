"""Document Indexer - JAYCO Dealer Portal

Extracts text from PDFs and indexes into Azure AI Search.

Supports two extraction modes (set EXTRACTION_TYPE env var):
1. "document_intelligence" (default) - Azure Document Intelligence + manual chunking + embedding
2. "integrated_vectorization" - Azure AI Search indexer + skillset pipeline

For document_intelligence mode:
    - Uses Azure Document Intelligence (prebuilt-layout) with PyPDF2 fallback
    - Chunks with configurable size/overlap
    - Generates embeddings via Azure OpenAI
    - Uploads to Azure AI Search index

For integrated_vectorization mode:
    - Creates blob data source, skillset, and indexer
    - DocumentIntelligenceLayoutSkill → SplitSkill → EmbeddingSkill
    - Azure AI Search handles the full pipeline automatically
"""

import hashlib
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Extraction type: "document_intelligence" or "integrated_vectorization"
EXTRACTION_TYPE = os.getenv("EXTRACTION_TYPE", "document_intelligence")


def generate_parent_id(file_path: str) -> str:
    """Generate a deterministic parent document ID from file path."""
    return hashlib.md5(file_path.encode()).hexdigest()


def index_with_document_intelligence(docs_path: str, source_system: str = "SharePoint"):
    """
    Index documents using Azure Document Intelligence (default) with PyPDF2 fallback.
    Includes chunking with overlap and embedding generation.
    """
    from indexer.document_ingestion import DocumentIngestionService
    from indexer.chunking import chunk_document_pages, chunk_full_text
    from indexer.azure_ai_search_client import AzureAISearchClient

    # Initialize services
    use_azure_di = os.getenv("USE_AZURE_DOCUMENT_INTELLIGENCE", "true").lower() == "true"
    ingestion_service = DocumentIngestionService(use_azure=use_azure_di)
    search_client = AzureAISearchClient()

    # Chunking config (from search_config.json integrated_vectorization.chunking)
    chunk_size = int(os.getenv("CHUNK_SIZE", "2000"))
    chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "200"))
    chunk_cross_page = os.getenv("CHUNK_CROSS_PAGE", "false").lower() == "true"

    # Create the search index
    search_client.create_index()

    # Process documents
    docs_dir = Path(docs_path)
    all_documents = []

    pdf_files = sorted(docs_dir.glob("*.pdf"))
    if not pdf_files:
        logger.warning(f"No PDF files found in {docs_path}")
        return

    logger.info(f"Processing {len(pdf_files)} PDF files with extraction_type=document_intelligence")

    for pdf_file in pdf_files:
        logger.info(f"Processing: {pdf_file.name}")

        # Generate parent document ID
        parent_id = generate_parent_id(str(pdf_file))

        # Extract text using Document Intelligence (with PyPDF2 fallback)
        extraction_result = ingestion_service.process_document(str(pdf_file))
        logger.info(
            f"  Extracted {extraction_result['page_count']} pages, "
            f"{extraction_result['word_count']} words "
            f"(method: {extraction_result['extraction_method']})"
        )

        # Chunk with overlap
        if extraction_result.get("pages"):
            chunks = chunk_document_pages(
                pages=extraction_result["pages"],
                size=chunk_size,
                overlap=chunk_overlap,
                document_id=parent_id,
                cross_page=chunk_cross_page,
            )
        else:
            chunks = chunk_full_text(
                text=extraction_result["text"],
                size=chunk_size,
                overlap=chunk_overlap,
                document_id=parent_id,
            )

        logger.info(f"  Chunked into {len(chunks)} chunks (size={chunk_size}, overlap={chunk_overlap})")

        # Generate embeddings and build index documents
        for chunk in chunks:
            embedding = search_client.generate_embedding(chunk.text)

            # Build content_with_source field
            content_with_source = f"[{pdf_file.name}] {chunk.text}"

            document = {
                "id": chunk.chunk_id,
                "content": chunk.text,
                "content_with_source": content_with_source,
                "content_vector": embedding,
                "document_name": pdf_file.name,
                "page_number": chunk.page_number,
                "source_system": source_system,
                "chunk_index": chunk.chunk_index,
                "chunk_parent_id": parent_id,
                "metadata_storage_name": pdf_file.name,
                "metadata_storage_path": str(pdf_file),
                "blob_url": "",  # Updated after blob upload
            }
            all_documents.append(document)

    # Upload to Azure AI Search
    if all_documents:
        succeeded = search_client.upload_documents(all_documents)
        logger.info(f"Indexing complete: {succeeded}/{len(all_documents)} documents uploaded")
    else:
        logger.warning("No documents to upload")


def index_with_integrated_vectorization():
    """
    Index documents using Azure AI Search Integrated Vectorization.
    Creates the indexer + skillset pipeline that handles extraction,
    chunking, and embedding automatically.

    Prerequisites:
    - Documents must already be uploaded to Azure Blob Storage
      (use scripts/upload_to_blob.py)
    """
    from indexer.azure_ai_search_client import AzureAISearchClient

    search_client = AzureAISearchClient()

    # Create the search index
    logger.info("Creating search index...")
    if not search_client.create_index():
        logger.error("Failed to create index. Aborting.")
        return

    # Create integrated vectorization pipeline (data source + skillset + indexer)
    logger.info("Creating integrated vectorization pipeline...")
    if not search_client.create_integrated_vectorization_pipeline():
        logger.error("Failed to create integrated vectorization pipeline. Aborting.")
        return

    # Trigger the indexer
    logger.info("Triggering indexer...")
    if search_client.run_indexer():
        logger.info("Integrated vectorization pipeline created and indexer triggered successfully.")
    else:
        logger.error("Failed to trigger indexer.")


def provision_agentic_retrieval():
    """
    Provision agentic retrieval pipeline: knowledge source, knowledge base,
    and MCP project connection.

    This enables the Foundry Agent to use MCPTool instead of AzureAISearchTool,
    giving the search service control over query planning and result synthesis.

    Prerequisites:
    - Search index must already exist and be populated
    - AGENTIC_RETRIEVAL_ENABLED=true in .env
    - AZURE_AI_PROJECT_RESOURCE_ID set for project connection creation
    """
    from indexer.azure_ai_search_client import AzureAISearchClient, AGENTIC_RETRIEVAL_AVAILABLE

    if not AGENTIC_RETRIEVAL_AVAILABLE:
        logger.error(
            "Agentic retrieval SDK classes not available. "
            "Install azure-search-documents>=11.7.0b2 with prerelease support."
        )
        return

    search_client = AzureAISearchClient()

    # Step 1: Create knowledge source
    logger.info("Creating knowledge source...")
    if not search_client.create_knowledge_source():
        logger.error("Failed to create knowledge source. Aborting.")
        return

    # Step 2: Create knowledge base
    logger.info("Creating knowledge base...")
    if not search_client.create_knowledge_base():
        logger.error("Failed to create knowledge base. Aborting.")
        return

    # Step 3: Create MCP project connection
    logger.info("Creating MCP project connection...")
    if not search_client.create_project_connection():
        logger.warning(
            "MCP project connection not created. "
            "Set AZURE_AI_PROJECT_RESOURCE_ID to enable. "
            f"Agents can still use the MCP endpoint directly: {search_client.get_mcp_endpoint()}"
        )
    else:
        logger.info("Agentic retrieval pipeline fully provisioned.")

    logger.info(f"MCP endpoint: {search_client.get_mcp_endpoint()}")


def main():
    """Main entrypoint - routes to appropriate indexing method based on EXTRACTION_TYPE."""
    import argparse

    parser = argparse.ArgumentParser(description="JAYCO Dealer Portal Document Indexer")
    parser.add_argument(
        "--extraction-type",
        choices=["document_intelligence", "integrated_vectorization"],
        default=EXTRACTION_TYPE,
        help="Extraction method (default: from EXTRACTION_TYPE env var)",
    )
    parser.add_argument(
        "--dir",
        default="./data/portal_docs",
        help="Directory containing PDF files (for document_intelligence mode)",
    )
    parser.add_argument(
        "--source",
        default="SharePoint",
        help="Source system label (SharePoint, Revver, DynamicWeb)",
    )
    parser.add_argument(
        "--provision-agentic",
        action="store_true",
        help="Provision agentic retrieval pipeline (knowledge source + knowledge base + MCP connection)",
    )
    args = parser.parse_args()

    if args.provision_agentic:
        logger.info("Provisioning agentic retrieval pipeline...")
        provision_agentic_retrieval()
        return

    logger.info(f"Starting indexer with extraction_type={args.extraction_type}")

    if args.extraction_type == "document_intelligence":
        index_with_document_intelligence(docs_path=args.dir, source_system=args.source)
    elif args.extraction_type == "integrated_vectorization":
        index_with_integrated_vectorization()
    else:
        logger.error(f"Unknown extraction type: {args.extraction_type}")


if __name__ == "__main__":
    main()
