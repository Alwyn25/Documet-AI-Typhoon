"""Validation service for comparing entities with PostgreSQL database"""

from typing import Dict, Any, List, Optional
from decimal import Decimal
from datetime import datetime, date
import json
import re

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from ..utils.database import db_manager
from ..utils.logging import logger
from ..config import settings
from ..models.schemas import (
    EntityComparison, 
    ValidationRequest,
    ValidationSummary,
    Vendor,
    Customer,
    LineItem,
    Totals,
    PaymentDetails
)
from ..prompts.summarization import VALIDATION_SUMMARY_PROMPT


def parse_date(date_str: Optional[str]) -> Optional[date]:
    """
    Parse date string into Python date object.
    Handles various date formats like:
    - '04-Mar-2020'
    - '2020-03-04'
    - '03/04/2020'
    - '2020/03/04'
    - ISO format dates
    """
    if not date_str or not isinstance(date_str, str):
        return None
    
    date_str = date_str.strip()
    if not date_str or date_str.lower() in ('null', 'none', ''):
        return None
    
    # Try common date formats
    date_formats = [
        '%Y-%m-%d',           # 2020-03-04
        '%d-%m-%Y',            # 04-03-2020
        '%m/%d/%Y',            # 03/04/2020
        '%d/%m/%Y',            # 04/03/2020
        '%Y/%m/%d',            # 2020/03/04
        '%d-%b-%Y',            # 04-Mar-2020
        '%d-%B-%Y',            # 04-March-2020
        '%b %d, %Y',           # Mar 04, 2020
        '%B %d, %Y',           # March 04, 2020
        '%d %b %Y',            # 04 Mar 2020
        '%d %B %Y',            # 04 March 2020
        '%Y-%m-%dT%H:%M:%S',   # ISO with time
        '%Y-%m-%dT%H:%M:%SZ',  # ISO with time and Z
    ]
    
    for fmt in date_formats:
        try:
            parsed = datetime.strptime(date_str, fmt)
            return parsed.date()
        except (ValueError, TypeError):
            continue
    
    # Try to extract date from strings like "04-Mar-2020" with regex
    # Pattern: DD-MMM-YYYY or DD-Month-YYYY
    month_map = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }
    
    # Match patterns like: 04-Mar-2020, 4-Mar-2020, 04-March-2020
    pattern = r'(\d{1,2})[-/](\w{3,9})[-/](\d{4})'
    match = re.match(pattern, date_str, re.IGNORECASE)
    if match:
        try:
            day = int(match.group(1))
            month_str = match.group(2).lower()[:3]  # First 3 chars
            year = int(match.group(3))
            
            if month_str in month_map:
                month = month_map[month_str]
                return date(year, month, day)
        except (ValueError, KeyError):
            pass
    
    # If all parsing fails, return None
    return None


def normalize_date_for_comparison(date_value: Optional[Any]) -> Optional[str]:
    """
    Normalize date value to ISO format string for comparison.
    Handles date objects, date strings, and None values.
    """
    if date_value is None:
        return None
    
    # If it's already a date object, convert to string
    if isinstance(date_value, date):
        return date_value.isoformat()
    
    # If it's a string, parse and normalize
    if isinstance(date_value, str):
        parsed_date = parse_date(date_value)
        if parsed_date:
            return parsed_date.isoformat()
        return date_value  # Return original if parsing fails
    
    # If it's a datetime, extract date
    if isinstance(date_value, datetime):
        return date_value.date().isoformat()
    
    return str(date_value) if date_value else None


class ValidationService:
    """Service for validating and comparing invoice entities with database"""

    def __init__(self):
        self.client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize OpenAI client if API key is available"""
        api_key = settings.OPENAI_API_KEY.strip() if settings.OPENAI_API_KEY else ""
        if OPENAI_AVAILABLE and api_key:
            try:
                self.client = OpenAI(api_key=api_key)
                logger.log_step("openai_client_initialized", {
                    "model": settings.LLM_MODEL if hasattr(settings, 'LLM_MODEL') else "gpt-4o-mini",
                    "status": "success"
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
        """Ensure OpenAI client is initialized"""
        if self.client:
            return
        
        api_key = settings.OPENAI_API_KEY.strip() if settings.OPENAI_API_KEY else ""
        if OPENAI_AVAILABLE and api_key:
            try:
                self.client = OpenAI(api_key=api_key)
            except Exception as e:
                logger.log_error("openai_client_init_failed", {"error": str(e)})
                raise ValueError(f"Failed to initialize OpenAI client: {str(e)}")
        else:
            raise ValueError("OpenAI client not initialized. Please set OPENAI_API_KEY.")

    async def validate_invoice(self, request: ValidationRequest) -> Dict[str, Any]:
        """
        Validate invoice by checking if it exists in database and comparing all entities
        
        Args:
            request: ValidationRequest with invoice data to validate (InvoiceSchema structure)
            
        Returns:
            Dictionary with validation results including comparisons
        """
        logger.log_step("validation_request_received", {
            "invoice_number": request.invoiceNumber
        })
        
        comparisons: List[EntityComparison] = []
        invoice_id = None
        invoice_exists = False
        duplicate_by_criteria = False
        
        try:
            async with db_manager.get_connection() as conn:
                # Check for missing/inconsistent values first
                missing_value_checks = self._check_missing_values(request)
                
                # Check for duplicate by invoice number + vendor + date (even if invoice number search fails)
                if request.invoiceNumber and request.vendor.name and request.invoiceDate:
                    new_vendor_name = (request.vendor.name or '').strip().lower()
                    parsed_date = parse_date(request.invoiceDate)
                    
                    if new_vendor_name and parsed_date:
                        # Search for invoices with same invoice number + vendor name + date
                        duplicate_check = await conn.fetchrow("""
                            SELECT i.invoice_id, i.invoice_number, i.invoice_date, v.name as vendor_name
                            FROM invoice i
                            JOIN vendorinfo v ON i.invoice_id = v.invoice_id
                            WHERE i.invoice_number = $1
                            AND LOWER(TRIM(v.name)) = $2
                            AND i.invoice_date = $3
                        """, request.invoiceNumber, new_vendor_name, parsed_date)
                        
                        if duplicate_check:
                            duplicate_by_criteria = True
                            logger.log_step("duplicate_detected_by_criteria", {
                                "invoice_number": request.invoiceNumber,
                                "vendor_name": new_vendor_name,
                                "invoice_date": str(parsed_date),
                                "existing_invoice_id": duplicate_check['invoice_id']
                            })
                
                # Check if invoice exists by invoice_number
                if request.invoiceNumber:
                    invoice_record = await conn.fetchrow("""
                        SELECT invoice_id, invoice_number, invoice_date, due_date
                        FROM invoice
                        WHERE invoice_number = $1
                    """, request.invoiceNumber)
                    
                    if invoice_record:
                        invoice_exists = True
                        invoice_id = invoice_record['invoice_id']
                        logger.log_step("invoice_found_in_db", {
                            "invoice_id": invoice_id,
                            "invoice_number": request.invoiceNumber
                        })
                        
                        # Compare invoice basic info
                        try:
                            invoice_comparison = await self._compare_invoice(
                                conn, invoice_id, request
                            )
                            comparisons.append(invoice_comparison)
                            logger.log_step("invoice_comparison_completed", {
                                "is_identical": invoice_comparison.is_identical,
                                "differences_count": len(invoice_comparison.differences)
                            })
                        except Exception as e:
                            logger.log_error("invoice_comparison_failed", {
                                "error": str(e),
                                "invoice_id": invoice_id
                            })
                            # Add fallback comparison
                            comparisons.append(EntityComparison(
                                entity_type="invoice",
                                exists_in_db=True,
                                is_identical=False,
                                differences=[{"field": "comparison_error", "issue": str(e)}],
                                existing_data=None,
                                new_data={"invoiceNumber": request.invoiceNumber}
                            ))
                        
                        # Compare vendor info
                        try:
                            vendor_comparison = await self._compare_vendor(
                                conn, invoice_id, request.vendor
                            )
                            comparisons.append(vendor_comparison)
                            logger.log_step("vendor_comparison_completed", {
                                "is_identical": vendor_comparison.is_identical,
                                "differences_count": len(vendor_comparison.differences)
                            })
                        except Exception as e:
                            logger.log_error("vendor_comparison_failed", {
                                "error": str(e),
                                "invoice_id": invoice_id
                            })
                            comparisons.append(EntityComparison(
                                entity_type="vendor",
                                exists_in_db=True,
                                is_identical=False,
                                differences=[{"field": "comparison_error", "issue": str(e)}],
                                existing_data=None,
                                new_data={"name": request.vendor.name}
                            ))
                        
                        # Compare customer info
                        try:
                            customer_comparison = await self._compare_customer(
                                conn, invoice_id, request.customer
                            )
                            comparisons.append(customer_comparison)
                            logger.log_step("customer_comparison_completed", {
                                "is_identical": customer_comparison.is_identical,
                                "differences_count": len(customer_comparison.differences)
                            })
                        except Exception as e:
                            logger.log_error("customer_comparison_failed", {
                                "error": str(e),
                                "invoice_id": invoice_id
                            })
                            comparisons.append(EntityComparison(
                                entity_type="customer",
                                exists_in_db=True,
                                is_identical=False,
                                differences=[{"field": "comparison_error", "issue": str(e)}],
                                existing_data=None,
                                new_data={"name": request.customer.name}
                            ))
                        
                        # Compare line items
                        try:
                            items_comparison = await self._compare_line_items(
                                conn, invoice_id, request.lineItems
                            )
                            comparisons.append(items_comparison)
                            logger.log_step("line_items_comparison_completed", {
                                "is_identical": items_comparison.is_identical,
                                "differences_count": len(items_comparison.differences),
                                "exists_in_db": items_comparison.exists_in_db
                            })
                        except Exception as e:
                            logger.log_error("line_items_comparison_failed", {
                                "error": str(e),
                                "invoice_id": invoice_id
                            })
                            comparisons.append(EntityComparison(
                                entity_type="line_items",
                                exists_in_db=True,
                                is_identical=False,
                                differences=[{"field": "comparison_error", "issue": str(e)}],
                                existing_data=None,
                                new_data={"count": len(request.lineItems)}
                            ))
                        
                        # Compare totals
                        try:
                            totals_comparison = await self._compare_totals(
                                conn, invoice_id, request.totals
                            )
                            comparisons.append(totals_comparison)
                            logger.log_step("totals_comparison_completed", {
                                "is_identical": totals_comparison.is_identical,
                                "differences_count": len(totals_comparison.differences)
                            })
                        except Exception as e:
                            logger.log_error("totals_comparison_failed", {
                                "error": str(e),
                                "invoice_id": invoice_id
                            })
                            comparisons.append(EntityComparison(
                                entity_type="totals",
                                exists_in_db=True,
                                is_identical=False,
                                differences=[{"field": "comparison_error", "issue": str(e)}],
                                existing_data=None,
                                new_data={"grandTotal": request.totals.grandTotal}
                            ))
                        
                        # Compare payment details
                        try:
                            payment_comparison = await self._compare_payment(
                                conn, invoice_id, request.paymentDetails
                            )
                            comparisons.append(payment_comparison)
                            logger.log_step("payment_comparison_completed", {
                                "is_identical": payment_comparison.is_identical,
                                "differences_count": len(payment_comparison.differences)
                            })
                        except Exception as e:
                            logger.log_error("payment_comparison_failed", {
                                "error": str(e),
                                "invoice_id": invoice_id
                            })
                            comparisons.append(EntityComparison(
                                entity_type="payment",
                                exists_in_db=True,
                                is_identical=False,
                                differences=[{"field": "comparison_error", "issue": str(e)}],
                                existing_data=None,
                                new_data={"status": request.paymentDetails.status}
                            ))
                    else:
                        logger.log_step("invoice_not_found_in_db", {
                            "invoice_number": request.invoiceNumber
                        })
                        # Invoice doesn't exist, all entities are new
                        # Still add comparisons for all entities to show what would be new
                        comparisons.append(EntityComparison(
                            entity_type="invoice",
                            exists_in_db=False,
                            is_identical=False,
                            differences=[],
                            existing_data=None,
                            new_data={
                                "invoiceNumber": request.invoiceNumber,
                                "invoiceDate": request.invoiceDate,
                                "dueDate": request.dueDate
                            }
                        ))
                        
                        # Add comparisons for all other entities even though invoice doesn't exist
                        # This helps show what data would be new
                        comparisons.append(EntityComparison(
                            entity_type="vendor",
                            exists_in_db=False,
                            is_identical=False,
                            differences=[],
                            existing_data=None,
                            new_data={
                                "name": request.vendor.name,
                                "gstin": request.vendor.gstin,
                                "pan": request.vendor.pan,
                                "address": request.vendor.address
                            }
                        ))
                        
                        comparisons.append(EntityComparison(
                            entity_type="customer",
                            exists_in_db=False,
                            is_identical=False,
                            differences=[],
                            existing_data=None,
                            new_data={
                                "name": request.customer.name,
                                "address": request.customer.address
                            }
                        ))
                        
                        comparisons.append(EntityComparison(
                            entity_type="line_items",
                            exists_in_db=False,
                            is_identical=False,
                            differences=[],
                            existing_data=None,
                            new_data={
                                "count": len(request.lineItems),
                                "items": [
                                    {
                                        "description": item.description,
                                        "quantity": item.quantity,
                                        "unitPrice": item.unitPrice,
                                        "taxPercent": item.taxPercent,
                                        "amount": item.amount
                                    }
                                    for item in request.lineItems
                                ]
                            }
                        ))
                        
                        comparisons.append(EntityComparison(
                            entity_type="totals",
                            exists_in_db=False,
                            is_identical=False,
                            differences=[],
                            existing_data=None,
                            new_data={
                                "subtotal": request.totals.subtotal,
                                "gstAmount": request.totals.gstAmount,
                                "roundOff": request.totals.roundOff,
                                "grandTotal": request.totals.grandTotal
                            }
                        ))
                        
                        comparisons.append(EntityComparison(
                            entity_type="payment",
                            exists_in_db=False,
                            is_identical=False,
                            differences=[],
                            existing_data=None,
                            new_data={
                                "mode": request.paymentDetails.mode,
                                "reference": request.paymentDetails.reference,
                                "status": request.paymentDetails.status
                            }
                        ))
                else:
                    logger.log_step("no_invoice_number_provided")
                    # No invoice number provided, still add comparisons for all entities
                    comparisons.append(EntityComparison(
                        entity_type="invoice",
                        exists_in_db=False,
                        is_identical=False,
                        differences=[],
                        existing_data=None,
                        new_data={
                            "invoiceNumber": None,
                            "invoiceDate": request.invoiceDate,
                            "dueDate": request.dueDate
                        }
                    ))
                    
                    # Add comparisons for all other entities
                    comparisons.append(EntityComparison(
                        entity_type="vendor",
                        exists_in_db=False,
                        is_identical=False,
                        differences=[],
                        existing_data=None,
                        new_data={
                            "name": request.vendor.name,
                            "gstin": request.vendor.gstin,
                            "pan": request.vendor.pan,
                            "address": request.vendor.address
                        }
                    ))
                    
                    comparisons.append(EntityComparison(
                        entity_type="customer",
                        exists_in_db=False,
                        is_identical=False,
                        differences=[],
                        existing_data=None,
                        new_data={
                            "name": request.customer.name,
                            "address": request.customer.address
                        }
                    ))
                    
                    comparisons.append(EntityComparison(
                        entity_type="line_items",
                        exists_in_db=False,
                        is_identical=False,
                        differences=[],
                        existing_data=None,
                        new_data={
                            "count": len(request.lineItems),
                            "items": [
                                {
                                    "description": item.description,
                                    "quantity": item.quantity,
                                    "unitPrice": item.unitPrice,
                                    "taxPercent": item.taxPercent,
                                    "amount": item.amount
                                }
                                for item in request.lineItems
                            ]
                        }
                    ))
                    
                    comparisons.append(EntityComparison(
                        entity_type="totals",
                        exists_in_db=False,
                        is_identical=False,
                        differences=[],
                        existing_data=None,
                        new_data={
                            "subtotal": request.totals.subtotal,
                            "gstAmount": request.totals.gstAmount,
                            "roundOff": request.totals.roundOff,
                            "grandTotal": request.totals.grandTotal
                        }
                    ))
                    
                    comparisons.append(EntityComparison(
                        entity_type="payment",
                        exists_in_db=False,
                        is_identical=False,
                        differences=[],
                        existing_data=None,
                        new_data={
                            "mode": request.paymentDetails.mode,
                            "reference": request.paymentDetails.reference,
                            "status": request.paymentDetails.status
                        }
                    ))
                
                # Validate tax calculations
                tax_validation_errors = self._validate_tax_calculations(request)
                
                # Generate summary
                summary = self._generate_summary(comparisons)
                
                # Generate LLM summary if client is available
                llm_summary = None
                try:
                    llm_summary = await self._generate_llm_summary(
                        comparisons, 
                        invoice_exists=invoice_exists,
                        invoice_number=request.invoiceNumber,
                        missing_value_checks=missing_value_checks,
                        tax_validation_errors=tax_validation_errors,
                        duplicate_by_criteria=duplicate_by_criteria
                    )
                except Exception as e:
                    logger.log_error("llm_summary_generation_failed", {
                        "error": str(e),
                        "note": "Continuing without LLM summary"
                    })
                
                # Ensure we always have comparisons
                if len(comparisons) == 0:
                    logger.log_error("no_comparisons_generated", {
                        "invoice_number": request.invoiceNumber,
                        "invoice_exists": invoice_exists,
                        "note": "No comparisons were generated - this should not happen"
                    })
                    # Add at least one comparison to show the invoice data
                    comparisons.append(EntityComparison(
                        entity_type="invoice",
                        exists_in_db=invoice_exists,
                        is_identical=False,
                        differences=[],
                        existing_data=None,
                        new_data={
                            "invoiceNumber": request.invoiceNumber,
                            "invoiceDate": request.invoiceDate,
                            "dueDate": request.dueDate
                        }
                    ))
                
                logger.log_step("validation_completed", {
                    "invoice_exists": invoice_exists,
                    "invoice_id": invoice_id,
                    "total_comparisons": len(comparisons),
                    "comparison_entity_types": [comp.entity_type for comp in comparisons],
                    "identical_entities": summary.get("identical_count", 0),
                    "different_entities": summary.get("different_count", 0),
                    "missing_value_checks": len(missing_value_checks.get("errors", [])),
                    "tax_validation_errors": len(tax_validation_errors),
                    "duplicate_by_criteria": duplicate_by_criteria,
                    "llm_summary_generated": llm_summary is not None
                })
                
                # Convert comparisons to dict format
                comparisons_dict = [comp.model_dump() for comp in comparisons]
                
                logger.log_step("comparisons_serialized", {
                    "comparisons_count": len(comparisons_dict),
                    "first_comparison": comparisons_dict[0] if comparisons_dict else None
                })
                
                return {
                    "invoice_exists": invoice_exists,
                    "invoice_id": invoice_id,
                    "duplicate_by_criteria": duplicate_by_criteria,
                    "comparisons": comparisons_dict,
                    "summary": summary,
                    "missing_value_checks": missing_value_checks,
                    "tax_validation_errors": tax_validation_errors,
                    "llm_summary": llm_summary.model_dump() if llm_summary else None
                }
                
        except Exception as e:
            logger.log_error("validation_failed", {
                "error": str(e),
                "invoice_number": request.invoiceNumber
            })
            raise

    async def _compare_invoice(
        self, conn, invoice_id: int, request: ValidationRequest
    ) -> EntityComparison:
        """Compare invoice basic information"""
        invoice_record = await conn.fetchrow("""
            SELECT invoice_id, invoice_number, invoice_date, due_date
            FROM invoice
            WHERE invoice_id = $1
        """, invoice_id)
        
        # Normalize dates for comparison
        existing_invoice_date = normalize_date_for_comparison(invoice_record['invoice_date'])
        existing_due_date = normalize_date_for_comparison(invoice_record['due_date'])
        new_invoice_date = normalize_date_for_comparison(request.invoiceDate)
        new_due_date = normalize_date_for_comparison(request.dueDate)
        
        existing = {
            "invoice_id": invoice_record['invoice_id'],
            "invoiceNumber": invoice_record['invoice_number'],
            "invoiceDate": existing_invoice_date,
            "dueDate": existing_due_date
        }
        
        new = {
            "invoiceNumber": request.invoiceNumber,
            "invoiceDate": new_invoice_date,
            "dueDate": new_due_date
        }
        
        differences = []
        is_identical = True
        
        # Compare invoice number
        if existing.get("invoiceNumber") != new.get("invoiceNumber"):
            is_identical = False
            differences.append({
                "field": "invoiceNumber",
                "existing": existing.get("invoiceNumber"),
                "new": new.get("invoiceNumber")
            })
        
        # Compare dates (already normalized)
        if existing_invoice_date != new_invoice_date:
            is_identical = False
            differences.append({
                "field": "invoiceDate",
                "existing": existing_invoice_date,
                "new": new_invoice_date
            })
        
        if existing_due_date != new_due_date:
            is_identical = False
            differences.append({
                "field": "dueDate",
                "existing": existing_due_date,
                "new": new_due_date
            })
        
        return EntityComparison(
            entity_type="invoice",
            exists_in_db=True,
            is_identical=is_identical,
            differences=differences,
            existing_data=existing,
            new_data=new
        )

    async def _compare_vendor(
        self, conn, invoice_id: int, new_vendor: Vendor
    ) -> EntityComparison:
        """Compare vendor information"""
        vendor_record = await conn.fetchrow("""
            SELECT vendor_id, invoice_id, name, gstin, pan, address
            FROM vendorinfo
            WHERE invoice_id = $1
        """, invoice_id)
        
        if not vendor_record:
            return EntityComparison(
                entity_type="vendor",
                exists_in_db=False,
                is_identical=False,
                differences=[],
                existing_data=None,
                new_data={
                    "name": new_vendor.name,
                    "gstin": new_vendor.gstin,
                    "pan": new_vendor.pan,
                    "address": new_vendor.address
                }
            )
        
        existing = {
            "name": vendor_record['name'],
            "gstin": vendor_record['gstin'],
            "pan": vendor_record['pan'],
            "address": vendor_record['address']
        }
        
        new = {
            "name": new_vendor.name,
            "gstin": new_vendor.gstin,
            "pan": new_vendor.pan,
            "address": new_vendor.address
        }
        
        differences = []
        is_identical = True
        
        for key in ["name", "gstin", "pan", "address"]:
            existing_val = existing.get(key)
            new_val = new.get(key)
            if existing_val != new_val:
                is_identical = False
                differences.append({
                    "field": key,
                    "existing": existing_val,
                    "new": new_val
                })
        
        return EntityComparison(
            entity_type="vendor",
            exists_in_db=True,
            is_identical=is_identical,
            differences=differences,
            existing_data=existing,
            new_data=new
        )

    async def _compare_customer(
        self, conn, invoice_id: int, new_customer: Customer
    ) -> EntityComparison:
        """Compare customer information"""
        customer_record = await conn.fetchrow("""
            SELECT customer_id, invoice_id, name, address
            FROM customerinfo
            WHERE invoice_id = $1
        """, invoice_id)
        
        if not customer_record:
            return EntityComparison(
                entity_type="customer",
                exists_in_db=False,
                is_identical=False,
                differences=[],
                existing_data=None,
                new_data={
                    "name": new_customer.name,
                    "address": new_customer.address
                }
            )
        
        existing = {
            "name": customer_record['name'],
            "address": customer_record['address']
        }
        
        new = {
            "name": new_customer.name,
            "address": new_customer.address
        }
        
        differences = []
        is_identical = True
        
        for key in ["name", "address"]:
            existing_val = existing.get(key)
            new_val = new.get(key)
            if existing_val != new_val:
                is_identical = False
                differences.append({
                    "field": key,
                    "existing": existing_val,
                    "new": new_val
                })
        
        return EntityComparison(
            entity_type="customer",
            exists_in_db=True,
            is_identical=is_identical,
            differences=differences,
            existing_data=existing,
            new_data=new
        )

    async def _compare_line_items(
        self, conn, invoice_id: int, new_items: List[LineItem]
    ) -> EntityComparison:
        """Compare line items"""
        existing_items = await conn.fetch("""
            SELECT item_id, invoice_id, description, quantity, unit_price, tax_percent, amount
            FROM item_details
            WHERE invoice_id = $1
            ORDER BY item_id
        """, invoice_id)
        
        existing_list = [
            {
                "description": item['description'],
                "quantity": float(item['quantity']),
                "unit_price": float(item['unit_price']),
                "tax_percent": float(item['tax_percent']),
                "amount": float(item['amount'])
            }
            for item in existing_items
        ]
        
        # Convert LineItem models to dict format for comparison
        normalized_new = [
            {
                "description": item.description,
                "quantity": float(item.quantity),
                "unit_price": float(item.unitPrice),
                "tax_percent": float(item.taxPercent),
                "amount": float(item.amount)
            }
            for item in new_items
        ]
        
        differences = []
        is_identical = len(existing_list) == len(normalized_new)
        
        if is_identical:
            for i, (existing_item, new_item) in enumerate(zip(existing_list, normalized_new)):
                for key in ["description", "quantity", "unit_price", "tax_percent", "amount"]:
                    existing_val = existing_item.get(key)
                    new_val = new_item.get(key)
                    if existing_val != new_val:
                        is_identical = False
                        differences.append({
                            "item_index": i,
                            "field": key,
                            "existing": existing_val,
                            "new": new_val
                        })
        else:
            is_identical = False
            differences.append({
                "field": "item_count",
                "existing": len(existing_list),
                "new": len(normalized_new)
            })
        
        return EntityComparison(
            entity_type="line_items",
            exists_in_db=len(existing_list) > 0,
            is_identical=is_identical,
            differences=differences,
            existing_data={"items": existing_list, "count": len(existing_list)},
            new_data={"items": normalized_new, "count": len(normalized_new)}
        )

    async def _compare_totals(
        self, conn, invoice_id: int, new_totals: Totals
    ) -> EntityComparison:
        """Compare totals"""
        totals_record = await conn.fetchrow("""
            SELECT totals_id, invoice_id, subtotal, gst_amount, round_off, grand_total
            FROM Totals
            WHERE invoice_id = $1
        """, invoice_id)
        
        if not totals_record:
            return EntityComparison(
                entity_type="totals",
                exists_in_db=False,
                is_identical=False,
                differences=[],
                existing_data=None,
                new_data={
                    "subtotal": new_totals.subtotal,
                    "gstAmount": new_totals.gstAmount,
                    "roundOff": new_totals.roundOff,
                    "grandTotal": new_totals.grandTotal
                }
            )
        
        existing = {
            "subtotal": float(totals_record['subtotal']),
            "gst_amount": float(totals_record['gst_amount']),
            "round_off": float(totals_record['round_off']) if totals_record['round_off'] else None,
            "grand_total": float(totals_record['grand_total'])
        }
        
        normalized_new = {
            "subtotal": float(new_totals.subtotal),
            "gst_amount": float(new_totals.gstAmount),
            "round_off": float(new_totals.roundOff) if new_totals.roundOff else None,
            "grand_total": float(new_totals.grandTotal)
        }
        
        differences = []
        is_identical = True
        
        for key in ["subtotal", "gst_amount", "round_off", "grand_total"]:
            existing_val = existing.get(key)
            new_val = normalized_new.get(key)
            if existing_val != new_val:
                is_identical = False
                differences.append({
                    "field": key,
                    "existing": existing_val,
                    "new": new_val
                })
        
        return EntityComparison(
            entity_type="totals",
            exists_in_db=True,
            is_identical=is_identical,
            differences=differences,
            existing_data=existing,
            new_data=normalized_new
        )

    async def _compare_payment(
        self, conn, invoice_id: int, new_payment: PaymentDetails
    ) -> EntityComparison:
        """Compare payment details"""
        payment_record = await conn.fetchrow("""
            SELECT payment_id, invoice_id, mode, reference, status
            FROM Paymentinfo
            WHERE invoice_id = $1
        """, invoice_id)
        
        if not payment_record:
            return EntityComparison(
                entity_type="payment",
                exists_in_db=False,
                is_identical=False,
                differences=[],
                existing_data=None,
                new_data={
                    "mode": new_payment.mode,
                    "reference": new_payment.reference,
                    "status": new_payment.status
                }
            )
        
        existing = {
            "mode": payment_record['mode'],
            "reference": payment_record['reference'],
            "status": payment_record['status']
        }
        
        normalized_new = {
            "mode": new_payment.mode,
            "reference": new_payment.reference,
            "status": new_payment.status
        }
        
        differences = []
        is_identical = True
        
        for key in ["mode", "reference", "status"]:
            existing_val = existing.get(key)
            new_val = normalized_new.get(key)
            if existing_val != new_val:
                is_identical = False
                differences.append({
                    "field": key,
                    "existing": existing_val,
                    "new": new_val
                })
        
        return EntityComparison(
            entity_type="payment",
            exists_in_db=True,
            is_identical=is_identical,
            differences=differences,
            existing_data=existing,
            new_data=normalized_new
        )

    def _generate_summary(self, comparisons: List[EntityComparison]) -> Dict[str, Any]:
        """Generate summary statistics from comparisons"""
        total_entities = len(comparisons)
        existing_count = sum(1 for comp in comparisons if comp.exists_in_db)
        identical_count = sum(1 for comp in comparisons if comp.is_identical)
        different_count = sum(1 for comp in comparisons if not comp.is_identical and comp.exists_in_db)
        new_count = sum(1 for comp in comparisons if not comp.exists_in_db)
        
        total_differences = sum(len(comp.differences) for comp in comparisons)
        
        return {
            "total_entities": total_entities,
            "existing_count": existing_count,
            "identical_count": identical_count,
            "different_count": different_count,
            "new_count": new_count,
            "total_differences": total_differences
        }

    def _check_missing_values(self, request: ValidationRequest) -> Dict[str, List[Dict[str, Any]]]:
        """
        Check for missing or inconsistent values in the invoice data.
        Returns dict with 'errors' and 'warnings' lists.
        """
        errors = []
        warnings = []
        
        # Check for missing critical vendor information
        if not request.vendor.gstin or not request.vendor.gstin.strip():
            errors.append({
                "type": "missing_gstin",
                "message": "Vendor GSTIN is missing or empty. GSTIN is required for tax compliance.",
                "severity": "critical",
                "field": "vendor.gstin"
            })
        
        if not request.vendor.name or not request.vendor.name.strip():
            errors.append({
                "type": "missing_vendor_name",
                "message": "Vendor name is missing or empty.",
                "severity": "critical",
                "field": "vendor.name"
            })
        
        # Check for missing customer information
        if not request.customer.name or not request.customer.name.strip():
            warnings.append({
                "type": "missing_customer_name",
                "message": "Customer name is missing or empty.",
                "severity": "moderate",
                "field": "customer.name"
            })
        
        # Check for missing invoice number
        if not request.invoiceNumber or not request.invoiceNumber.strip():
            errors.append({
                "type": "missing_invoice_number",
                "message": "Invoice number is missing or empty.",
                "severity": "critical",
                "field": "invoiceNumber"
            })
        
        # Check for missing dates
        if not request.invoiceDate or not request.invoiceDate.strip():
            warnings.append({
                "type": "missing_invoice_date",
                "message": "Invoice date is missing or empty.",
                "severity": "moderate",
                "field": "invoiceDate"
            })
        
        # Check for empty line items
        if not request.lineItems or len(request.lineItems) == 0:
            errors.append({
                "type": "missing_line_items",
                "message": "No line items found in invoice. Invoice must have at least one line item.",
                "severity": "critical",
                "field": "lineItems"
            })
        
        # Check for missing totals
        if request.totals.grandTotal is None or request.totals.grandTotal == 0:
            if len(request.lineItems) > 0:
                errors.append({
                    "type": "missing_grand_total",
                    "message": "Grand total is missing or zero, but line items exist.",
                    "severity": "critical",
                    "field": "totals.grandTotal"
                })
        
        return {
            "errors": errors,
            "warnings": warnings
        }

    def _validate_tax_calculations(self, request: ValidationRequest) -> List[Dict[str, Any]]:
        """
        Validate tax calculations:
        1. Line item calculations: quantity * unitPrice * (1 + taxPercent/100) should equal amount
        2. Totals validation: subtotal + gstAmount + roundOff should equal grandTotal
        3. Line items sum should match subtotal
        """
        errors = []
        warnings = []
        
        # Validate line item calculations
        calculated_subtotal = 0.0
        calculated_gst = 0.0
        
        for idx, item in enumerate(request.lineItems):
            # Calculate expected amount: (quantity * unitPrice) * (1 + taxPercent/100)
            base_amount = item.quantity * item.unitPrice
            expected_amount = base_amount * (1 + item.taxPercent / 100)
            tax_amount = base_amount * (item.taxPercent / 100)
            
            # Allow small rounding differences (0.01)
            amount_diff = abs(item.amount - expected_amount)
            if amount_diff > 0.01:
                errors.append({
                    "type": "line_item_calculation_error",
                    "message": f"Line item {idx + 1} calculation mismatch: Expected {expected_amount:.2f} but got {item.amount:.2f} (difference: {amount_diff:.2f})",
                    "severity": "critical",
                    "line_item_index": idx,
                    "description": item.description,
                    "expected": round(expected_amount, 2),
                    "actual": item.amount
                })
            
            calculated_subtotal += base_amount
            calculated_gst += tax_amount
        
        # Validate totals
        # Check if subtotal matches sum of line item base amounts
        subtotal_diff = abs(request.totals.subtotal - calculated_subtotal)
        if subtotal_diff > 0.01:
            errors.append({
                "type": "subtotal_mismatch",
                "message": f"Subtotal mismatch: Calculated from line items {calculated_subtotal:.2f} but totals show {request.totals.subtotal:.2f} (difference: {subtotal_diff:.2f})",
                "severity": "critical",
                "calculated": round(calculated_subtotal, 2),
                "actual": request.totals.subtotal
            })
        
        # Check if GST amount matches calculated GST
        gst_diff = abs(request.totals.gstAmount - calculated_gst)
        if gst_diff > 0.01:
            errors.append({
                "type": "gst_amount_mismatch",
                "message": f"GST amount mismatch: Calculated from line items {calculated_gst:.2f} but totals show {request.totals.gstAmount:.2f} (difference: {gst_diff:.2f})",
                "severity": "critical",
                "calculated": round(calculated_gst, 2),
                "actual": request.totals.gstAmount
            })
        
        # Check grand total calculation: subtotal + gstAmount + roundOff = grandTotal
        round_off = request.totals.roundOff or 0.0
        expected_grand_total = request.totals.subtotal + request.totals.gstAmount + round_off
        grand_total_diff = abs(request.totals.grandTotal - expected_grand_total)
        
        if grand_total_diff > 0.01:
            errors.append({
                "type": "grand_total_calculation_error",
                "message": f"Grand total calculation error: Expected {expected_grand_total:.2f} (subtotal {request.totals.subtotal:.2f} + GST {request.totals.gstAmount:.2f} + roundOff {round_off:.2f}) but got {request.totals.grandTotal:.2f} (difference: {grand_total_diff:.2f})",
                "severity": "critical",
                "expected": round(expected_grand_total, 2),
                "actual": request.totals.grandTotal
            })
        elif grand_total_diff > 0.001:  # Very small difference (rounding)
            warnings.append({
                "type": "grand_total_rounding",
                "message": f"Grand total has minor rounding difference: {grand_total_diff:.4f}",
                "severity": "minor",
                "expected": round(expected_grand_total, 2),
                "actual": request.totals.grandTotal
            })
        
        return errors + warnings

    def _detect_duplicate_invoice(self, comparisons: List[EntityComparison], invoice_exists: bool, duplicate_by_criteria: bool = False) -> Optional[str]:
        """
        Detect if this is a duplicate invoice (COMPARISON-BASED ERROR).
        Three methods:
        1. Duplicate by criteria: Invoice number + vendor name + invoice date match
        2. All entities identical (complete duplicate) - including line items
        3. All critical entities identical (invoice, vendor, customer, totals, payment) - line items can differ (this becomes a warning)
        Returns error message if duplicate detected, None otherwise.
        """
        if duplicate_by_criteria:
            return "Duplicate invoice detected: Invoice number, vendor name, and invoice date combination already exists in database. This appears to be a duplicate submission."
        
        if not invoice_exists:
            return None
        
        # Check if all entities are identical (including line items)
        all_entities = ["invoice", "vendor", "customer", "totals", "payment", "line_items"]
        all_comparisons = [comp for comp in comparisons if comp.entity_type in all_entities]
        
        # Check if ALL entities including line items are identical
        all_identical_including_items = all(comp.is_identical for comp in all_comparisons if comp.exists_in_db)
        
        if all_identical_including_items and len([c for c in all_comparisons if c.exists_in_db]) == len(all_entities):
            return "Duplicate invoice detected: All entities (invoice, vendor, customer, line items, totals, payment) are identical to existing invoice in database. This appears to be a complete duplicate submission."
        
        # Check critical entities (excluding line items)
        critical_entities = ["invoice", "vendor", "customer", "totals", "payment"]
        critical_comparisons = [comp for comp in comparisons if comp.entity_type in critical_entities]
        
        all_critical_identical = all(comp.is_identical for comp in critical_comparisons if comp.exists_in_db)
        
        if all_critical_identical:
            # Critical entities identical but line items differ - this is handled as warning in categorization
            # Return None here, let the categorization handle it as a warning
            return None
        
        return None

    def _categorize_differences(
        self, 
        comparisons: List[EntityComparison], 
        invoice_exists: bool, 
        invoice_number: Optional[str],
        missing_value_checks: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        tax_validation_errors: Optional[List[Dict[str, Any]]] = None,
        duplicate_by_criteria: bool = False
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Pre-categorize differences into errors and warnings based on business logic.
        Returns dict with 'errors' and 'warnings' lists.
        """
        errors = []
        warnings = []
        
        # Add missing value checks as errors/warnings
        if missing_value_checks:
            errors.extend(missing_value_checks.get("errors", []))
            warnings.extend(missing_value_checks.get("warnings", []))
        
        # Add tax validation errors
        if tax_validation_errors:
            for tax_error in tax_validation_errors:
                if tax_error.get("severity") == "critical":
                    errors.append(tax_error)
                else:
                    warnings.append(tax_error)
        
        # Check for duplicate invoice (all entities identical)
        duplicate_error = self._detect_duplicate_invoice(comparisons, invoice_exists, duplicate_by_criteria)
        if duplicate_error:
            errors.append({
                "type": "duplicate_invoice",
                "message": duplicate_error,
                "severity": "critical"
            })
        
        # COMPARISON-BASED VALIDATIONS
        # Analyze each comparison for entity-level errors and warnings
        for comp in comparisons:
            # Skip if entity doesn't exist in DB (it's new, not a comparison issue)
            if not comp.exists_in_db:
                continue
            
            # ERROR: If invoice exists and all entities are identical (complete duplicate)
            if comp.is_identical and invoice_exists:
                # This is already handled by duplicate detection, but we can add entity-specific notes
                if comp.entity_type == "invoice":
                    # Invoice basic info is identical - this contributes to duplicate error
                    pass  # Already handled above
                elif comp.entity_type in ["vendor", "customer", "totals", "payment"]:
                    # These being identical along with invoice confirms duplicate
                    pass  # Already handled above
            
            # WARNING: Line items changed for existing invoice
            if comp.entity_type == "line_items" and invoice_exists and not comp.is_identical:
                if comp.exists_in_db:
                    warnings.append({
                        "type": "line_items_changed",
                        "message": f"Line items changed for existing invoice '{invoice_number}': {len(comp.differences)} differences detected. Items, quantities, or prices have been modified.",
                        "severity": "moderate",
                        "differences_count": len(comp.differences),
                        "existing_items_count": comp.existing_data.get("count", 0) if comp.existing_data else 0,
                        "new_items_count": comp.new_data.get("count", 0) if comp.new_data else 0
                    })
            
            # Skip identical entities for further analysis
            if comp.is_identical:
                continue
            
            # COMPARISON-BASED VALIDATIONS BY ENTITY TYPE
            if comp.entity_type == "invoice":
                # Invoice-level differences
                for diff in comp.differences:
                    field = diff.get("field")
                    if field == "invoiceNumber":
                        # ERROR: Invoice number mismatch (shouldn't happen if we searched by invoice number)
                        errors.append({
                            "type": "invoice_number_mismatch",
                            "message": f"Invoice number mismatch: existing '{diff.get('existing')}' vs new '{diff.get('new')}'. Database record has different invoice number.",
                            "severity": "critical"
                        })
                    elif field in ["invoiceDate", "dueDate"]:
                        # Date differences - check if it's a logic error or just different dates
                        existing_date = parse_date(str(diff.get("existing", "")))
                        new_date = parse_date(str(diff.get("new", "")))
                        if existing_date and new_date:
                            if field == "dueDate" and comp.existing_data and comp.new_data:
                                # Check if due date is before invoice date (logic error)
                                invoice_date_existing = parse_date(str(comp.existing_data.get("invoiceDate", "")))
                                invoice_date_new = parse_date(str(comp.new_data.get("invoiceDate", "")))
                                if invoice_date_existing and new_date < invoice_date_existing:
                                    errors.append({
                                        "type": "date_logic_error",
                                        "message": f"Due date ({new_date}) is before invoice date ({invoice_date_existing})",
                                        "severity": "critical"
                                    })
                                elif existing_date != new_date:
                                    warnings.append({
                                        "type": "date_change",
                                        "message": f"{field} changed from {existing_date} to {new_date}",
                                        "severity": "moderate"
                                    })
                            elif existing_date != new_date:
                                warnings.append({
                                    "type": "date_change",
                                    "message": f"Invoice {field} changed from {existing_date} to {new_date}",
                                    "severity": "moderate"
                                })
            
            elif comp.entity_type == "totals":
                # Amount differences (COMPARISON-BASED VALIDATION)
                for diff in comp.differences:
                    field = diff.get("field")
                    existing_val = diff.get("existing")
                    new_val = diff.get("new")
                    
                    if field in ["grand_total", "subtotal", "gst_amount"]:
                        if existing_val and new_val:
                            try:
                                existing_float = float(existing_val)
                                new_float = float(new_val)
                                if existing_float != 0:
                                    variance = abs((new_float - existing_float) / existing_float) * 100
                                    absolute_diff = abs(new_float - existing_float)
                                    
                                    # ERROR: Significant amount discrepancy (> 1% or > 10 absolute)
                                    if variance > 1.0 or absolute_diff > 10.0:
                                        errors.append({
                                            "type": "amount_discrepancy",
                                            "message": f"Totals {field} difference exceeds threshold: existing {existing_float:.2f} vs new {new_float:.2f} (variance: {variance:.2f}%, absolute: {absolute_diff:.2f})",
                                            "severity": "critical",
                                            "field": field,
                                            "existing": existing_float,
                                            "new": new_float,
                                            "variance_percent": round(variance, 2),
                                            "absolute_difference": round(absolute_diff, 2)
                                        })
                                    # WARNING: Minor amount difference
                                    elif variance > 0 or absolute_diff > 0.01:
                                        warnings.append({
                                            "type": "amount_rounding",
                                            "message": f"Totals {field} minor difference: existing {existing_float:.2f} vs new {new_float:.2f} (variance: {variance:.2f}%, absolute: {absolute_diff:.2f})",
                                            "severity": "minor",
                                            "field": field,
                                            "existing": existing_float,
                                            "new": new_float
                                        })
                            except (ValueError, TypeError):
                                warnings.append({
                                    "type": "amount_format",
                                    "message": f"Totals {field} format difference: existing '{existing_val}' vs new '{new_val}'",
                                    "severity": "minor",
                                    "field": field
                                })
                    elif field == "round_off":
                        # Round off differences are usually minor
                        warnings.append({
                            "type": "round_off_difference",
                            "message": f"Round off difference: existing '{existing_val}' vs new '{new_val}'",
                            "severity": "minor",
                            "field": field
                        })
            
            elif comp.entity_type == "vendor":
                # Vendor differences (COMPARISON-BASED VALIDATION)
                for diff in comp.differences:
                    field = diff.get("field")
                    if field in ["gstin", "pan"]:
                        # ERROR: Missing critical tax info (removed)
                        if not diff.get("new") and diff.get("existing"):
                            errors.append({
                                "type": "missing_tax_info",
                                "message": f"Vendor {field.upper()} removed: was '{diff.get('existing')}', now missing. This affects tax compliance.",
                                "severity": "critical",
                                "field": f"vendor.{field}",
                                "existing": diff.get("existing"),
                                "new": diff.get("new")
                            })
                        # WARNING: Tax info changed
                        elif diff.get("new") != diff.get("existing"):
                            warnings.append({
                                "type": "tax_info_change",
                                "message": f"Vendor {field.upper()} changed: '{diff.get('existing')}' to '{diff.get('new')}'. Verify this is correct.",
                                "severity": "moderate",
                                "field": f"vendor.{field}",
                                "existing": diff.get("existing"),
                                "new": diff.get("new")
                            })
                    elif field == "address":
                        warnings.append({
                            "type": "address_change",
                            "message": f"Vendor address changed: '{diff.get('existing')}' to '{diff.get('new')}'",
                            "severity": "minor",
                            "field": "vendor.address"
                        })
                    elif field == "name":
                        # WARNING: Vendor name change (could indicate different vendor)
                        warnings.append({
                            "type": "vendor_name_change",
                            "message": f"Vendor name changed: '{diff.get('existing')}' to '{diff.get('new')}'. Verify this is the same vendor.",
                            "severity": "moderate",
                            "field": "vendor.name",
                            "existing": diff.get("existing"),
                            "new": diff.get("new")
                        })
            
            elif comp.entity_type == "line_items":
                # Line items differences - already handled above, but add detailed analysis
                if comp.exists_in_db and not comp.is_identical:
                    # Detailed line item differences
                    item_count_diff = False
                    item_content_diff = False
                    
                    for diff in comp.differences:
                        if diff.get("field") == "item_count":
                            item_count_diff = True
                        else:
                            item_content_diff = True
                    
                    if item_count_diff:
                        existing_count = comp.existing_data.get("count", 0) if comp.existing_data else 0
                        new_count = comp.new_data.get("count", 0) if comp.new_data else 0
                        warnings.append({
                            "type": "line_items_count_changed",
                            "message": f"Line items count changed: existing invoice has {existing_count} items, new data has {new_count} items",
                            "severity": "moderate",
                            "existing_count": existing_count,
                            "new_count": new_count
                        })
                    
                    if item_content_diff:
                        warnings.append({
                            "type": "line_items_content_changed",
                            "message": f"Line items content changed: {len([d for d in comp.differences if d.get('field') != 'item_count'])} item field differences detected (description, quantity, price, tax, or amount)",
                            "severity": "moderate",
                            "differences": [d for d in comp.differences if d.get("field") != "item_count"]
                        })
                elif not comp.exists_in_db:
                    warnings.append({
                        "type": "line_items_new",
                        "message": "New line items added (invoice not in database)",
                        "severity": "minor"
                    })
            
            elif comp.entity_type == "payment":
                # Payment differences (COMPARISON-BASED VALIDATION)
                for diff in comp.differences:
                    field = diff.get("field")
                    if field == "status":
                        existing_status = diff.get("existing")
                        new_status = diff.get("new")
                        # ERROR: Payment status regression (Paid → Unpaid/Partial)
                        if existing_status == "Paid" and new_status in ["Unpaid", "Partial"]:
                            errors.append({
                                "type": "payment_status_regression",
                                "message": f"Payment status regressed from '{existing_status}' to '{new_status}'. This indicates a potential payment reversal issue.",
                                "severity": "critical",
                                "field": "payment.status",
                                "existing": existing_status,
                                "new": new_status
                            })
                        # WARNING: Payment status changed (other cases)
                        elif existing_status != new_status:
                            warnings.append({
                                "type": "payment_status_change",
                                "message": f"Payment status changed from '{existing_status}' to '{new_status}'. Verify this is correct.",
                                "severity": "moderate",
                                "field": "payment.status",
                                "existing": existing_status,
                                "new": new_status
                            })
                    else:
                        # WARNING: Other payment field changes
                        warnings.append({
                            "type": "payment_field_change",
                            "message": f"Payment {field} changed: '{diff.get('existing')}' to '{diff.get('new')}'",
                            "severity": "minor",
                            "field": f"payment.{field}"
                        })
        
        return {
            "errors": errors,
            "warnings": warnings
        }

    async def _generate_llm_summary(
        self, 
        comparisons: List[EntityComparison], 
        invoice_exists: bool = False, 
        invoice_number: Optional[str] = None,
        missing_value_checks: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        tax_validation_errors: Optional[List[Dict[str, Any]]] = None,
        duplicate_by_criteria: bool = False
    ) -> Optional[ValidationSummary]:
        """Generate LLM-powered summary with errors and warnings categorization"""
        try:
            self._ensure_client()
        except ValueError:
            # Client not available, return None
            return None
        
        # Pre-categorize differences using business logic
        categorized = self._categorize_differences(
            comparisons, 
            invoice_exists, 
            invoice_number,
            missing_value_checks=missing_value_checks,
            tax_validation_errors=tax_validation_errors,
            duplicate_by_criteria=duplicate_by_criteria
        )
        
        # Prepare comparison data for LLM
        comparison_data = {
            "invoice_exists": invoice_exists,
            "invoice_number": invoice_number,
            "duplicate_by_criteria": duplicate_by_criteria,
            "comparisons": [
                {
                    "entity_type": comp.entity_type,
                    "exists_in_db": comp.exists_in_db,
                    "is_identical": comp.is_identical,
                    "differences": comp.differences,
                    "existing_data": comp.existing_data,
                    "new_data": comp.new_data
                }
                for comp in comparisons
            ],
            "summary": self._generate_summary(comparisons),
            "missing_value_checks": missing_value_checks or {},
            "tax_validation_errors": tax_validation_errors or [],
            "pre_categorized": {
                "errors": categorized["errors"],
                "warnings": categorized["warnings"]
            }
        }
        
        # Create prompt with comparison data
        prompt = f"""{VALIDATION_SUMMARY_PROMPT}

Comparison Data:
{json.dumps(comparison_data, indent=2)}

Note: Pre-categorized errors and warnings are provided as guidance. Use them along with the categorization rules to create the final summary.
"""
        
        try:
            model = getattr(settings, 'LLM_MODEL', 'gpt-4o-mini')
            temperature = getattr(settings, 'LLM_TEMPERATURE', 0.0)
            
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are an expert validation analyst."},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                response_format={"type": "json_object"}
            )
            
            # Parse response
            content = response.choices[0].message.content
            summary_data = json.loads(content)
            
            logger.log_step("llm_summary_generated", {
                "errors_count": len(summary_data.get("errors", [])),
                "warnings_count": len(summary_data.get("warnings", [])),
                "severity": summary_data.get("severity", "none"),
                "pre_categorized_errors": len(categorized["errors"]),
                "pre_categorized_warnings": len(categorized["warnings"])
            })
            
            return ValidationSummary(
                summary=summary_data.get("summary", ""),
                errors=summary_data.get("errors", []),
                warnings=summary_data.get("warnings", []),
                severity=summary_data.get("severity", "none")
            )
            
        except Exception as e:
            logger.log_error("llm_summary_parsing_failed", {
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise


# Global validation service instance
validation_service = ValidationService()

