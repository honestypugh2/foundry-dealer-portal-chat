"""Documents router - Document listing and metadata."""

from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.models import DocumentListResponse
from app.connectors.sharepoint_sim import SharePointSimConnector
from app.connectors.revver_sim import RevverSimConnector

router = APIRouter()


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    source: str = "all",
):
    """
    List available documents from all source systems.
    Sources: sharepoint, revver, all
    """
    documents = []

    if source in ("all", "sharepoint"):
        sp_connector = SharePointSimConnector()
        documents.extend(await sp_connector.list_documents())

    if source in ("all", "revver"):
        revver_connector = RevverSimConnector()
        documents.extend(await revver_connector.list_documents())

    return DocumentListResponse(
        documents=documents,
        total_count=len(documents),
    )


@router.get("/documents/{document_name}")
async def download_document(document_name: str):
    """Download a document PDF by name."""
    # Search in both connector paths
    sp_connector = SharePointSimConnector()
    revver_connector = RevverSimConnector()

    for connector in [sp_connector, revver_connector]:
        file_path = connector.data_path / document_name
        if file_path.exists() and file_path.is_file():
            return FileResponse(
                path=str(file_path.resolve()),
                filename=document_name,
                media_type="application/pdf",
            )

    # Also check portal_docs as fallback
    portal_path = Path("../../data/portal_docs") / document_name
    if portal_path.exists() and portal_path.is_file():
        return FileResponse(
            path=str(portal_path.resolve()),
            filename=document_name,
            media_type="application/pdf",
        )

    raise HTTPException(status_code=404, detail=f"Document '{document_name}' not found")
