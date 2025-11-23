import json
import uuid
from typing import Dict, Any, Optional

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from ..config import settings
from ..models.schemas import InvoiceSchema, ValidationResult
from ..prompts.extraction import EXTRACTION_SCHEMA_PROMPT
from ..prompts.validation import VALIDATION_SCHEMA_PROMPT
from ..utils.logging import logger


class SchemaMappingService:
    """Service for extracting structured schemas from OCR text using LLM"""

    def __init__(self):
        self.client = None
        api_key = settings.OPENAI_API_KEY.strip() if settings.OPENAI_API_KEY else ""
        if OPENAI_AVAILABLE and api_key:
            try:
                self.client = OpenAI(api_key=api_key)
                logger.log_step("openai_client_initialized", {
                    "model": settings.LLM_MODEL,
                    "status": "success",
                    "api_key_length": len(api_key)
                })
            except Exception as e:
                logger.log_error("openai_client_init_failed", {"error": str(e)})
        else:
            logger.log_step("openai_client_not_available", {
                "message": "OpenAI client not available or API key not set",
                "openai_available": OPENAI_AVAILABLE,
                "api_key_set": bool(api_key)
            })

    def _ensure_client(self):
        """Ensure OpenAI client is initialized, re-initialize if needed"""
        if self.client:
            return
        
        api_key = settings.OPENAI_API_KEY.strip() if settings.OPENAI_API_KEY else ""
        logger.log_step("checking_openai_client", {
            "openai_available": OPENAI_AVAILABLE,
            "api_key_present": bool(settings.OPENAI_API_KEY),
            "api_key_length": len(api_key) if api_key else 0,
            "api_key_preview": api_key[:10] + "..." if api_key and len(api_key) > 10 else "N/A"
        })
        
        if OPENAI_AVAILABLE and api_key:
            try:
                # Simple initialization - just pass the API key
                # If there are proxy issues, they should be handled by the library
                self.client = OpenAI(api_key=api_key)
                logger.log_step("openai_client_initialized", {
                    "model": settings.LLM_MODEL,
                    "status": "success",
                    "api_key_length": len(api_key)
                })
            except Exception as e:
                error_msg = str(e)
                logger.log_error("openai_client_init_failed", {
                    "error": error_msg,
                    "error_type": type(e).__name__
                })
                # If it's a proxies error, provide helpful message
                if "proxies" in error_msg.lower():
                    raise ValueError(
                        "OpenAI client initialization failed due to proxy configuration. "
                        "Please check your HTTP_PROXY/HTTPS_PROXY environment variables or update the OpenAI library."
                    )
                raise ValueError(f"Failed to initialize OpenAI client: {error_msg}")
        else:
            raise ValueError("OpenAI client not initialized. Please set OPENAI_API_KEY.")

    async def extract_schema(self, ocr_text: str, schema_type: str = "invoice") -> Dict[str, Any]:
        """
        Extract structured schema from OCR text using LLM
        
        Args:
            ocr_text: The OCR-extracted text from the document
            schema_type: Type of schema to extract (default: "invoice")
        
        Returns:
            Dictionary containing extracted schema and metadata
        """
        document_id = uuid.uuid4().hex
        
        logger.log_extraction(document_id, schema_type)
        
        # Ensure client is initialized (lazy initialization)
        self._ensure_client()
        
        if not ocr_text or not ocr_text.strip():
            raise ValueError("OCR text cannot be empty.")
        
        try:
            # Prepare the extraction prompt
            system_prompt = EXTRACTION_SCHEMA_PROMPT
            user_prompt = f"Extract invoice information from the following OCR text:\n\n{ocr_text}"
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=settings.LLM_TEMPERATURE,
                response_format={"type": "json_object"}
            )
            
            # Extract JSON from response
            extracted_json_str = response.choices[0].message.content.strip()
            
            # Remove markdown code blocks if present
            if extracted_json_str.startswith("```json"):
                extracted_json_str = extracted_json_str[7:]
            if extracted_json_str.startswith("```"):
                extracted_json_str = extracted_json_str[3:]
            if extracted_json_str.endswith("```"):
                extracted_json_str = extracted_json_str[:-3]
            extracted_json_str = extracted_json_str.strip()
            
            # Parse JSON
            extracted_data = json.loads(extracted_json_str)
            
            # Validate against schema
            try:
                invoice_schema = InvoiceSchema(**extracted_data)
                logger.log_step("schema_extraction_completed", {
                    "document_id": document_id,
                    "status": "success"
                })
                
                return {
                    "document_id": document_id,
                    "extracted_schema": invoice_schema.model_dump(),
                    "raw_json": extracted_data
                }
            except Exception as validation_error:
                logger.log_error("schema_validation_failed", {
                    "document_id": document_id,
                    "error": str(validation_error)
                })
                # Return raw data even if validation fails
                return {
                    "document_id": document_id,
                    "extracted_schema": extracted_data,
                    "raw_json": extracted_data,
                    "validation_warning": f"Schema validation failed: {str(validation_error)}"
                }
                
        except json.JSONDecodeError as e:
            logger.log_error("json_parse_failed", {
                "document_id": document_id,
                "error": str(e)
            })
            raise ValueError(f"Failed to parse extracted JSON: {str(e)}")
        except Exception as e:
            logger.log_error("schema_extraction_failed", {
                "document_id": document_id,
                "error": str(e)
            })
            raise

    async def validate_schema(self, extracted_schema: Dict[str, Any]) -> ValidationResult:
        """
        Validate extracted schema for consistency and correctness
        
        Args:
            extracted_schema: The extracted schema dictionary
        
        Returns:
            ValidationResult with errors and warnings
        """
        errors = []
        warnings = []
        
        try:
            # Convert to InvoiceSchema for validation
            invoice = InvoiceSchema(**extracted_schema)
            
            # Validate line items calculations
            for idx, item in enumerate(invoice.lineItems):
                expected_amount = item.quantity * item.unitPrice * (1 + item.taxPercent / 100)
                if abs(item.amount - expected_amount) > 0.01:  # Allow small floating point differences
                    errors.append({
                        "field": f"lineItems[{idx}].amount",
                        "issue": f"Amount mismatch. Expected: {expected_amount:.2f}, Got: {item.amount}",
                        "suggestion": f"Set amount to {expected_amount:.2f}"
                    })
            
            # Validate totals
            calculated_subtotal = sum(item.amount / (1 + item.taxPercent / 100) for item in invoice.lineItems)
            calculated_gst = sum(item.amount - (item.amount / (1 + item.taxPercent / 100)) for item in invoice.lineItems)
            
            round_off = invoice.totals.roundOff or 0
            calculated_total = invoice.totals.subtotal + invoice.totals.gstAmount + round_off
            
            if abs(invoice.totals.grandTotal - calculated_total) > 0.01:
                errors.append({
                    "field": "totals.grandTotal",
                    "issue": f"Grand total mismatch. Expected: {calculated_total:.2f}, Got: {invoice.totals.grandTotal}",
                    "suggestion": f"Set grandTotal to {calculated_total:.2f}"
                })
            
            # Check for missing critical fields
            if not invoice.invoiceNumber:
                warnings.append({
                    "field": "invoiceNumber",
                    "message": "Invoice number is missing"
                })
            
            if not invoice.invoiceDate:
                warnings.append({
                    "field": "invoiceDate",
                    "message": "Invoice date is missing"
                })
            
            if not invoice.vendor.name:
                warnings.append({
                    "field": "vendor.name",
                    "message": "Vendor name is missing"
                })
            
            is_valid = len(errors) == 0
            
            logger.log_validation("validation_document", is_valid)
            
            return ValidationResult(
                isValid=is_valid,
                errors=errors,
                warnings=warnings
            )
            
        except Exception as e:
            logger.log_error("schema_validation_exception", {"error": str(e)})
            return ValidationResult(
                isValid=False,
                errors=[{
                    "field": "schema",
                    "issue": f"Schema validation exception: {str(e)}",
                    "suggestion": None
                }],
                warnings=[]
            )


# Global service instance
schema_mapping_service = SchemaMappingService()

