from typing import Dict, Any

class DataIntegrationAgent:
    """
    Transforms the canonical invoice schema into a detailed, ERP-ready format
    and generates the final payload for the target system.
    """
    def map_to_erp(self, canonical_invoice: Dict[str, Any], target_system: str = "ZOHO") -> Dict[str, Any]:
        """
        Takes the canonical invoice data and produces the final mapped_invoice schema.
        """
        print(f"\n--- DataIntegrationAgent: Mapping to ERP schema for {target_system} ---")

        # In a real system, this mapping logic would be much more complex,
        # involving lookups to vendor masters, tax code tables, etc.

        # Mock Vendor Mapping
        vendor_mapping = {
            "vendor_name": canonical_invoice.get("vendor", {}).get("name"),
            "vendor_gstin": canonical_invoice.get("vendor", {}).get("gstin"),
            "vendor_code": "VEN-MOCK-001",
            "ledger_name": canonical_invoice.get("vendor", {}).get("name"),
        }

        # Mock Tax Mapping (assuming intra-state)
        tax_mapping = {
            "type": "INTRA_STATE",
            "sgst_rate": 9.0,
            "cgst_rate": 9.0,
            "igst_rate": 0.0,
            "tax_accounts": { "sgst_ledger": "Input SGST 9%", "cgst_ledger": "Input CGST 9%" }
        }

        # Mock Final Payload Generation (for Zoho)
        zoho_payload = {
            "customer_id": "CUST-MOCK-001",
            "invoice_date": canonical_invoice.get("invoice_date"),
            "due_date": canonical_invoice.get("due_date"),
            "line_items": [
                {
                    "item_id": f"ITEM-MOCK-{item.get('hsn', '0000')}",
                    "description": item.get("description"),
                    "quantity": item.get("qty"),
                    "rate": item.get("unit_price"),
                    "tax_id": "TAX-MOCK-GST18"
                } for item in canonical_invoice.get("items", [])
            ]
        }

        mapped_invoice = {
            "invoice_id": canonical_invoice.get("invoice_id"),
            "agent": "DataIntegrationAgent",
            "target_system": target_system,
            "status": "READY",
            "vendor_mapping": vendor_mapping,
            "tax_mapping": tax_mapping,
            "payload": {
                "tally": None,
                "zoho": zoho_payload
            }
        }

        print("--- DataIntegrationAgent: Successfully mapped to ERP schema ---")
        return mapped_invoice

integration_agent = DataIntegrationAgent()
