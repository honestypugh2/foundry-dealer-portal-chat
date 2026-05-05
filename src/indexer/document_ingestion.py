"""Document Ingestion Module

Processes JAYCO dealer technical documents (PDFs) using:
1. Azure Document Intelligence (OCR-enabled, layout extraction) - DEFAULT
2. PyPDF2 fallback (no Azure required)

Supports: PDF files from SharePoint, Revver, and DynamicWeb sources.
"""

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Optional Azure imports
try:
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
    from azure.identity import AzureCliCredential, ChainedTokenCredential, ManagedIdentityCredential
    DOCINT_AVAILABLE = True
except ImportError:
    DOCINT_AVAILABLE = False
    logger.info("azure-ai-documentintelligence not installed, using PyPDF2 fallback only")

try:
    from PyPDF2 import PdfReader
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False
    logger.warning("PyPDF2 not installed, PDF processing limited")


class DocumentIngestionService:
    """
    Processes JAYCO dealer technical documents and extracts text content.

    Supports:
    - Azure Document Intelligence for OCR-enabled layout extraction (default)
    - PyPDF2 for standard PDF text extraction (fallback)
    """

    def __init__(self, use_azure: bool = True):
        self.use_azure = use_azure
        self.azure_endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")

        if self.use_azure and not self.azure_endpoint:
            logger.warning(
                "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT not configured. "
                "Falling back to PyPDF2 processing."
            )
            self.use_azure = False

        if self.use_azure and not DOCINT_AVAILABLE:
            logger.warning(
                "azure-ai-documentintelligence not installed. "
                "Falling back to PyPDF2 processing."
            )
            self.use_azure = False

    def process_document(self, file_path: str) -> dict[str, Any]:
        """
        Process a single PDF document and extract text content.

        Args:
            file_path: Path to the PDF document file

        Returns:
            Dictionary with extracted text, metadata, page info, and tables
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Document not found: {file_path}")

        ext = path.suffix.lower()
        if ext != ".pdf":
            raise ValueError(f"Unsupported file type: {ext}. Only PDF files are supported.")

        logger.info(f"Processing document: {path.name} (method: {'Azure DI' if self.use_azure else 'PyPDF2'})")

        if self.use_azure and DOCINT_AVAILABLE:
            return self._process_with_azure(file_path)
        elif PYPDF2_AVAILABLE:
            return self._process_with_pypdf2(file_path)
        else:
            raise RuntimeError("No PDF processing library available. Install PyPDF2 or azure-ai-documentintelligence.")

    def _process_with_azure(self, file_path: str) -> dict[str, Any]:
        """Process document using Azure Document Intelligence prebuilt-layout model."""
        try:
            credential = ChainedTokenCredential(
                ManagedIdentityCredential(),
                AzureCliCredential(),
            )

            client = DocumentIntelligenceClient(
                endpoint=self.azure_endpoint,
                credential=credential,
            )

            with open(file_path, "rb") as f:
                poller = client.begin_analyze_document(
                    model_id="prebuilt-layout",
                    body=f,
                    content_type="application/octet-stream",
                )
                result = poller.result()

            # Extract full text content
            text = result.content if result.content else ""

            # Extract per-page text
            pages = []
            if result.pages:
                for page in result.pages:
                    page_text = ""
                    if page.lines:
                        page_text = "\n".join(line.content for line in page.lines)
                    pages.append({
                        "page_number": page.page_number,
                        "text": page_text,
                        "width": page.width,
                        "height": page.height,
                    })

            # Extract tables
            tables = []
            if result.tables:
                for table in result.tables:
                    table_data = {
                        "row_count": table.row_count,
                        "column_count": table.column_count,
                        "cells": [],
                    }
                    if table.cells:
                        for cell in table.cells:
                            table_data["cells"].append({
                                "row_index": cell.row_index,
                                "column_index": cell.column_index,
                                "content": cell.content,
                            })
                    tables.append(table_data)

            return {
                "text": text,
                "pages": pages,
                "page_count": len(result.pages) if result.pages else 1,
                "word_count": len(text.split()),
                "char_count": len(text),
                "tables": tables,
                "extraction_method": "azure_document_intelligence",
            }

        except Exception as e:
            logger.warning(
                f"Azure Document Intelligence failed for {file_path}: {e}. "
                "Falling back to PyPDF2."
            )
            if PYPDF2_AVAILABLE:
                return self._process_with_pypdf2(file_path)
            raise

    def _process_with_pypdf2(self, file_path: str) -> dict[str, Any]:
        """Process PDF using PyPDF2 (fallback when Azure DI unavailable)."""
        if not PYPDF2_AVAILABLE:
            raise ImportError("PyPDF2 is required for fallback PDF processing")

        reader = PdfReader(file_path)
        pages = []
        all_text_parts = []

        for page_num, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            if page_text.strip():
                pages.append({
                    "page_number": page_num,
                    "text": page_text,
                    "width": None,
                    "height": None,
                })
                all_text_parts.append(page_text)

        text = "\n\n".join(all_text_parts)

        return {
            "text": text,
            "pages": pages,
            "page_count": len(reader.pages),
            "word_count": len(text.split()),
            "char_count": len(text),
            "tables": [],
            "extraction_method": "pypdf2",
        }
