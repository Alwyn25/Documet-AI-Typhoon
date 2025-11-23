import time
import uuid
import json
from typing import List, Dict, Any, Optional
from enum import Enum
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form, Depends
from pydantic import BaseModel
from bson import ObjectId

from ..services.ocr_service import ocr_service, serialize_for_json
from ..services.typhoon_api_service import typhoon_api_service
from ..services.gpt4_vision_service import gpt4_vision_service
from ..utils.logging import logger

router = APIRouter(prefix="/api/v1", tags=["OCR"])


class OCRInputType(str, Enum):
    """Allowed document input types for OCR processing."""
    pdf = "pdf"
    image = "image"
    both = "both"


class OCREngine(str, Enum):
    """Supported OCR engines."""
    typhoon = "typhoon"
    azure = "azure"
    tesseract = "tesseract"
    easyocr = "easyocr"


class OCRRequest(BaseModel):
    """Request model for OCR processing."""
    argument: OCRInputType


def parse_ocr_request(argument: OCRInputType = Form(...)) -> OCRRequest:
    """Parse multipart form data into an OCRRequest model."""
    return OCRRequest(argument=argument)


class OCRResponse(BaseModel):
    """Response model for OCR processing"""
    success: bool
    message: str
    processed_documents: List[Dict[str, Any]]
    total_documents: int
    errors: List[str]


@router.post("/ocr/", response_model=OCRResponse)
async def process_ocr(
    request: Request,
    ocr_request: OCRRequest = Depends(parse_ocr_request),
    files: List[UploadFile] = File(...)
):
    """Process uploaded PDF and image files with OCR"""
    start_time = time.time()
    
    logger.log_step("request_received", {
        "method": request.method,
        "url": str(request.url),
        "client": request.client.host if request.client else "unknown"
    })
    
    if not files:
        raise HTTPException(status_code=400, detail="At least one file must be uploaded for OCR processing.")
    
    requested_type = ocr_request.argument
    disallowed_files: List[str] = []

    for upload in files:
        filename = upload.filename or "unknown"
        content_type = (upload.content_type or "").lower()
        suffix = (filename.split(".")[-1].lower() if "." in filename else "")
        is_pdf = content_type == "application/pdf" or suffix == "pdf"
        is_image = content_type.startswith("image/") or suffix in {"png", "jpg", "jpeg", "tiff", "bmp", "gif", "webp"}

        if requested_type == OCRInputType.pdf and not is_pdf:
            disallowed_files.append(filename)
        elif requested_type == OCRInputType.image and not is_image:
            disallowed_files.append(filename)
        elif requested_type == OCRInputType.both and not (is_pdf or is_image):
            disallowed_files.append(filename)

    if disallowed_files:
        raise HTTPException(
            status_code=400,
            detail=f"The following files do not match requested type '{requested_type.value}': {', '.join(disallowed_files)}"
        )

    logger.log_step("ocr_endpoint_called", {
        "requested_type": requested_type.value,
        "file_count": len(files),
        "filenames": [upload.filename or "unknown" for upload in files],
        "content_types": [upload.content_type for upload in files]
    })
    
    try:
        # Prepare uploaded files for OCR processing
        prepared_documents = await ocr_service.prepare_documents_from_uploads(files)
        
        # Process documents with OCR
        result = await ocr_service.process_documents(prepared_documents)
        
        process_time = time.time() - start_time
        
        logger.log_step("ocr_endpoint_completed", {
            "success": result["success"],
            "total_documents": result["total_documents"],
            "process_time": process_time,
            "requested_type": requested_type.value
        })
        
        logger.log_step("request_completed", {
            "method": request.method,
            "url": str(request.url),
            "status_code": 200,
            "process_time": process_time
        })
        
        return OCRResponse(**result)
        
    except Exception as e:
        process_time = time.time() - start_time
        error_msg = f"OCR processing failed: {str(e)}"
        
        logger.log_error("ocr_processing_failed", {
            "error": str(e),
            "process_time": process_time
        })
        
        logger.log_step("request_completed", {
            "method": request.method,
            "url": str(request.url),
            "status_code": 500,
            "process_time": process_time
        })
        
        raise HTTPException(status_code=500, detail=error_msg)


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "agent": "ocr_agent"
    }


@router.get("/documents/")
async def list_documents():
    """List all OCR processed documents"""
    try:
        from ..utils.mongo import mongo_manager
        documents = mongo_manager.list_documents()
        
        # Serialize documents to handle MongoDB ObjectId fields
        serialized_documents = serialize_for_json(documents)
        
        # Remove base64 data for performance
        for doc in serialized_documents:
            if "pages" in doc:
                for page in doc["pages"]:
                    if "images" in page:
                        for image in page["images"]:
                            if "base64_data" in image:
                                image["base64_data"] = "[BASE64_DATA]"
        
        return {
            "success": True,
            "documents": serialized_documents,
            "total": len(serialized_documents)
        }
        
    except Exception as e:
        logger.log_error("list_documents_failed", {"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")


@router.get("/documents/{document_id}")
async def get_document(document_id: str):
    """Get a specific OCR processed document"""
    try:
        from ..utils.mongo import mongo_manager
        document = None

        if document_id and ObjectId.is_valid(document_id):
            try:
                document = mongo_manager.get_document(document_id)
            except Exception:
                document = None

        if not document:
            document = mongo_manager.get_document_by_field("document_id", document_id)
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Serialize document to handle MongoDB ObjectId fields
        serialized_document = serialize_for_json(document)
        
        return {
            "success": True,
            "document": serialized_document
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.log_error("get_document_failed", {"error": str(e), "document_id": document_id})
        raise HTTPException(status_code=500, detail=f"Failed to get document: {str(e)}") 


@router.post("/typhoon/upload")
async def typhoon_ocr_upload(
    file: UploadFile = File(...),
    pages: Optional[str] = Form(default=None, description="Comma-separated page numbers for PDFs"),
):
    """Upload a PDF or image and run Typhoon OCR via the upstream API."""
    logger.log_step("typhoon_upload_received", {
        "filename": file.filename,
        "content_type": file.content_type,
        "pages": pages,
    })

    try:
        pages_list = None
        if pages:
            try:
                pages_list = [int(p.strip()) for p in pages.split(",") if p.strip()]
            except ValueError:
                raise HTTPException(status_code=400, detail="Pages must be comma-separated integers.")

        api_response = await typhoon_api_service.extract_text(file, pages_list)

        extracted_texts: List[str] = []
        for page_result in api_response.get("results", []):
            if page_result.get("success") and page_result.get("message"):
                content = page_result["message"]["choices"][0]["message"]["content"]
                try:
                    parsed = json.loads(content)
                    extracted_texts.append(parsed.get("natural_text", content))
                except json.JSONDecodeError:
                    extracted_texts.append(content)

        return {
            "success": True,
            "message": "Typhoon OCR completed",
            "pages_processed": len(extracted_texts),
            "extracted_texts": extracted_texts,
            "raw_response": api_response,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.log_error("typhoon_upload_failed", {"error": str(exc)})
        raise HTTPException(status_code=500, detail=f"Typhoon OCR upload failed: {str(exc)}")


async def _run_engine_pipeline(files: List[UploadFile], engine: OCREngine, request: Request) -> OCRResponse:
    logger.log_step("engine_ocr_request_received", {
        "engine": engine.value,
        "file_count": len(files),
        "filenames": [upload.filename or "unknown" for upload in files],
        "content_types": [upload.content_type for upload in files]
    })

    prepared_documents = await ocr_service.prepare_documents_from_uploads(files)
    result = await ocr_service.process_documents_with_engine(prepared_documents, engine.value)
    return OCRResponse(**result)


@router.post("/ocr/typhoon/", response_model=OCRResponse)
async def process_ocr_typhoon(request: Request, files: List[UploadFile] = File(...)):
    return await _run_engine_pipeline(files, OCREngine.typhoon, request)


@router.post("/ocr/azure/", response_model=OCRResponse)
async def process_ocr_azure(request: Request, files: List[UploadFile] = File(...)):
    return await _run_engine_pipeline(files, OCREngine.azure, request)


@router.post("/ocr/tesseract/", response_model=OCRResponse)
async def process_ocr_tesseract(request: Request, files: List[UploadFile] = File(...)):
    return await _run_engine_pipeline(files, OCREngine.tesseract, request)


@router.post("/ocr/easyocr/", response_model=OCRResponse)
async def process_ocr_easyocr(request: Request, files: List[UploadFile] = File(...)):
    return await _run_engine_pipeline(files, OCREngine.easyocr, request)


@router.post("/ocr/gpt4vision/", response_model=OCRResponse)
async def process_ocr_gpt4vision(request: Request, files: List[UploadFile] = File(...)):
    """Process uploaded documents using GPT-4 Vision (page-by-page extraction)."""
    start_time = time.time()
    processed_documents = []
    errors: List[str] = []

    logger.log_step("gpt4vision_request_received", {
        "file_count": len(files),
        "filenames": [upload.filename or "unknown" for upload in files],
        "content_types": [upload.content_type for upload in files]
    })

    for upload in files:
        try:
            pages = await gpt4_vision_service.process_upload(upload)
            
            # Aggregate token usage for document
            document_token_usage = None
            all_page_tokens = [page.get("token_usage") for page in pages if page.get("token_usage")]
            if all_page_tokens:
                total_doc_input = sum(usage.get("input_tokens", 0) for usage in all_page_tokens)
                total_doc_output = sum(usage.get("output_tokens", 0) or 0 for usage in all_page_tokens)
                document_token_usage = {
                    "input_tokens": total_doc_input,
                    "output_tokens": total_doc_output if total_doc_output > 0 else None,
                    "total_tokens": total_doc_input + total_doc_output,
                    "pages_with_tokens": len(all_page_tokens),
                    "details": all_page_tokens
                }
            
            document = {
                "document_id": uuid.uuid4().hex,
                "filename": upload.filename or "document",
                "pages": pages,
                "total_pages": len(pages),
                "ocr_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "ocr_status": "completed",
                "ocr_errors": [],
                "token_usage": document_token_usage
            }
            processed_documents.append(document)
        except Exception as exc:
            error_msg = f"GPT4Vision failed for {upload.filename or 'document'}: {str(exc)}"
            errors.append(error_msg)
            logger.log_error("gpt4vision_document_failed", {"error": str(exc), "filename": upload.filename})

    process_time = time.time() - start_time

    logger.log_step("gpt4vision_request_completed", {
        "documents": len(processed_documents),
        "errors": len(errors),
        "process_time": process_time
    })

    return OCRResponse(
        success=len(errors) == 0,
        message=f"GPT-4 Vision processed {len(processed_documents)} documents",
        processed_documents=processed_documents,
        total_documents=len(files),
        errors=errors
    )