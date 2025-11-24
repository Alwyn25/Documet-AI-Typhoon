from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal

# --- Status Enum for Workflow Gating ---
StatusEnum = Literal[
    "UPLOADED", "UPLOADED_METADATA_SAVED", "FAILED_INGESTION",
    "OCR_DONE", "FAILED_OCR",
    "MAPPING_COMPLETE", "FAILED_MAPPING",
    "VALIDATED_CLEAN", "VALIDATED_FLAGGED",
    "SYNCED_SUCCESS", "FAILED_SYNC", "DB_RECORD_SAVED"
]

# --- Canonical Invoice Schema (for data interchange) ---

class Vendor(BaseModel):
    name: Optional[str] = None
    gstin: Optional[str] = None
    pan: Optional[str] = None
    address: Optional[str] = None

class LineItem(BaseModel):
    description: str
    qty: float
    unit_price: float
    tax_pct: Optional[float] = None
    amount: float
    hsn: Optional[str] = None

class Totals(BaseModel):
    subtotal: float
    tax_total: Optional[float] = None
    grand_total: float
    round_off: Optional[float] = None

class CanonicalInvoice(BaseModel):
    """The detailed, canonical schema for an extracted invoice."""
    invoice_no: str
    invoice_date: str
    due_date: Optional[str] = None
    vendor: Vendor
    items: List[LineItem]
    totals: Totals

# --- Validation Result Schema ---

class ValidationRuleResult(BaseModel):
    rule_id: str
    status: Literal["PASS", "FAIL", "WARN"]
    message: Optional[str] = None
    severity: int
    deduction_points: float

class ValidationReport(BaseModel):
    invoice_id: str
    overall_score: float
    status: Literal["PASS", "FAIL", "WARN"]
    rules: List[ValidationRuleResult]

# --- LangGraph State Model ---

class InvoiceGraphState(BaseModel):
    """Represents the state of the invoice processing workflow."""

    user_id: str
    file_content: bytes
    original_filename: str

    file_path: Optional[str] = None
    mongo_document_id: Optional[str] = None
    ocr_output: Optional[Dict[str, Any]] = None

    # This will hold the rich, canonical invoice data after mapping
    canonical_invoice: Optional[CanonicalInvoice] = None

    validation_report: Optional[ValidationReport] = None

    # The final, ERP-ready mapped payload
    erp_payload: Optional[Dict[str, Any]] = None

    current_status: StatusEnum
    error_message: Optional[str] = None
