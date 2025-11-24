from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal

# --- Invoice Processing Protocol ---
# This defines the fields that will be passed between agents and tracked in the state.

StatusEnum = Literal[
    "UPLOADED", "UPLOADED_METADATA_SAVED", "FAILED_INGESTION",
    "OCR_DONE", "FAILED_OCR",
    "MAPPED", "MAPPING_COMPLETE", "FAILED_MAPPING",
    "VALIDATED_CLEAN", "VALIDATED_FLAGGED",
    "SYNCED_SUCCESS", "FAILED_SYNC",
    "DUPLICATE_FOUND", "UNIQUE_RECORD",
    "DB_RECORD_SAVED", "FAILED_DB_SAVE"
]

class InvoiceProcessingProtocol(BaseModel):
    user_id: str
    file_path: str
    extracted_text: Optional[str] = None
    mapped_schema: Optional[Dict[str, Any]] = None
    validation_flags: List[str] = Field(default_factory=list)
    status: StatusEnum

# --- LangGraph State Model ---

class InvoiceGraphState(BaseModel):
    """Represents the state of the invoice processing workflow."""

    # Input data
    user_id: str
    file_path: str

    # State after each agent's execution
    mongo_document_id: Optional[str] = None
    extracted_text: Optional[str] = None
    mapped_schema: Optional[Dict[str, Any]] = None
    validation_flags: List[str] = Field(default_factory=list)

    # The current status, used for gating and routing
    current_status: StatusEnum

    # Error handling
    error_message: Optional[str] = None

# --- Agent-specific Data Models ---

class ExtractedInvoice(BaseModel):
    """A simplified model for what the OCR agent might produce."""
    invoice_no: str
    invoice_date: str
    total_amount: float
    raw_text: str

class ValidatedRecord(BaseModel):
    """A model for the final, validated record to be saved in PostgreSQL."""
    user_id: str
    invoice_no: str
    invoice_date: str
    total_amount: float
    is_flagged: bool
    validation_flags: List[str]
    # ... other structured fields
