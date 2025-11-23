from typing import List, Optional, Literal
from pydantic import BaseModel


class Vendor(BaseModel):
    name: Optional[str] = None
    gstin: Optional[str] = None
    pan: Optional[str] = None
    address: Optional[str] = None


class Customer(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None


class LineItem(BaseModel):
    description: str
    quantity: float
    unitPrice: float
    taxPercent: float
    amount: float


class Totals(BaseModel):
    subtotal: float
    gstAmount: float
    roundOff: Optional[float] = None
    grandTotal: float


class PaymentDetails(BaseModel):
    mode: Optional[str] = None
    reference: Optional[str] = None
    status: Optional[Literal["Paid", "Unpaid", "Partial"]] = None


class InvoiceSchema(BaseModel):
    invoiceNumber: Optional[str] = None
    invoiceDate: Optional[str] = None
    dueDate: Optional[str] = None
    vendor: Vendor
    customer: Customer
    lineItems: List[LineItem]
    totals: Totals
    paymentDetails: PaymentDetails


class ValidationError(BaseModel):
    field: str
    issue: str
    suggestion: Optional[str] = None


class ValidationWarning(BaseModel):
    field: str
    message: str


class ValidationResult(BaseModel):
    isValid: bool
    errors: List[ValidationError]
    warnings: List[ValidationWarning]


class SchemaMappingRequest(BaseModel):
    ocr_text: str
    schema_type: str = "invoice"


class SchemaMappingResponse(BaseModel):
    success: bool
    message: str
    document_id: Optional[str] = None
    invoice_id: Optional[int] = None
    extracted_schema: Optional[InvoiceSchema] = None
    validation_result: Optional[ValidationResult] = None

