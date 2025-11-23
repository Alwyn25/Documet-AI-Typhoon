# Testing Validation Service

## How to Get Comparison Results

The validation service runs **separately** from the schema mapping service. After extracting and saving an invoice via the schema mapping service, you need to call the validation service to get comparison results.

## Step 1: Extract and Save Invoice (Schema Mapping Service)

```bash
POST http://localhost:8202/api/v1/schema-mapping/
Content-Type: application/json

{
  "ocr_text": "...",
  "schema_type": "invoice"
}
```

This saves the invoice to PostgreSQL and returns the extracted schema.

## Step 2: Validate Invoice (Validation Service)

```bash
POST http://localhost:8203/api/v1/validate/
Content-Type: application/json

{
  "invoiceNumber": "GST112020",
  "invoiceDate": "04-Mar-2020",
  "dueDate": "19-Mar-2020",
  "vendor": {
    "name": "GUJARAT FREIGHT TOOLS",
    "gstin": "24HDE7487RE5RT4",
    "pan": null,
    "address": "64, Akshay Industrial Estate\nNear New Cloath Market,\nAhmedabad - 38562"
  },
  "customer": {
    "name": "Kevin Motors",
    "address": "Chandani Chok, New Delhi, Opposite\nStatue, New Delhi, Delhi - 110014"
  },
  "lineItems": [
    {
      "description": "Automatic Saw",
      "quantity": 1,
      "unitPrice": 586,
      "taxPercent": 9,
      "amount": 638.74
    },
    {
      "description": "Stanley Hammer\nClaw Hammer Steel Shaft\n(Black and Chrome)",
      "quantity": 1,
      "unitPrice": 568,
      "taxPercent": 9,
      "amount": 619.12
    }
  ],
  "totals": {
    "subtotal": 1154,
    "gstAmount": 103.86,
    "roundOff": null,
    "grandTotal": 1258
  },
  "paymentDetails": {
    "mode": null,
    "reference": null,
    "status": null
  }
}
```

## Expected Response Structure

The validation service will return:

```json
{
  "success": true,
  "message": "Validation completed successfully.",
  "invoice_exists": true,
  "invoice_id": 2,
  "duplicate_by_criteria": false,
  "comparisons": [
    {
      "entity_type": "invoice",
      "exists_in_db": true,
      "is_identical": true/false,
      "differences": [...],
      "existing_data": {...},
      "new_data": {...}
    },
    {
      "entity_type": "vendor",
      "exists_in_db": true,
      "is_identical": true/false,
      "differences": [...],
      "existing_data": {...},
      "new_data": {...}
    },
    {
      "entity_type": "customer",
      "exists_in_db": true,
      "is_identical": true/false,
      "differences": [...],
      "existing_data": {...},
      "new_data": {...}
    },
    {
      "entity_type": "line_items",
      "exists_in_db": true,
      "is_identical": true/false,
      "differences": [...],
      "existing_data": {...},
      "new_data": {...}
    },
    {
      "entity_type": "totals",
      "exists_in_db": true,
      "is_identical": true/false,
      "differences": [...],
      "existing_data": {...},
      "new_data": {...}
    },
    {
      "entity_type": "payment",
      "exists_in_db": true,
      "is_identical": true/false,
      "differences": [...],
      "existing_data": {...},
      "new_data": {...}
    }
  ],
  "summary": {
    "total_entities": 6,
    "identical_count": 5,
    "different_count": 1,
    "new_count": 0,
    "total_differences": 1
  },
  "missing_value_checks": {
    "errors": [],
    "warnings": []
  },
  "tax_validation_errors": [],
  "llm_summary": {
    "summary": "...",
    "errors": [...],
    "warnings": [...],
    "severity": "moderate"
  }
}
```

## Quick Test with cURL

```bash
curl -X POST http://localhost:8203/api/v1/validate/ \
  -H "Content-Type: application/json" \
  -d '{
    "invoiceNumber": "GST112020",
    "invoiceDate": "04-Mar-2020",
    "dueDate": "19-Mar-2020",
    "vendor": {
      "name": "GUJARAT FREIGHT TOOLS",
      "gstin": "24HDE7487RE5RT4",
      "pan": null,
      "address": "64, Akshay Industrial Estate\nNear New Cloath Market,\nAhmedabad - 38562"
    },
    "customer": {
      "name": "Kevin Motors",
      "address": "Chandani Chok, New Delhi, Opposite\nStatue, New Delhi, Delhi - 110014"
    },
    "lineItems": [
      {
        "description": "Automatic Saw",
        "quantity": 1,
        "unitPrice": 586,
        "taxPercent": 9,
        "amount": 638.74
      },
      {
        "description": "Stanley Hammer\nClaw Hammer Steel Shaft\n(Black and Chrome)",
        "quantity": 1,
        "unitPrice": 568,
        "taxPercent": 9,
        "amount": 619.12
      }
    ],
    "totals": {
      "subtotal": 1154,
      "gstAmount": 103.86,
      "roundOff": null,
      "grandTotal": 1258
    },
    "paymentDetails": {
      "mode": null,
      "reference": null,
      "status": null
    }
  }'
```

## Troubleshooting

1. **No comparisons returned**: Check validation service logs for errors
2. **Invoice not found**: Verify invoice number matches exactly (case-sensitive)
3. **Empty comparisons**: Check database connection and ensure invoice was saved correctly

