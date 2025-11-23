import unittest
from datetime import date
from InvoiceCoreProcessor.models.protocol import ExtractedInvoiceData, ItemDetail
from InvoiceCoreProcessor.services.mapping import schema_mapping_service


class TestSchemaMapping(unittest.TestCase):

    def test_schema_mapping_service(self):
        # Create a sample ExtractedInvoiceData object
        item1 = ItemDetail(
            description="Test Item 1",
            quantity=1,
            unit_price=100.0,
            tax_percentage=18.0,
            taxable_amount=100.0,
            calculated_tax=18.0,
            total_amount=118.0,
        )
        extracted_data = ExtractedInvoiceData(
            invoice_no="TEST-001",
            invoice_date=date(2024, 1, 1),
            vendor_name="Test Vendor",
            vendor_gstin="123456789012345",
            extracted_subtotal=100.0,
            extracted_tax_amount=18.0,
            extracted_total_amount=118.0,
            item_details=[item1],
            confidence_score=0.99,
            document_ref="test_ref",
        )

        # Call the schema mapping service
        accounting_schema = schema_mapping_service(extracted_data)

        # Assert that the mapping is correct
        self.assertEqual(accounting_schema.txn_date, extracted_data.invoice_date)
        self.assertEqual(accounting_schema.contact_name, extracted_data.vendor_name)
        self.assertEqual(accounting_schema.gstin, extracted_data.vendor_gstin)
        self.assertEqual(accounting_schema.taxable_subtotal, 100.0)
        self.assertEqual(accounting_schema.total_tax_amount, 18.0)
        self.assertEqual(accounting_schema.grand_total, 118.0)
        self.assertEqual(len(accounting_schema.line_items_data), 1)
        self.assertEqual(accounting_schema.line_items_data[0]['description'], "Test Item 1")


if __name__ == '__main__':
    unittest.main()
