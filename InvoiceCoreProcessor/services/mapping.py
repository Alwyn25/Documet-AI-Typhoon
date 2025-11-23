from InvoiceCoreProcessor.models.protocol import ExtractedInvoiceData, AccountingSchema


def schema_mapping_service(extracted_data: ExtractedInvoiceData) -> AccountingSchema:
    """
    Maps the ExtractedInvoiceData to the target AccountingSchema for Tally/Zoho.
    """
    line_items_data = [
        {
            "description": item.description,
            "qty": item.quantity,
            "rate": item.unit_price,
            "tax_percentage": item.tax_percentage,
        }
        for item in extracted_data.item_details
    ]

    return AccountingSchema(
        txn_date=extracted_data.invoice_date,
        contact_name=extracted_data.vendor_name,
        gstin=extracted_data.vendor_gstin,
        line_items_data=line_items_data,
        taxable_subtotal=round(extracted_data.extracted_subtotal, 2),
        total_tax_amount=round(extracted_data.extracted_tax_amount, 2),
        grand_total=round(extracted_data.extracted_total_amount, 2),
    )
