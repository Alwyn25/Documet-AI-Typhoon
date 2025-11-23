"""Extraction prompts for schema mapping"""

EXTRACTION_SCHEMA_PROMPT = """

You are an expert schema mapping agent specializing in invoices. 

First, analyze the OCR-extracted text from the invoice image. Then, map the extracted information to the following structured JSON schema. If a field is not present in the extracted text, use a value of null.

The JSON schema should be:

{
  "invoiceNumber": string | null,
  "invoiceDate": string | null,
  "dueDate": string | null,
  "vendor": {
    "name": string | null,
    "gstin": string | null,
    "pan": string | null,
    "address": string | null
  },
  "customer": {
    "name": string | null,
    "address": string | null
  },
  "lineItems": [
    {
      "description": string,
      "quantity": number,
      "unitPrice": number,
      "taxPercent": number,
      "amount": number
    }
  ],
  "totals": {
    "subtotal": number,
    "gstAmount": number,
    "roundOff": number | null,
    "grandTotal": number
  },
  "paymentDetails": {
    "mode": string | null,
    "reference": string | null,
    "status": "Paid" | "Unpaid" | "Partial" | null
  }
}

Return ONLY the raw JSON object. Do not include any explanatory text, markdown formatting, or anything else.

"""

