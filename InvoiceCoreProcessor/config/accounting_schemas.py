# This file contains example target schemas for various accounting systems.
# In a real-world application, these might be more complex and could be
# loaded from a configuration file or a database.

TALLY_SCHEMA = {
    "VOUCHER": {
        "DATE": "YYYY-MM-DD",
        "VOUCHERTYPENAME": "Purchase",
        "PARTYLEDGERNAME": "string",
        "NARRATION": "string",
        "ALLLEDGERENTRIES.LIST": [
            {
                "LEDGERNAME": "string",
                "ISDEEMEDPOSITIVE": "Yes",
                "AMOUNT": "float"
            }
        ]
    }
}

ZOHO_BOOKS_SCHEMA = {
    "customer_id": "string",
    "line_items": [
        {
            "item_id": "string",
            "name": "string",
            "rate": "float",
            "quantity": "float"
        }
    ],
    "invoice_number": "string",
    "total": "float"
}
