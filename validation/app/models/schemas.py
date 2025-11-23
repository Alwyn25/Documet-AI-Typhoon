"""Validation service models"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel


class Vendor(BaseModel):
    """Vendor information model"""
    name: Optional[str] = None
    gstin: Optional[str] = None
    pan: Optional[str] = None
    address: Optional[str] = None


class Customer(BaseModel):
    """Customer information model"""
    name: Optional[str] = None
    address: Optional[str] = None


class LineItem(BaseModel):
    """Line item model"""
    description: str
    quantity: float
    unitPrice: float
    taxPercent: float
    amount: float


class Totals(BaseModel):
    """Totals model"""
    subtotal: float
    gstAmount: float
    roundOff: Optional[float] = None
    grandTotal: float


class PaymentDetails(BaseModel):
    """Payment details model"""
    mode: Optional[str] = None
    reference: Optional[str] = None
    status: Optional[Literal["Paid", "Unpaid", "Partial"]] = None


class InvoiceSchema(BaseModel):
    """Invoice schema model matching extraction prompt structure"""
    invoiceNumber: Optional[str] = None
    invoiceDate: Optional[str] = None
    dueDate: Optional[str] = None
    vendor: Vendor
    customer: Customer
    lineItems: List[LineItem]
    totals: Totals
    paymentDetails: PaymentDetails


class EntityComparison(BaseModel):
    """Comparison result for a single entity"""
    entity_type: str  # e.g., "invoice", "vendor", "customer", "items", "totals", "payment"
    exists_in_db: bool
    is_identical: bool
    differences: List[Dict[str, Any]]  # List of field differences
    existing_data: Optional[Dict[str, Any]] = None
    new_data: Optional[Dict[str, Any]] = None


class ValidationRequest(BaseModel):
    """Request model for validation - accepts InvoiceSchema structure"""
    invoiceNumber: Optional[str] = None
    invoiceDate: Optional[str] = None
    dueDate: Optional[str] = None
    vendor: Vendor
    customer: Customer
    lineItems: List[LineItem]
    totals: Totals
    paymentDetails: PaymentDetails


class ValidationSummary(BaseModel):
    """LLM-generated validation summary"""
    summary: str  # Overall summary text
    errors: List[str]  # List of error bullet points
    warnings: List[str]  # List of warning bullet points
    severity: Literal["critical", "moderate", "minor", "none"]


class ValidationResponse(BaseModel):
    """Response model for validation"""
    success: bool
    message: str
    invoice_exists: bool
    invoice_id: Optional[int] = None
    duplicate_by_criteria: bool = False
    comparisons: List[EntityComparison]
    summary: Dict[str, Any]  # Summary statistics
    missing_value_checks: Optional[Dict[str, List[Dict[str, Any]]]] = None
    tax_validation_errors: Optional[List[Dict[str, Any]]] = None
    llm_summary: Optional[ValidationSummary] = None  # LLM-generated summary

