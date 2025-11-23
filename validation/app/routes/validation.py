"""Validation routes"""

import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..services.validation_service import validation_service
from ..models.schemas import ValidationRequest, ValidationResponse
from ..utils.logging import logger

router = APIRouter(prefix="/api/v1", tags=["Validation"])


@router.post("/validate/", response_model=ValidationResponse)
async def validate_invoice(request: Request, validation_request: ValidationRequest):
    """
    Validate invoice by checking if it exists in database and comparing all entities
    
    Request body should follow the InvoiceSchema structure:
    {
      "invoiceNumber": string | null,
      "invoiceDate": string | null,
      "dueDate": string | null,
      "vendor": {
        "name": string | null,
        "gstin": string | null,
        "pan": string | null,
        "address": string | null
      },
      "customer": {
        "name": string | null,
        "address": string | null
      },
      "lineItems": [
        {
          "description": string,
          "quantity": number,
          "unitPrice": number,
          "taxPercent": number,
          "amount": number
        }
      ],
      "totals": {
        "subtotal": number,
        "gstAmount": number,
        "roundOff": number | null,
        "grandTotal": number
      },
      "paymentDetails": {
        "mode": string | null,
        "reference": string | null,
        "status": "Paid" | "Unpaid" | "Partial" | null
      }
    }
    """
    start_time = time.time()
    
    logger.log_step("validation_request_received", {
        "method": request.method,
        "url": str(request.url),
        "client": request.client.host if request.client else "unknown",
        "invoice_number": validation_request.invoiceNumber
    })
    
    if not validation_request.invoiceNumber:
        raise HTTPException(
            status_code=400,
            detail="invoiceNumber is required for validation."
        )
    
    try:
        # Perform validation
        validation_result = await validation_service.validate_invoice(validation_request)
        
        process_time = time.time() - start_time
        
        # Parse LLM summary if available
        llm_summary = None
        if validation_result.get("llm_summary"):
            from ..models.schemas import ValidationSummary
            llm_summary = ValidationSummary(**validation_result["llm_summary"])
        
        logger.log_step("validation_completed", {
            "invoice_number": validation_request.invoiceNumber,
            "invoice_exists": validation_result["invoice_exists"],
            "process_time": process_time,
            "comparisons_count": len(validation_result.get("comparisons", [])),
            "llm_summary_available": llm_summary is not None
        })
        
        # Ensure comparisons are always present
        comparisons = validation_result.get("comparisons", [])
        if not comparisons:
            logger.log_error("no_comparisons_in_response", {
                "invoice_number": validation_request.invoiceNumber,
                "note": "Comparisons array is empty in validation result"
            })
        
        return ValidationResponse(
            success=True,
            message="Validation completed successfully.",
            invoice_exists=validation_result["invoice_exists"],
            invoice_id=validation_result.get("invoice_id"),
            duplicate_by_criteria=validation_result.get("duplicate_by_criteria", False),
            comparisons=comparisons,
            summary=validation_result.get("summary", {}),
            missing_value_checks=validation_result.get("missing_value_checks"),
            tax_validation_errors=validation_result.get("tax_validation_errors"),
            llm_summary=llm_summary
        )
        
    except Exception as exc:
        process_time = time.time() - start_time
        logger.log_error("validation_failed", {
            "error": str(exc),
            "invoice_number": validation_request.invoiceNumber,
            "process_time": process_time
        })
        raise HTTPException(
            status_code=500,
            detail=f"Failed to validate invoice: {str(exc)}"
        )


@router.get("/validate/{invoice_number}")
async def validate_invoice_by_number(invoice_number: str):
    """
    Validate invoice by invoice number (fetches from database and returns comparison)
    """
    start_time = time.time()
    
    logger.log_step("validation_by_number_request", {
        "invoice_number": invoice_number
    })
    
    try:
        # Create validation request with just invoice number
        # Note: This endpoint requires minimal data, but ValidationRequest requires all fields
        # For this endpoint, we'll need to provide minimal valid data
        from ..models.schemas import Vendor, Customer, LineItem, Totals, PaymentDetails
        
        validation_request = ValidationRequest(
            invoiceNumber=invoice_number,
            vendor=Vendor(),
            customer=Customer(),
            lineItems=[],
            totals=Totals(subtotal=0.0, gstAmount=0.0, grandTotal=0.0),
            paymentDetails=PaymentDetails()
        )
        
        # Perform validation
        validation_result = await validation_service.validate_invoice(validation_request)
        
        process_time = time.time() - start_time
        
        logger.log_step("validation_by_number_completed", {
            "invoice_number": invoice_number,
            "invoice_exists": validation_result["invoice_exists"],
            "process_time": process_time
        })
        
        return ValidationResponse(
            success=True,
            message="Validation completed successfully.",
            invoice_exists=validation_result["invoice_exists"],
            invoice_id=validation_result.get("invoice_id"),
            comparisons=validation_result["comparisons"],
            summary=validation_result["summary"]
        )
        
    except Exception as exc:
        process_time = time.time() - start_time
        logger.log_error("validation_by_number_failed", {
            "error": str(exc),
            "invoice_number": invoice_number,
            "process_time": process_time
        })
        raise HTTPException(
            status_code=500,
            detail=f"Failed to validate invoice: {str(exc)}"
        )


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "agent": "validation_agent"
    }

