# DocumentAI Schema Mapping Service

The schema mapping microservice extracts structured data from OCR text using Large Language Models (LLM). It specializes in mapping unstructured text to predefined JSON schemas, with built-in validation.

## Quick Start

```bash
cd schema_mapping
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS / Linux
pip install -r requirements.txt
python run.py
```

The service defaults to `http://0.0.0.0:8202`.

## Database Setup

Before running the service, ensure PostgreSQL is installed and running. Then create the database:

```bash
# Connect to PostgreSQL
psql -U postgres

# Create database
CREATE DATABASE documentai;

# Exit psql
\q
```

Initialize the database tables:

```bash
python init_database.py
```

## Configuration

Configuration values are defined in `config/shared_settings.py` and can be overridden via environment variables.

- `SCHEMA_MAPPING_SERVICE_HOST` / `HOST`
- `SCHEMA_MAPPING_SERVICE_PORT` / `PORT`
- `SCHEMA_MAPPING_DEBUG` / `DEBUG`
- `OPENAI_API_KEY` - Required for LLM operations
- `LLM_MODEL` - Default: "gpt-4o-mini"
- `LLM_TEMPERATURE` - Default: 0.0
- `GEMINI_API_KEY` - Required for Gemini-based extraction
- `GEMINI_MODEL` - Default: "gemini-2.0-flash"
- `POSTGRES_HOST` / `DB_HOST` - Default: "localhost"
- `POSTGRES_PORT` / `DB_PORT` - Default: 5432
- `POSTGRES_USER` / `DB_USER` - Default: "postgres"
- `POSTGRES_PASSWORD` / `DB_PASSWORD` - Default: "postgres"
- `POSTGRES_DB` / `DB_NAME` - Default: "documentai"

## API

### POST `/api/v1/schema-mapping/`

Extract structured schema from OCR text.

**Request Body**:
```json
{
  "ocr_text": "Invoice #12345\nDate: 2024-01-15\nVendor: ABC Corp...",
  "schema_type": "invoice"
}
```

**Response**:
```json
{
  "success": true,
  "message": "Schema extracted and validated successfully.",
  "document_id": "a1b2c3d4e5f6",
  "extracted_schema": {
    "invoiceNumber": "12345",
    "invoiceDate": "2024-01-15",
    "dueDate": "2024-02-15",
    "vendor": {
      "name": "ABC Corp",
      "gstin": "29ABCDE1234F1Z5",
      "pan": "ABCDE1234F",
      "address": "123 Main St, City"
    },
    "customer": {
      "name": "XYZ Ltd",
      "address": "456 Oak Ave, City"
    },
    "lineItems": [
      {
        "description": "Product A",
        "quantity": 10,
        "unitPrice": 100.0,
        "taxPercent": 18.0,
        "amount": 1180.0
      }
    ],
    "totals": {
      "subtotal": 1000.0,
      "gstAmount": 180.0,
      "roundOff": 0.0,
      "grandTotal": 1180.0
    },
    "paymentDetails": {
      "mode": "Bank Transfer",
      "reference": "TXN123456",
      "status": "Paid"
    }
  },
  "validation_result": {
    "isValid": true,
    "errors": [],
    "warnings": []
  }
}
```

### GET `/api/v1/invoices/{invoice_id}`

Retrieve invoice by ID with all related data (vendor, customer, items, totals, payment, metadata).

**Response**:
```json
{
  "success": true,
  "invoice": {
    "invoice": {
      "invoice_id": 1,
      "invoice_number": "12345",
      "invoice_date": "2024-01-15",
      "due_date": "2024-02-15",
      "created_at": "2024-01-15T10:00:00",
      "updated_at": "2024-01-15T10:00:00"
    },
    "vendor": {
      "vendor_id": 1,
      "invoice_id": 1,
      "name": "ABC Corp",
      "gstin": "29ABCDE1234F1Z5",
      "pan": "ABCDE1234F",
      "address": "123 Main St, City"
    },
    "customer": {
      "customer_id": 1,
      "invoice_id": 1,
      "name": "XYZ Ltd",
      "address": "456 Oak Ave, City"
    },
    "items": [
      {
        "item_id": 1,
        "invoice_id": 1,
        "description": "Product A",
        "quantity": 10.0,
        "unit_price": 100.0,
        "tax_percent": 18.0,
        "amount": 1180.0
      }
    ],
    "totals": {
      "totals_id": 1,
      "invoice_id": 1,
      "subtotal": 1000.0,
      "gst_amount": 180.0,
      "round_off": 0.0,
      "grand_total": 1180.0
    },
    "payment": {
      "payment_id": 1,
      "invoice_id": 1,
      "mode": "Bank Transfer",
      "reference": "TXN123456",
      "status": "Paid"
    },
    "metadata": {
      "metadata_id": 1,
      "invoice_id": 1,
      "upload_timestamp": "2024-01-15T10:00:00",
      "extracted_confidence_score": 100.0,
      "document_id": "a1b2c3d4e5f6",
      "validation_is_valid": true,
      "validation_errors": [],
      "validation_warnings": []
    }
  }
}
```

### GET `/api/v1/health`

Service health information.

### POST `/api/v1/schema-mapping/upload`

Upload a PDF or image, extract invoice data using Gemini, validate it, and store it.

**Request**

`multipart/form-data` with a file field named `file`.

**Response**

Returns the same structure as the text-based schema-mapping endpoint, including the extracted schema and validation result.

## Prompts Module

The service includes a `prompts` module where all extraction and validation prompts are stored:

- `app/prompts/extraction.py` - Contains the extraction schema prompt
- `app/prompts/validation.py` - Contains the validation prompt

You can modify these prompts to customize the extraction and validation behavior.

## Logging

Structured logs are written to:

- `logs/schema_mapping_service.log`
- `logs/schema_mapping_service_error.log`

Console logging is enabled by default.

## Folder Structure

```
schema_mapping/
├── app/
│   ├── config.py
│   ├── main.py
│   ├── models/
│   │   └── schemas.py
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── extraction.py
│   │   └── validation.py
│   ├── routes/
│   │   └── schema_mapping.py
│   ├── services/
│   │   └── schema_mapping_service.py
│   └── utils/
│       └── logging.py
├── logs/
├── README.md
├── requirements.txt
└── run.py
```

## Database Schema

The service uses PostgreSQL with the following tables:

- **invoice** - Main invoice table (invoice_id, invoice_number, invoice_date, due_date)
- **vendorinfo** - Vendor information (name, GSTIN, PAN, address) - Foreign key to invoice
- **customerinfo** - Customer information (name, address) - Foreign key to invoice
- **item_details** - Line items (description, quantity, unit_price, tax_percent, amount) - Foreign key to invoice
- **Totals** - Invoice totals (subtotal, gst_amount, round_off, grand_total) - Foreign key to invoice
- **Paymentinfo** - Payment details (mode, reference, status) - Foreign key to invoice
- **metadata** - Extraction metadata (upload_timestamp, confidence_score, validation results) - Foreign key to invoice

All tables have proper primary keys and foreign key relationships with CASCADE delete.

## Features

- **LLM-Powered Extraction**: Uses OpenAI GPT models to extract structured data from unstructured OCR text
- **Schema Validation**: Automatically validates extracted schemas for consistency and correctness
- **PostgreSQL Integration**: Automatically saves extracted data to PostgreSQL with proper relationships
- **Modular Prompts**: All prompts stored in dedicated module for easy customization
- **Structured Logging**: Comprehensive logging for debugging and monitoring
- **Error Handling**: Robust error handling with detailed error messages

