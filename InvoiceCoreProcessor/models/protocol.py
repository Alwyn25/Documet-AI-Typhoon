from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date, datetime


class InvoiceIngestionRequest(BaseModel):
    raw_file_ref: str = Field(..., description="MongoDB ref or cloud storage path")
    user_id: str


class ItemDetail(BaseModel):
    description: str = Field(..., description="Description of the item/service.")
    quantity: float = Field(..., gt=0, description="Quantity of the item.")
    unit_price: float = Field(..., ge=0, description="Price per unit (Rate).")
    tax_percentage: float = Field(..., ge=0, le=100, description="Applicable GST/Tax percentage.")
    taxable_amount: float = Field(..., ge=0, description="Quantity * Unit Price.")
    calculated_tax: float = Field(..., ge=0, description="Taxable Amount * Tax Percentage.")
    total_amount: float = Field(..., ge=0, description="Taxable Amount + Calculated Tax.")


class ExtractedInvoiceData(BaseModel):
    # Core Invoice Details
    invoice_no: str = Field(..., min_length=1)
    invoice_date: date
    due_date: Optional[date] = None

    # Vendor/Customer Info
    vendor_name: str
    vendor_gstin: Optional[str] = Field(None, min_length=15, max_length=15)  # Required for validation

    # Financial Totals (as extracted, before rounding/validation)
    extracted_subtotal: float = Field(..., ge=0)
    extracted_tax_amount: float = Field(..., ge=0)
    extracted_total_amount: float = Field(..., ge=0)  # Grand Total

    # Items
    item_details: List[ItemDetail]

    # Metadata
    confidence_score: float = Field(..., ge=0, le=1.0)
    document_ref: str = Field(..., description="MongoDB/Cloud Storage ID of the raw file.")


class Anomaly(BaseModel):
    flag_type: str = Field(..., description="e.g., 'DUPLICATE_FOUND', 'TAX_MISMATCH'")
    message: str


class AccountingSchema(BaseModel):
    # Representative simplified target schema for Tally/Zoho posting
    txn_date: date
    contact_name: str
    gstin: str
    line_items_data: List[dict]  # Simplified list of items for API payload
    taxable_subtotal: float
    total_tax_amount: float
    grand_total: float
    # Other optional fields: payment_mode, reference_no, etc.


class ValidatedInvoiceRecord(BaseModel):
    # Base Data
    upload_timestamp: datetime
    extracted_data: Optional[ExtractedInvoiceData] = None

    # Validation Results
    validation_status: str = "PENDING"  # SUCCESS, ANOMALY, ERROR
    anomaly_flags: List[Anomaly] = Field(default_factory=list)
    review_required: bool = False

    # Mapped Data
    accounting_system_schema: Optional[AccountingSchema] = None

    # Using str here for simplicity
    file_id: str

    # PostgreSQL-specific ID for persistence
    db_id: Optional[int] = None
