"""Service for saving extracted schemas to PostgreSQL database"""

from datetime import datetime, date
from typing import Dict, Any, Optional
from decimal import Decimal
import re
import json

from ..utils.database import db_manager
from ..models.schemas import InvoiceSchema, ValidationResult
from ..utils.logging import logger


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
    
    # If all parsing fails, log and return None
    logger.log_error("date_parsing_failed", {
        "date_string": date_str,
        "note": "Could not parse date, will be stored as NULL"
    })
    return None


class DatabaseService:
    """Service for persisting invoice schemas to PostgreSQL"""

    async def save_invoice_schema(
        self,
        invoice_schema: InvoiceSchema,
        document_id: str,
        ocr_text: str,
        validation_result: Optional[ValidationResult] = None,
        confidence_score: Optional[float] = None
    ) -> int:
        """
        Save extracted invoice schema to PostgreSQL database
        
        Args:
            invoice_schema: The extracted invoice schema
            document_id: Unique document identifier
            ocr_text: Original OCR text
            validation_result: Validation result if available
            confidence_score: Confidence score for extraction (0-100)
        
        Returns:
            invoice_id: The primary key of the created invoice record
        """
        try:
            async with db_manager.get_connection() as conn:
                # Start transaction
                async with conn.transaction():
                    # Parse dates from strings to date objects
                    parsed_invoice_date = parse_date(invoice_schema.invoiceDate)
                    parsed_due_date = parse_date(invoice_schema.dueDate)
                    
                    logger.log_step("parsing_dates", {
                        "invoice_date_raw": invoice_schema.invoiceDate,
                        "invoice_date_parsed": str(parsed_invoice_date) if parsed_invoice_date else None,
                        "due_date_raw": invoice_schema.dueDate,
                        "due_date_parsed": str(parsed_due_date) if parsed_due_date else None
                    })
                    
                    # Insert or update invoice table
                    # Handle case where invoice_number might be None
                    if invoice_schema.invoiceNumber:
                        # Check if invoice with this number already exists
                        existing_invoice = await conn.fetchrow("""
                            SELECT invoice_id FROM invoice 
                            WHERE invoice_number = $1
                        """, invoice_schema.invoiceNumber)
                        
                        if existing_invoice:
                            # Update existing invoice
                            invoice_id = existing_invoice['invoice_id']
                            await conn.execute("""
                                UPDATE invoice 
                                SET invoice_date = $1,
                                    due_date = $2,
                                    updated_at = CURRENT_TIMESTAMP
                                WHERE invoice_id = $3
                            """,
                                parsed_invoice_date,
                                parsed_due_date,
                                invoice_id
                            )
                            logger.log_step("invoice_updated", {
                                "invoice_id": invoice_id,
                                "invoice_number": invoice_schema.invoiceNumber
                            })
                        else:
                            # Insert new invoice
                            invoice_id = await conn.fetchval("""
                                INSERT INTO invoice (invoice_number, invoice_date, due_date)
                                VALUES ($1, $2, $3)
                                RETURNING invoice_id
                            """,
                                invoice_schema.invoiceNumber,
                                parsed_invoice_date,
                                parsed_due_date
                            )
                            logger.log_step("invoice_inserted", {
                                "invoice_id": invoice_id,
                                "invoice_number": invoice_schema.invoiceNumber
                            })
                    else:
                        # Insert without invoice_number
                        invoice_id = await conn.fetchval("""
                            INSERT INTO invoice (invoice_number, invoice_date, due_date)
                            VALUES (NULL, $1, $2)
                            RETURNING invoice_id
                        """,
                            parsed_invoice_date,
                            parsed_due_date
                        )
                        logger.log_step("invoice_inserted_no_number", {
                            "invoice_id": invoice_id
                        })
                    
                    # Insert vendor info
                    logger.log_step("saving_vendor_info", {
                        "invoice_id": invoice_id,
                        "vendor_name": invoice_schema.vendor.name
                    })
                    await conn.execute("""
                        INSERT INTO vendorinfo (invoice_id, name, gstin, pan, address)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (invoice_id) DO UPDATE
                        SET name = EXCLUDED.name,
                            gstin = EXCLUDED.gstin,
                            pan = EXCLUDED.pan,
                            address = EXCLUDED.address,
                            updated_at = CURRENT_TIMESTAMP
                    """,
                        invoice_id,
                        invoice_schema.vendor.name,
                        invoice_schema.vendor.gstin,
                        invoice_schema.vendor.pan,
                        invoice_schema.vendor.address
                    )
                    logger.log_step("vendor_info_saved", {
                        "invoice_id": invoice_id
                    })
                    
                    # Insert customer info
                    logger.log_step("saving_customer_info", {
                        "invoice_id": invoice_id,
                        "customer_name": invoice_schema.customer.name,
                        "customer_address": invoice_schema.customer.address
                    })
                    await conn.execute("""
                        INSERT INTO customerinfo (invoice_id, name, address)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (invoice_id) DO UPDATE
                        SET name = EXCLUDED.name,
                            address = EXCLUDED.address,
                            updated_at = CURRENT_TIMESTAMP
                    """,
                        invoice_id,
                        invoice_schema.customer.name,
                        invoice_schema.customer.address
                    )
                    logger.log_step("customer_info_saved", {
                        "invoice_id": invoice_id
                    })
                    
                    # Delete existing items and insert new ones
                    await conn.execute("""
                        DELETE FROM item_details WHERE invoice_id = $1
                    """, invoice_id)
                    
                    # Insert line items
                    for item in invoice_schema.lineItems:
                        await conn.execute("""
                            INSERT INTO item_details 
                            (invoice_id, description, quantity, unit_price, tax_percent, amount)
                            VALUES ($1, $2, $3, $4, $5, $6)
                        """,
                            invoice_id,
                            item.description,
                            Decimal(str(item.quantity)),
                            Decimal(str(item.unitPrice)),
                            Decimal(str(item.taxPercent)),
                            Decimal(str(item.amount))
                        )
                    
                    # Insert totals
                    await conn.execute("""
                        INSERT INTO Totals 
                        (invoice_id, subtotal, gst_amount, round_off, grand_total)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (invoice_id) DO UPDATE
                        SET subtotal = EXCLUDED.subtotal,
                            gst_amount = EXCLUDED.gst_amount,
                            round_off = EXCLUDED.round_off,
                            grand_total = EXCLUDED.grand_total,
                            updated_at = CURRENT_TIMESTAMP
                    """,
                        invoice_id,
                        Decimal(str(invoice_schema.totals.subtotal)),
                        Decimal(str(invoice_schema.totals.gstAmount)),
                        Decimal(str(invoice_schema.totals.roundOff)) if invoice_schema.totals.roundOff else None,
                        Decimal(str(invoice_schema.totals.grandTotal))
                    )
                    
                    # Insert payment info
                    await conn.execute("""
                        INSERT INTO Paymentinfo (invoice_id, mode, reference, status)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (invoice_id) DO UPDATE
                        SET mode = EXCLUDED.mode,
                            reference = EXCLUDED.reference,
                            status = EXCLUDED.status,
                            updated_at = CURRENT_TIMESTAMP
                    """,
                        invoice_id,
                        invoice_schema.paymentDetails.mode,
                        invoice_schema.paymentDetails.reference,
                        invoice_schema.paymentDetails.status
                    )
                    
                    # Insert metadata
                    validation_errors_json = None
                    validation_warnings_json = None
                    is_valid = None
                    
                    if validation_result:
                        is_valid = validation_result.isValid
                        # Convert to JSON strings for JSONB columns
                        validation_errors_json = json.dumps([
                            {"field": e.field, "issue": e.issue, "suggestion": e.suggestion}
                            for e in validation_result.errors
                        ]) if validation_result.errors else None
                        validation_warnings_json = json.dumps([
                            {"field": w.field, "message": w.message}
                            for w in validation_result.warnings
                        ]) if validation_result.warnings else None
                    
                    await conn.execute("""
                        INSERT INTO metadata 
                        (invoice_id, document_id, ocr_text, upload_timestamp, 
                         extracted_confidence_score, validation_is_valid, 
                         validation_errors, validation_warnings)
                        VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb)
                        ON CONFLICT (invoice_id) DO UPDATE
                        SET document_id = EXCLUDED.document_id,
                            ocr_text = EXCLUDED.ocr_text,
                            extracted_confidence_score = EXCLUDED.extracted_confidence_score,
                            validation_is_valid = EXCLUDED.validation_is_valid,
                            validation_errors = EXCLUDED.validation_errors,
                            validation_warnings = EXCLUDED.validation_warnings,
                            updated_at = CURRENT_TIMESTAMP
                    """,
                        invoice_id,
                        document_id,
                        ocr_text,
                        datetime.utcnow(),
                        Decimal(str(confidence_score)) if confidence_score else None,
                        is_valid,
                        validation_errors_json,
                        validation_warnings_json
                    )
                    
                    logger.log_step("invoice_saved_to_database", {
                        "invoice_id": invoice_id,
                        "document_id": document_id,
                        "invoice_number": invoice_schema.invoiceNumber
                    })
                    
                    return invoice_id
                    
        except Exception as e:
            logger.log_error("database_save_failed", {
                "document_id": document_id,
                "error": str(e)
            })
            raise

    async def get_invoice_by_id(self, invoice_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve invoice by ID with all related data"""
        try:
            async with db_manager.get_connection() as conn:
                # Get invoice
                invoice = await conn.fetchrow("""
                    SELECT * FROM invoice WHERE invoice_id = $1
                """, invoice_id)
                
                if not invoice:
                    return None
                
                # Get vendor info
                vendor = await conn.fetchrow("""
                    SELECT * FROM vendorinfo WHERE invoice_id = $1
                """, invoice_id)
                
                # Get customer info
                customer = await conn.fetchrow("""
                    SELECT * FROM customerinfo WHERE invoice_id = $1
                """, invoice_id)
                
                # Get line items
                items = await conn.fetch("""
                    SELECT * FROM item_details WHERE invoice_id = $1 ORDER BY item_id
                """, invoice_id)
                
                # Get totals
                totals = await conn.fetchrow("""
                    SELECT * FROM Totals WHERE invoice_id = $1
                """, invoice_id)
                
                # Get payment info
                payment = await conn.fetchrow("""
                    SELECT * FROM Paymentinfo WHERE invoice_id = $1
                """, invoice_id)
                
                # Get metadata
                metadata = await conn.fetchrow("""
                    SELECT * FROM metadata WHERE invoice_id = $1
                """, invoice_id)
                
                return {
                    "invoice": dict(invoice) if invoice else None,
                    "vendor": dict(vendor) if vendor else None,
                    "customer": dict(customer) if customer else None,
                    "items": [dict(item) for item in items],
                    "totals": dict(totals) if totals else None,
                    "payment": dict(payment) if payment else None,
                    "metadata": dict(metadata) if metadata else None
                }
                
        except Exception as e:
            logger.log_error("database_fetch_failed", {
                "invoice_id": invoice_id,
                "error": str(e)
            })
            raise


# Global database service instance
database_service = DatabaseService()

