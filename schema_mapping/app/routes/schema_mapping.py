import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..services.schema_mapping_service import schema_mapping_service
from ..services.database_service import database_service
from ..models.schemas import SchemaMappingRequest, SchemaMappingResponse, ValidationResult, InvoiceSchema
from ..utils.logging import logger
from ..utils.mongo import mongo_manager

router = APIRouter(prefix="/api/v1", tags=["Schema Mapping"])


@router.post("/schema-mapping/", response_model=SchemaMappingResponse)
async def map_schema(request: Request, mapping_request: SchemaMappingRequest):
    """
    Extract structured schema from OCR text
    
    Request body should contain:
    - ocr_text: The OCR-extracted text
    - schema_type: Type of schema (default: "invoice")
    """
    start_time = time.time()
    
    logger.log_step("schema_mapping_request_received", {
        "method": request.method,
        "url": str(request.url),
        "client": request.client.host if request.client else "unknown",
        "schema_type": mapping_request.schema_type
    })
    
    if not mapping_request.ocr_text or not mapping_request.ocr_text.strip():
        raise HTTPException(status_code=400, detail="OCR text cannot be empty.")
    
    try:
        # Extract schema
        extraction_result = await schema_mapping_service.extract_schema(
            ocr_text=mapping_request.ocr_text,
            schema_type=mapping_request.schema_type
        )
        
        logger.log_step("schema_extracted", {
            "document_id": extraction_result["document_id"],
            "has_invoice_number": bool(extraction_result["extracted_schema"].get("invoiceNumber")),
            "has_vendor": bool(extraction_result["extracted_schema"].get("vendor")),
            "has_customer": bool(extraction_result["extracted_schema"].get("customer")),
            "line_items_count": len(extraction_result["extracted_schema"].get("lineItems", []))
        })
        
        # Validate schema
        validation_result = await schema_mapping_service.validate_schema(
            extracted_schema=extraction_result["extracted_schema"]
        )
        
        # Save to PostgreSQL database
        invoice_schema = InvoiceSchema(**extraction_result["extracted_schema"])
        confidence_score = 100.0 if validation_result.isValid else 80.0  # Simple confidence scoring
        
        logger.log_step("preparing_database_save", {
            "document_id": extraction_result["document_id"],
            "customer_name": invoice_schema.customer.name,
            "vendor_name": invoice_schema.vendor.name
        })
        
        invoice_id = await database_service.save_invoice_schema(
            invoice_schema=invoice_schema,
            document_id=extraction_result["document_id"],
            ocr_text=mapping_request.ocr_text,
            validation_result=validation_result,
            confidence_score=confidence_score
        )
        logger.log_step("invoice_saved_to_postgres", {
            "invoice_id": invoice_id,
            "document_id": extraction_result["document_id"]
        })
        
        # Prepare response object
        response_data = SchemaMappingResponse(
            success=True,
            message="Schema extracted, validated, and saved to database successfully.",
            document_id=extraction_result["document_id"],
            invoice_id=invoice_id,
            extracted_schema=extraction_result["extracted_schema"],
            validation_result=validation_result
        )
        
        # Save full response to MongoDB
        try:
            mongo_document = {
                "document_id": extraction_result["document_id"],
                "invoice_id": invoice_id,
                "ocr_text": mapping_request.ocr_text,
                "schema_type": mapping_request.schema_type,
                "extracted_schema": extraction_result["extracted_schema"],
                "validation_result": {
                    "isValid": validation_result.isValid,
                    "errors": validation_result.errors,
                    "warnings": validation_result.warnings
                },
                "confidence_score": confidence_score,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "response": response_data.model_dump()  # Full response as-is
            }
            
            mongo_id = mongo_manager.save_document(mongo_document)
            logger.log_step("invoice_saved_to_mongodb", {
                "mongo_id": mongo_id,
                "document_id": extraction_result["document_id"],
                "invoice_id": invoice_id
            })
        except Exception as mongo_error:
            # Log error but don't fail the request if MongoDB save fails
            logger.log_error("mongodb_save_failed", {
                "error": str(mongo_error),
                "document_id": extraction_result["document_id"],
                "invoice_id": invoice_id
            })
        
        process_time = time.time() - start_time
        
        logger.log_step("schema_mapping_completed", {
            "document_id": extraction_result["document_id"],
            "invoice_id": invoice_id,
            "is_valid": validation_result.isValid,
            "process_time": process_time
        })
        
        return response_data
        
    except ValueError as ve:
        process_time = time.time() - start_time
        logger.log_error("schema_mapping_validation_error", {
            "error": str(ve),
            "process_time": process_time
        })
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        process_time = time.time() - start_time
        logger.log_error("schema_mapping_failed", {
            "error": str(exc),
            "process_time": process_time
        })
        raise HTTPException(status_code=500, detail=f"Failed to extract schema: {str(exc)}")


@router.get("/invoices/{invoice_id}")
async def get_invoice(invoice_id: int):
    """Get invoice by ID with all related data"""
    try:
        invoice_data = await database_service.get_invoice_by_id(invoice_id)
        if not invoice_data:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return {
            "success": True,
            "invoice": invoice_data
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.log_error("get_invoice_failed", {
            "invoice_id": invoice_id,
            "error": str(exc)
        })
        raise HTTPException(status_code=500, detail=f"Failed to retrieve invoice: {str(exc)}")


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "agent": "schema_mapping_agent"
    }

