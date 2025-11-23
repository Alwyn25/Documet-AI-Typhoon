import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from fastapi import UploadFile

from ..config import settings
from ..models.metadata import DocumentMetadata
from ..utils.logging import logger


class IngestionService:
    """Service responsible for persisting uploaded documents and generating metadata."""

    def __init__(self) -> None:
        self.allowed_extensions = {ext.lower() for ext in settings.ALLOWED_EXTENSIONS}
        self.storage_root = settings.storage_root_path
        self.storage_root.mkdir(parents=True, exist_ok=True)
        logger.log_step("ingestion_service_initialized", {
            "storage_root": str(self.storage_root),
            "allowed_extensions": sorted(self.allowed_extensions)
        })

    async def ingest_files(self, files: List[UploadFile]) -> List[Dict[str, Any]]:
        """Persist uploaded files to disk and return descriptive metadata."""
        ingested_documents: List[Dict[str, Any]] = []

        for upload in files:
            original_filename = upload.filename or f"upload-{uuid.uuid4().hex}"
            extension = self._get_extension(original_filename, upload.content_type)

            if extension not in self.allowed_extensions:
                logger.log_error("unsupported_file_extension", {
                    "filename": original_filename,
                    "extension": extension
                })
                raise ValueError(f"Unsupported file type: {extension}")

            file_bytes = await upload.read()
            file_size_bytes = len(file_bytes)

            max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
            if file_size_bytes > max_bytes:
                logger.log_error("file_too_large", {
                    "filename": original_filename,
                    "size_bytes": file_size_bytes,
                    "max_bytes": max_bytes
                })
                raise ValueError(
                    f"File '{original_filename}' exceeds the maximum size of {settings.MAX_FILE_SIZE_MB} MB"
                )

            document_id = uuid.uuid4().hex
            stored_name = f"{document_id}.{extension}"
            stored_path = self.storage_root / stored_name

            with stored_path.open("wb") as output:
                output.write(file_bytes)

            metadata = DocumentMetadata(
                document_id=document_id,
                original_filename=original_filename,
                stored_filename=stored_name,
                content_type=upload.content_type,
                extension=extension,
                size_bytes=file_size_bytes,
                size_mb=round(file_size_bytes / (1024 * 1024), 4),
                storage_path=str(stored_path),
                uploaded_at=datetime.utcnow().isoformat() + "Z",
            )

            logger.log_step("document_ingested", metadata.model_dump())
            ingested_documents.append(metadata.model_dump())

        return ingested_documents

    def _get_extension(self, filename: str, content_type: str | None) -> str:
        suffix = Path(filename).suffix.lower().lstrip(".")
        if suffix:
            return suffix

        if content_type:
            subtype = content_type.split("/")[-1].lower()
            mapped = self._map_mime_subtype(subtype)
            if mapped:
                return mapped

        return "bin"

    @staticmethod
    def _map_mime_subtype(subtype: str) -> str | None:
        mime_map = {
            "jpeg": "jpg",
            "svg+xml": "svg",
            "msword": "doc",
            "vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
            "plain": "txt",
            "rtf": "rtf",
            "x-tiff": "tiff",
        }
        return mime_map.get(subtype, subtype if subtype else None)


ingestion_service = IngestionService()


