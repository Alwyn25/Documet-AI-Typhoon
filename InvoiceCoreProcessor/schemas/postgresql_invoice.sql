CREATE TABLE IF NOT EXISTS invoices (
    id SERIAL PRIMARY KEY,
    vendor_gstin VARCHAR(15) NOT NULL,
    invoice_no VARCHAR(255) NOT NULL,
    invoice_date DATE NOT NULL,
    upload_timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    validation_status VARCHAR(50) NOT NULL,
    review_required BOOLEAN DEFAULT FALSE,
    raw_file_ref VARCHAR(255),
    -- Storing the full extracted data as JSONB for detailed logging and potential reprocessing
    extracted_data JSONB,
    -- Storing the final accounting schema as JSONB for integration records
    accounting_system_schema JSONB,
    -- Storing anomaly flags as JSONB for detailed error reporting
    anomaly_flags JSONB
);
