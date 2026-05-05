"""Chunking Module

Fixed-size chunking with overlap for JAYCO dealer technical documents.
Supports character-based and word-based chunking strategies.

Reference: https://learn.microsoft.com/en-us/azure/search/vector-search-how-to-chunk-documents
"""

import hashlib
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class TextChunk:
    """A single text chunk with metadata."""
    chunk_id: str
    chunk_index: int
    text: str
    page_number: int | None = None
    parent_id: str = ""


def _stable_chunk_id(document_id: str, chunk_index: int, chunk_text: str) -> str:
    """Generate a stable, deterministic chunk ID from document ID, index, and content."""
    h = hashlib.md5(chunk_text.encode("utf-8", errors="ignore")).hexdigest()
    return f"{document_id}_{chunk_index}_{h}"


def fixed_size_chunking(
    text: str,
    size: int = 2000,
    overlap: int = 200,
    document_id: str = "document",
    page_number: int | None = None,
) -> List[TextChunk]:
    """
    Splits text into fixed-size chunks with overlap and returns
    a list of TextChunk objects including chunk_id and chunk_index.

    Args:
        text: The input string to chunk.
        size: The maximum number of characters per chunk. Must be > 0.
        overlap: Overlap between consecutive chunks in characters. Must be >= 0 and < size.
        document_id: Identifier used when generating stable chunk IDs (parent doc ID).
        page_number: Optional page number for all chunks from this text.

    Returns:
        A list of TextChunk instances.
    """
    if size <= 0:
        raise ValueError("size must be > 0")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")
    if overlap >= size:
        raise ValueError("overlap must be < size")

    if not text or not text.strip():
        return []

    text_length = len(text)
    step = size - overlap
    chunks: List[TextChunk] = []
    start = 0
    index = 0

    while start < text_length:
        end = min(start + size, text_length)
        chunk_text = text[start:end].strip()

        if chunk_text:
            chunk_id = _stable_chunk_id(document_id, index, chunk_text)
            chunks.append(TextChunk(
                chunk_id=chunk_id,
                chunk_index=index,
                text=chunk_text,
                page_number=page_number,
                parent_id=document_id,
            ))

        # Stop once this chunk reaches the end
        if start + size >= text_length:
            break

        start += step
        index += 1

    return chunks


def chunk_document_pages(
    pages: list[dict],
    size: int = 2000,
    overlap: int = 200,
    document_id: str = "document",
    cross_page: bool = False,
) -> List[TextChunk]:
    """
    Chunk a document that has been split into pages.

    Args:
        pages: List of dicts with 'page_number' and 'text' keys.
        size: Maximum characters per chunk.
        overlap: Overlap between consecutive chunks.
        document_id: Parent document ID for chunk ID generation.
        cross_page: If True, concatenates all pages and chunks across page
            boundaries (page_number reflects the starting page of each chunk).
            If False, processes each page independently.

    Returns:
        List of TextChunk instances with page_number preserved.
    """
    if cross_page:
        return _chunk_cross_page(pages, size, overlap, document_id)

    all_chunks: List[TextChunk] = []
    global_index = 0

    for page in pages:
        page_text = page.get("text", "")
        page_num = page.get("page_number")

        if not page_text or not page_text.strip():
            continue

        page_chunks = fixed_size_chunking(
            text=page_text,
            size=size,
            overlap=overlap,
            document_id=document_id,
            page_number=page_num,
        )

        # Re-index to be globally sequential
        for chunk in page_chunks:
            reindexed = TextChunk(
                chunk_id=_stable_chunk_id(document_id, global_index, chunk.text),
                chunk_index=global_index,
                text=chunk.text,
                page_number=chunk.page_number,
                parent_id=document_id,
            )
            all_chunks.append(reindexed)
            global_index += 1

    return all_chunks


def _chunk_cross_page(
    pages: list[dict],
    size: int,
    overlap: int,
    document_id: str,
) -> List[TextChunk]:
    """
    Concatenate all pages and chunk across page boundaries.
    Each chunk's page_number reflects the page where the chunk starts.
    """
    # Build a combined text and track page boundary offsets
    combined = ""
    page_offsets: list[tuple[int, int]] = []  # (start_offset, page_number)

    for page in pages:
        page_text = page.get("text", "")
        page_num = page.get("page_number")
        if not page_text or not page_text.strip():
            continue
        page_offsets.append((len(combined), page_num))
        combined += page_text + "\n"

    if not combined.strip():
        return []

    # Chunk the combined text
    step = size - overlap
    chunks: List[TextChunk] = []
    start = 0
    index = 0

    while start < len(combined):
        end = min(start + size, len(combined))
        chunk_text = combined[start:end].strip()

        if chunk_text:
            # Find which page this chunk starts on
            page_num = None
            for offset, pn in reversed(page_offsets):
                if start >= offset:
                    page_num = pn
                    break

            chunk_id = _stable_chunk_id(document_id, index, chunk_text)
            chunks.append(TextChunk(
                chunk_id=chunk_id,
                chunk_index=index,
                text=chunk_text,
                page_number=page_num,
                parent_id=document_id,
            ))
            index += 1

        if start + size >= len(combined):
            break
        start += step

    return chunks


def chunk_full_text(
    text: str,
    size: int = 2000,
    overlap: int = 200,
    document_id: str = "document",
) -> List[TextChunk]:
    """
    Chunk a full document text (no page-level splitting).
    Useful when Azure DI returns a single text blob.

    Args:
        text: Full document text.
        size: Maximum characters per chunk.
        overlap: Overlap between consecutive chunks.
        document_id: Parent document ID for chunk ID generation.

    Returns:
        List of TextChunk instances.
    """
    return fixed_size_chunking(
        text=text,
        size=size,
        overlap=overlap,
        document_id=document_id,
        page_number=None,
    )
