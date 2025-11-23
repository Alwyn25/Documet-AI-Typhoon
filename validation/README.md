# Validation Service

Validation microservice for DocumentAI that checks if invoice entities exist in PostgreSQL database and compares them with new data.

## Overview

The Validation service provides functionality to:
- Check if an invoice exists in the database by invoice number
- Compare all invoice entities (vendor, customer, line items, totals, payment) between existing database records and new data
- Generate detailed comparison reports showing differences
- Provide summary statistics about entity matches and differences

## Directory Structure

```
validation/
├── app/
│   ├── __init__.py
│   ├── config.py              # Service configuration
│   ├── main.py                # FastAPI application
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py         # Pydantic models for requests/responses
│   ├── routes/
│   │   ├── __init__.py
│   │   └── validation.py      # API routes
│   ├── services/
│   │   ├── __init__.py
│   │   └── validation_service.py  # Core validation logic
│   └── utils/
│       ├── __init__.py
│       ├── database.py         # PostgreSQL connection manager
│       └── logging.py          # Structured logging
├── logs/                       # Log files directory
├── requirements.txt           # Python dependencies
├── run.py                     # Service entry point
└── README.md                  # This file
```

## Installation

1. Install dependencies:
```bash
cd validation
pip install -r requirements.txt
```

2. Configure environment variables (optional):
Create a `.env` file in the `validation/` directory or use the root `.env` file:
```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_USER=postgres
POSTGRES_PASSWORD=Password123
POSTGRES_DB=invoice_db
```

## Running the Service

### Development Mode
```bash
python run.py
```

The service will start on `http://localhost:8203` by default.

### Production Mode
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8203
```

## API Endpoints

### POST `/api/v1/validate/`

Validate an invoice by comparing it with existing database records.

**Request Body:**
```json
{
  "invoice_number": "GST112020",
  "invoice_date": "2020-03-04",
  "due_date": "2020-03-19",
  "vendor": {
    "name": "GUJARAT FREIGHT TOOLS",
    "gstin": "24AABCU9603R1ZX",
    "pan": "AABCU9603R",
    "address": "123 Main St"
  },
  "customer": {
    "name": "Kevin Motors",
    "address": "Chandani Chok, New Delhi"
  },
  "line_items": [
    {
      "description": "Product 1",
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
  "payment_details": {
    "mode": "Bank Transfer",
    "reference": "REF123",
    "status": "Paid"
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Validation completed successfully.",
  "invoice_exists": true,
  "invoice_id": 1,
  "comparisons": [
    {
      "entity_type": "invoice",
      "exists_in_db": true,
      "is_identical": true,
      "differences": [],
      "existing_data": {...},
      "new_data": {...}
    },
    {
      "entity_type": "vendor",
      "exists_in_db": true,
      "is_identical": false,
      "differences": [
        {
          "field": "address",
          "existing": "Old Address",
          "new": "123 Main St"
        }
      ],
      "existing_data": {...},
      "new_data": {...}
    }
  ],
  "summary": {
    "total_entities": 6,
    "existing_count": 6,
    "identical_count": 5,
    "different_count": 1,
    "new_count": 0,
    "total_differences": 1
  }
}
```

### GET `/api/v1/validate/{invoice_number}`

Validate an invoice by invoice number (fetches all data from database and returns comparison).

**Response:** Same as POST endpoint, but only compares with database data (no new data provided).

### GET `/api/v1/health`

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "agent": "validation_agent"
}
```

## Validation Logic

The validation service performs the following checks:

1. **Invoice Check**: Searches for invoice by `invoice_number` in the `invoice` table
2. **Entity Comparison**: If invoice exists, compares:
   - Invoice basic info (invoice_number, invoice_date, due_date)
   - Vendor information (name, gstin, pan, address)
   - Customer information (name, address)
   - Line items (description, quantity, unit_price, tax_percent, amount)
   - Totals (subtotal, gst_amount, round_off, grand_total)
   - Payment details (mode, reference, status)

3. **Difference Detection**: For each entity, identifies:
   - Fields that differ between existing and new data
   - Missing entities in database
   - New entities not in database

4. **Summary Generation**: Provides statistics about:
   - Total entities checked
   - Number of existing entities
   - Number of identical entities
   - Number of different entities
   - Number of new entities
   - Total number of field differences

## Database Schema

The service expects the following PostgreSQL tables (same as schema_mapping service):
- `invoice` - Main invoice table
- `vendorinfo` - Vendor information
- `customerinfo` - Customer information
- `item_details` - Line items
- `Totals` - Invoice totals
- `Paymentinfo` - Payment details
- `metadata` - Metadata (not compared)

## Configuration

Service configuration is managed through:
- `config/shared_settings.py` - Shared defaults
- `app/config.py` - Service-specific settings
- Environment variables (`.env` file)

Key configuration options:
- `VALIDATION_SERVICE_PORT` - Service port (default: 8203)
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` - Database connection

## Logging

Logs are written to:
- `logs/validation_service.log` - General logs
- `logs/validation_service_error.log` - Error logs

Logs use structured JSON format for easy parsing and analysis.

## Error Handling

The service handles:
- Missing invoice numbers
- Database connection errors
- Invalid request data
- Missing entities in database

All errors are logged with detailed context and return appropriate HTTP status codes.

## Integration

The validation service can be integrated with:
- **Schema Mapping Service**: Validate extracted schemas before saving
- **OCR Service**: Validate OCR results
- **Ingestion Service**: Validate uploaded documents

## Development

To extend the validation service:
1. Add new entity types in `services/validation_service.py`
2. Add comparison methods for new entities
3. Update models in `models/schemas.py` if needed
4. Add new routes in `routes/validation.py` if needed

## License

Part of the DocumentAI Typhoon project.

