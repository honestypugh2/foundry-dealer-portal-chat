"""Simulated Revver (document management) connector for demo mode.

In production, this would use Revver's API to access
JAYCO's document management system.
"""

from pathlib import Path
from datetime import datetime

from app.config import env
from app.models import DocumentInfo


# Documents that would live in Revver in production
REVVER_DOCUMENTS = [
    "Hub, Drums, & Bearings Installation Instructions.pdf",
    "IS-System-Troubleshooting-Guide_v6-1.pdf",
    "Jake Plate and Shock Bushing Guide.pdf",
    "GM SERVICE BULLETIN FOR BRAKE DISCONNECT.pdf",
]


class RevverSimConnector:
    """
    Simulated Revver connector.

    In production:
    - Uses Revver REST API with OAuth2 authentication
    - Accesses JAYCO's technical document repository
    - Supports version tracking and document workflows
    """

    def __init__(self):
        self.data_path = Path(env("REVVER_SIM_DATA_PATH", "./data/revver_docs"))

    async def list_documents(self) -> list[DocumentInfo]:
        """List documents from simulated Revver repository."""
        documents = []

        for doc_name in REVVER_DOCUMENTS:
            file_path = self.data_path / doc_name
            size = file_path.stat().st_size if file_path.exists() else None

            documents.append(
                DocumentInfo(
                    name=doc_name,
                    source_system="Revver",
                    size_bytes=size,
                    page_count=self._estimate_pages(doc_name),
                    last_modified=datetime(2024, 5, 20).isoformat(),
                    tags=self._get_tags(doc_name),
                )
            )

        return documents

    async def get_document_content(self, document_name: str) -> bytes | None:
        """Retrieve document content from simulated Revver."""
        file_path = self.data_path / document_name
        if file_path.exists():
            return file_path.read_bytes()
        return None

    def _estimate_pages(self, doc_name: str) -> int:
        """Estimate page count based on document name."""
        page_map = {
            "Hub, Drums, & Bearings Installation Instructions.pdf": 12,
            "IS-System-Troubleshooting-Guide_v6-1.pdf": 24,
            "Jake Plate and Shock Bushing Guide.pdf": 6,
            "GM SERVICE BULLETIN FOR BRAKE DISCONNECT.pdf": 3,
        }
        return page_map.get(doc_name, 1)

    def _get_tags(self, doc_name: str) -> list[str]:
        """Get tags for document categorization."""
        tag_map = {
            "Hub, Drums, & Bearings Installation Instructions.pdf": ["hub", "bearings", "installation", "drums"],
            "IS-System-Troubleshooting-Guide_v6-1.pdf": ["IS system", "troubleshooting", "guide"],
            "Jake Plate and Shock Bushing Guide.pdf": ["jake plate", "shock", "bushing"],
            "GM SERVICE BULLETIN FOR BRAKE DISCONNECT.pdf": ["brake", "service bulletin", "GM", "safety"],
        }
        return tag_map.get(doc_name, [])
