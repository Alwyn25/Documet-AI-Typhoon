from datetime import date
from typing import List
from InvoiceCoreProcessor.models.protocol import ExtractedInvoiceData, ItemDetail


def simulated_document_ai_extraction(raw_file_ref: str) -> ExtractedInvoiceData:
    """
    Simulates the output of a Document AI service.
    Returns a pre-defined JSON object representing the ExtractedInvoiceData.
    """
    item1 = ItemDetail(
        description="Software Development Services",
        quantity=1,
        unit_price=5000.00,
        tax_percentage=18.0,
        taxable_amount=5000.00,
        calculated_tax=900.00,
        total_amount=5900.00,
    )

    item2 = ItemDetail(
        description="Cloud Hosting",
        quantity=1,
        unit_price=1000.00,
        tax_percentage=18.0,
        taxable_amount=1000.00,
        calculated_tax=180.00,
        total_amount=1180.00,
    )

    return ExtractedInvoiceData(
        invoice_no="INV-2024-001",
        invoice_date=date(2024, 5, 20),
        due_date=date(2024, 6, 19),
        vendor_name="Global Tech Solutions Inc.",
        vendor_gstin="29ABCDE1234F1Z5",
        extracted_subtotal=6000.00,
        extracted_tax_amount=1080.00,
        extracted_total_amount=7080.00,
        item_details=[item1, item2],
        confidence_score=0.95,
        document_ref=raw_file_ref,
    )
