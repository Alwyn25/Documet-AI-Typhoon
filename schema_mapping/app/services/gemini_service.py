import base64
import json
import uuid
from typing import Any, Dict, List

import google.generativeai as genai  # type: ignore[import-not-found]
from fastapi.concurrency import run_in_threadpool

from ..config import settings
from ..models.schemas import InvoiceSchema, ValidationError, ValidationResult, ValidationWarning
from ..utils.logging import logger


EXTRACTION_PROMPT = """
You are an expert OCR and data extraction agent specializing in invoices. Analyze the attached invoice image or PDF and extract the following information in a structured JSON format.
Do not include any explanatory text, markdown formatting, or anything else, only the raw JSON object. If a field is not present, use a value of null.

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

VALIDATION_PROMPT = """
You are an expert anomaly detection agent for accounting. Analyze the following invoice JSON data. Identify any inconsistencies, missing critical information, or calculation errors.

Perform these checks:
1. Missing Critical Fields: Check if 'invoiceNumber', 'invoiceDate', 'vendor.name', or 'totals.grandTotal' are null or empty.
2. Duplicate Check (Simulated): Based on the data, state if this could be a duplicate. For this simulation, flag as a potential duplicate if the invoice date is within the last 30 days.
3. Calculation Validation: Verify that the sum of all 'lineItems.amount' equals 'totals.subtotal'.
4. Grand Total Check: Verify that 'totals.subtotal' + 'totals.gstAmount' + (optional 'totals.roundOff' or 0) equals 'totals.grandTotal'. Allow minor floating point discrepancies.

Return your findings as a JSON array of objects. Each object should have a "type" ('error' or 'warning') and a "message". If there are no issues, return an empty array [].
"""


class GeminiInvoiceService:
    def __init__(self) -> None:
        self.model_name = settings.GEMINI_MODEL or "gemini-2.0-flash"
        self._model = None
        self._api_key = None

    def _ensure_client(self):
        # Lazy initialization - reload API key each time to pick up changes
        api_key = settings.GEMINI_API_KEY.strip() if settings.GEMINI_API_KEY else ""
        
        if not api_key:
            logger.log_error("gemini_api_key_missing", {"message": "GEMINI_API_KEY is not configured"})
            raise ValueError("GEMINI_API_KEY is not configured. Please set it in your .env file.")
        
        # Re-initialize if API key changed or model not initialized
        if self._api_key != api_key or self._model is None:
            logger.log_step("gemini_client_initializing", {
                "model": self.model_name,
                "api_key_length": len(api_key),
                "api_key_preview": api_key[:10] + "..." if len(api_key) > 10 else "N/A"
            })
            try:
                genai.configure(api_key=api_key)
                self._model = genai.GenerativeModel(self.model_name)
                self._api_key = api_key
                logger.log_step("gemini_client_initialized", {
                    "model": self.model_name,
                    "status": "success"
                })
            except Exception as e:
                error_msg = str(e)
                logger.log_error("gemini_client_init_failed", {
                    "error": error_msg,
                    "error_type": type(e).__name__
                })
                if "API_KEY" in error_msg or "expired" in error_msg.lower() or "invalid" in error_msg.lower():
                    raise ValueError(
                        f"Gemini API key is invalid or expired. Please check your GEMINI_API_KEY in the .env file. "
                        f"Error: {error_msg}"
                    )
                raise ValueError(f"Failed to initialize Gemini client: {error_msg}")

    @staticmethod
    def _file_to_inline_part(file_bytes: bytes, mime_type: str) -> Dict[str, Any]:
        encoded = base64.b64encode(file_bytes).decode("utf-8")
        return {
            "inline_data": {
                "mime_type": mime_type or "application/octet-stream",
                "data": encoded,
            }
        }

    async def extract_invoice_schema(self, file_bytes: bytes, mime_type: str) -> InvoiceSchema:
        self._ensure_client()

        def _run():
            try:
                response = self._model.generate_content(
                    contents=[
                        {
                            "role": "user",
                            "parts": [
                                self._file_to_inline_part(file_bytes, mime_type),
                                {"text": EXTRACTION_PROMPT}
                            ]
                        }
                    ]
                )
                text = (response.text or "").replace("```json", "").replace("```", "").strip()
                if not text:
                    raise ValueError("Gemini returned empty response for extraction.")
                import json
                data = json.loads(text)
                return InvoiceSchema(**data)
            except Exception as e:
                error_msg = str(e)
                # Check for API key errors
                if "API_KEY" in error_msg or "expired" in error_msg.lower() or "invalid" in error_msg.lower():
                    raise ValueError(
                        f"Gemini API key error: {error_msg}. "
                        f"Please verify your GEMINI_API_KEY in the .env file is valid and not expired."
                    )
                raise

        return await run_in_threadpool(_run)

    async def validate_invoice_schema(self, invoice_schema: InvoiceSchema) -> ValidationResult:
        self._ensure_client()

        def _run():
            prompt = f"{VALIDATION_PROMPT}\n\nInvoice Data:\n{invoice_schema.model_dump_json(indent=2)}"
            response = self._model.generate_content(prompt)
            text = (response.text or "").replace("```json", "").replace("```", "").strip()
            try:
                findings = json.loads(text) if text else []
            except json.JSONDecodeError:
                findings = []
            if not isinstance(findings, list):
                findings = []
            errors: List[ValidationError] = []
            warnings: List[ValidationWarning] = []
            for finding in findings:
                finding_type = (finding.get("type") or "warning").lower()
                message = finding.get("message") or "Unknown issue"
                if finding_type == "error":
                    errors.append(ValidationError(field="general", issue=message))
                else:
                    warnings.append(ValidationWarning(field="general", message=message))
            return ValidationResult(isValid=len(errors) == 0, errors=errors, warnings=warnings)

        return await run_in_threadpool(_run)


gemini_invoice_service = GeminiInvoiceService()

