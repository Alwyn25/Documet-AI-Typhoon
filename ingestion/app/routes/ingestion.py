import time
from typing import List

from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from pydantic import BaseModel

from ..services.ingestion_service import ingestion_service
from ..models.metadata import DocumentMetadata
from ..utils.logging import logger

router = APIRouter(prefix="/api/v1", tags=["Ingestion"])


class IngestionResponse(BaseModel):
    success: bool
    message: str
    documents: List[DocumentMetadata]
    total_documents: int


@router.post("/ingestion/", response_model=IngestionResponse)
async def ingest_documents(request: Request, files: List[UploadFile] = File(...)):
    start_time = time.time()

    logger.log_step("ingestion_request_received", {
        "method": request.method,
        "url": str(request.url),
        "client": request.client.host if request.client else "unknown",
        "file_count": len(files)
    })

    if not files:
        raise HTTPException(status_code=400, detail="At least one file must be uploaded.")

    try:
        documents = await ingestion_service.ingest_files(files)

        process_time = time.time() - start_time
        logger.log_step("ingestion_completed", {
            "document_count": len(documents),
            "process_time": process_time
        })

        return IngestionResponse(
            success=True,
            message=f"Ingested {len(documents)} documents successfully.",
            documents=documents,
            total_documents=len(documents)
        )
    except ValueError as ve:
        process_time = time.time() - start_time
        logger.log_error("ingestion_validation_error", {
            "error": str(ve),
            "process_time": process_time
        })
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        process_time = time.time() - start_time
        logger.log_error("ingestion_failed", {
            "error": str(exc),
            "process_time": process_time
        })
        raise HTTPException(status_code=500, detail="Failed to ingest documents.")


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "agent": "ingestion_agent"
    }


