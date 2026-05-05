"""Upload to Blob Storage

Uploads JAYCO dealer technical documents (PDFs) from local directory
to Azure Blob Storage for indexing by Azure AI Search.
"""

import logging
import os
from pathlib import Path
from typing import Optional

from azure.identity import AzureCliCredential, ChainedTokenCredential, ManagedIdentityCredential
from azure.storage.blob import BlobServiceClient, ContainerClient
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def get_blob_service_client() -> BlobServiceClient:
    """Create BlobServiceClient using connection string or managed identity."""
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")

    if connection_string:
        return BlobServiceClient.from_connection_string(connection_string)

    account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
    if not account_name:
        raise ValueError(
            "Either AZURE_STORAGE_CONNECTION_STRING or AZURE_STORAGE_ACCOUNT_NAME "
            "must be set."
        )

    credential = ChainedTokenCredential(
        ManagedIdentityCredential(),
        AzureCliCredential(),
    )
    account_url = f"https://{account_name}.blob.core.windows.net"
    return BlobServiceClient(account_url=account_url, credential=credential)


def upload_documents(
    local_dir: str,
    container_name: Optional[str] = None,
    blob_prefix: str = "documents",
    overwrite: bool = True,
) -> list[dict]:
    """
    Upload all PDF files from a local directory to Azure Blob Storage.

    Args:
        local_dir: Path to local directory containing PDF files.
        container_name: Blob container name (defaults to env AZURE_STORAGE_CONTAINER).
        blob_prefix: Virtual folder prefix in blob storage.
        overwrite: Whether to overwrite existing blobs.

    Returns:
        List of dicts with upload results (filename, blob_url, success).
    """
    container_name = container_name or os.getenv("AZURE_STORAGE_CONTAINER_PORTAL", "portal-docs")
    docs_path = Path(local_dir)

    if not docs_path.exists():
        raise FileNotFoundError(f"Directory not found: {local_dir}")

    blob_service = get_blob_service_client()

    # Create container if it doesn't exist
    container_client = blob_service.get_container_client(container_name)
    try:
        container_client.get_container_properties()
    except Exception:
        container_client.create_container()
        logger.info(f"Created container: {container_name}")

    results = []
    pdf_files = sorted(docs_path.glob("*.pdf"))

    if not pdf_files:
        logger.warning(f"No PDF files found in {local_dir}")
        return results

    logger.info(f"Uploading {len(pdf_files)} PDF files to container '{container_name}'")

    for pdf_file in pdf_files:
        blob_name = f"{blob_prefix}/{pdf_file.name}" if blob_prefix else pdf_file.name
        blob_client = container_client.get_blob_client(blob_name)

        try:
            with open(pdf_file, "rb") as f:
                blob_client.upload_blob(f, overwrite=overwrite)

            blob_url = blob_client.url
            logger.info(f"  Uploaded: {pdf_file.name} -> {blob_name}")
            results.append({
                "filename": pdf_file.name,
                "blob_name": blob_name,
                "blob_url": blob_url,
                "success": True,
            })
        except Exception as e:
            logger.error(f"  Failed to upload {pdf_file.name}: {e}")
            results.append({
                "filename": pdf_file.name,
                "blob_name": blob_name,
                "blob_url": "",
                "success": False,
                "error": str(e),
            })

    succeeded = sum(1 for r in results if r["success"])
    logger.info(f"Upload complete: {succeeded}/{len(results)} files uploaded successfully")
    return results


def main():
    """CLI entrypoint for uploading documents."""
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Upload dealer portal PDFs to Azure Blob Storage")
    parser.add_argument(
        "--dir",
        default="./data/sharepoint_docs",
        help="Local directory containing PDF files (default: ./data/sharepoint_docs)",
    )
    parser.add_argument(
        "--container",
        default=None,
        help="Blob container name (default: from AZURE_STORAGE_CONTAINER_PORTAL env)",
    )
    parser.add_argument(
        "--prefix",
        default="documents",
        help="Blob virtual folder prefix (default: documents)",
    )
    parser.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Don't overwrite existing blobs",
    )
    args = parser.parse_args()

    results = upload_documents(
        local_dir=args.dir,
        container_name=args.container,
        blob_prefix=args.prefix,
        overwrite=not args.no_overwrite,
    )

    print(f"\n{'='*60}")
    print(f"Upload Summary: {sum(1 for r in results if r['success'])}/{len(results)} succeeded")
    print(f"{'='*60}")
    for r in results:
        status = "OK" if r["success"] else "FAILED"
        print(f"  [{status}] {r['filename']}")


if __name__ == "__main__":
    main()
