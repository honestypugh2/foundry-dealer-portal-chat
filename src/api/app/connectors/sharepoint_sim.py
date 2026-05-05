"""Simulated SharePoint connector for demo mode.

In production, this would use Microsoft Graph API to access
JAYCO's SharePoint document libraries.
"""

import os
from pathlib import Path
from datetime import datetime

from app.config import env
from app.models import DocumentInfo


# Documents that would live in SharePoint in production
SHAREPOINT_DOCUMENTS = [
    "Axles and Suspension - Lippert Master Manual.pdf",
    "Jayco Axle Torque Procedures.pdf",
    "Equalizer Chart Drawing.pdf",
    "Customer Advisory (Fixed Flange Nut Substitution) - 06-02-23.pdf",
    "Deflection Measurement Procedure.pdf",
]


class SharePointSimConnector:
    """
    Simulated SharePoint connector.

    In production:
    - Uses Microsoft Graph API with Entra ID authentication
    - Accesses JAYCO's SharePoint Online document libraries
    - Supports real-time document sync and delta queries
    """

    def __init__(self):
        self.data_path = Path(env("SHAREPOINT_SIM_DATA_PATH", "./data/sharepoint_docs"))

    async def list_documents(self) -> list[DocumentInfo]:
        """List documents from simulated SharePoint library."""
        documents = []

        for doc_name in SHAREPOINT_DOCUMENTS:
            file_path = self.data_path / doc_name
            size = file_path.stat().st_size if file_path.exists() else None

            documents.append(
                DocumentInfo(
                    name=doc_name,
                    source_system="SharePoint",
                    size_bytes=size,
                    page_count=self._estimate_pages(doc_name),
                    last_modified=datetime(2024, 6, 15).isoformat(),
                    tags=self._get_tags(doc_name),
                )
            )

        return documents

    async def get_document_content(self, document_name: str) -> bytes | None:
        """Retrieve document content from simulated SharePoint."""
        file_path = self.data_path / document_name
        if file_path.exists():
            return file_path.read_bytes()
        return None

    def _estimate_pages(self, doc_name: str) -> int:
        """Estimate page count based on document name."""
        page_map = {
            "Axles and Suspension - Lippert Master Manual.pdf": 87,
            "Jayco Axle Torque Procedures.pdf": 4,
            "Equalizer Chart Drawing.pdf": 2,
            "Customer Advisory (Fixed Flange Nut Substitution) - 06-02-23.pdf": 1,
            "Deflection Measurement Procedure.pdf": 3,
        }
        return page_map.get(doc_name, 1)

    def _get_tags(self, doc_name: str) -> list[str]:
        """Get tags for document categorization."""
        tag_map = {
            "Axles and Suspension - Lippert Master Manual.pdf": ["axles", "suspension", "master manual", "lippert"],
            "Jayco Axle Torque Procedures.pdf": ["torque", "procedures", "axles"],
            "Equalizer Chart Drawing.pdf": ["equalizer", "drawings", "specifications"],
            "Customer Advisory (Fixed Flange Nut Substitution) - 06-02-23.pdf": ["advisory", "safety", "flange nut"],
            "Deflection Measurement Procedure.pdf": ["deflection", "measurement", "suspension"],
        }
        return tag_map.get(doc_name, [])
