from typing import Callable, List
from InvoiceCoreProcessor.models.protocol import ValidatedInvoiceRecord, Anomaly


def validation_service_anomaly_agent(
    invoice_record: ValidatedInvoiceRecord,
    duplicate_checker: Callable[[str, str, str], bool]
) -> ValidatedInvoiceRecord:
    """
    Performs deep validation (tax, duplicate, amount check) and flags anomalies.
    The duplicate checking logic is injected as a dependency.
    """
    anomalies: List[Anomaly] = []
    extracted_data = invoice_record.extracted_data

    # 1. Missing Data Check
    if not extracted_data.vendor_gstin or len(extracted_data.vendor_gstin) != 15:
        anomalies.append(Anomaly(
            flag_type="MISSING_DATA",
            message=f"Vendor GSTIN is missing or invalid. Received: '{extracted_data.vendor_gstin}'"
        ))

    if not extracted_data.invoice_no:
        anomalies.append(Anomaly(
            flag_type="MISSING_DATA",
            message="Invoice number is missing."
        ))

    # 2. Tax Mismatch Check
    calculated_tax_sum = sum(item.calculated_tax for item in extracted_data.item_details)
    if abs(round(calculated_tax_sum, 2) - round(extracted_data.extracted_tax_amount, 2)) > 0.02:
        anomalies.append(Anomaly(
            flag_type="TAX_MISMATCH",
            message=(f"Calculated tax sum ({calculated_tax_sum:.2f}) does not match "
                     f"extracted tax amount ({extracted_data.extracted_tax_amount:.2f}).")
        ))

    # 3. Amount Mismatch Check
    calculated_total = extracted_data.extracted_subtotal + extracted_data.extracted_tax_amount
    if abs(round(calculated_total, 2) - round(extracted_data.extracted_total_amount, 2)) > 1.00:
        anomalies.append(Anomaly(
            flag_type="AMOUNT_MISMATCH",
            message=(f"Subtotal + Tax ({calculated_total:.2f}) does not match "
                     f"grand total ({extracted_data.extracted_total_amount:.2f}).")
        ))

    # 4. Duplicate Invoice Check (using injected dependency)
    if extracted_data.vendor_gstin and extracted_data.invoice_no:
        is_duplicate = duplicate_checker(
            extracted_data.vendor_gstin,
            extracted_data.invoice_no,
            extracted_data.invoice_date,
        )
        if is_duplicate:
            anomalies.append(Anomaly(
                flag_type="DUPLICATE_INVOICE",
                message="An invoice with the same Vendor GSTIN, Invoice No, and a similar date already exists."
            ))

    if anomalies:
        invoice_record.validation_status = "ANOMALY"
        invoice_record.anomaly_flags.extend(anomalies)
        invoice_record.review_required = True
    else:
        invoice_record.validation_status = "SUCCESS"
        invoice_record.review_required = False

    return invoice_record
