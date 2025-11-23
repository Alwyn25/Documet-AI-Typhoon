
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# --- Pydantic Models for Internal State Management ---

class ItemDetail(BaseModel):
    """Represents a single line item within an invoice."""
    item_description: str
    unit_price: float
    quantity: float

class ExtractedInvoiceData(BaseModel):
    """Contains the core data extracted from an invoice document."""
    invoice_no: str
    vendor_gstin: str
    total_amount: float
    item_details: List[ItemDetail]
    confidence_score: float

class MappedSchema(BaseModel):
    """Holds the invoice data mapped to different accounting schemas."""
    tallyprime_schema: Dict[str, Any]
    zoho_books_schema: Dict[str, Any]

class ValidationResult(BaseModel):
    """Result from the validation agent."""
    validation_status: str  # e.g., "SUCCESS", "ANOMALY"
    anomaly_flags: List[str] = Field(default_factory=list)

class ValidatedInvoiceRecord(BaseModel):
    """The final, validated record that will be stored."""
    extracted_data: ExtractedInvoiceData
    validation_status: str
    anomaly_flags: List[str]
    accounting_system_schema: str # This will be a JSON string of MappedSchema

class StoreRequest(BaseModel):
    """The request message for the DataStore service."""
    validated_record: ValidatedInvoiceRecord
    raw_file_ref: str

class StoreResult(BaseModel):
    """The response message from the DataStore service."""
    success: bool
    message: str
