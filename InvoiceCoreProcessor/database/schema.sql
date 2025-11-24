-- PostgreSQL schema for the InvoiceCoreProcessor validation engine

-- 1.1 validation_rule: Master list of all possible validation rules.
CREATE TABLE validation_rule (
    id              SERIAL PRIMARY KEY,
    rule_id         TEXT NOT NULL UNIQUE,           -- e.g., 'DOC-001', 'VND-001'
    category        TEXT NOT NULL,                  -- e.g., 'DOCUMENT_INTEGRITY', 'VENDOR', 'TAX'
    description     TEXT NOT NULL,                  -- Human-readable description of the rule
    severity        SMALLINT NOT NULL CHECK (severity BETWEEN 1 AND 5), -- 1=Low, 5=Fatal
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 1.2 invoice: Core summary record for each processed invoice.
CREATE TABLE invoice (
    id              UUID PRIMARY KEY,
    external_ref    TEXT,                           -- Reference to a job ID or file path
    vendor_id       UUID,                           -- Foreign key to a vendors table (if one exists)
    invoice_no      TEXT NOT NULL,
    invoice_date    DATE NOT NULL,
    currency        TEXT NOT NULL DEFAULT 'INR',
    total_amount    NUMERIC(18, 2) NOT NULL,
    status          TEXT NOT NULL,                  -- e.g. 'PENDING', 'VALIDATED', 'POSTED', 'FLAGGED'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (vendor_id, invoice_no, invoice_date)    -- Basic duplicate prevention constraint
);

-- 1.3 invoice_validation_run: Records each execution of the validation engine for an invoice.
CREATE TABLE invoice_validation_run (
    id              UUID PRIMARY KEY,
    invoice_id      UUID NOT NULL REFERENCES invoice(id) ON DELETE CASCADE,
    run_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    engine_version  TEXT NOT NULL,                  -- e.g., git SHA or semantic version of the rule engine
    overall_score   NUMERIC(5, 2),                  -- The final 0-100 reliability score
    status          TEXT NOT NULL,                  -- 'PASS', 'FAIL', 'WARN'
    summary         JSONB,                          -- Compact summary of the results
    created_by      TEXT NOT NULL DEFAULT 'system'
);

-- 1.4 invoice_validation_result: Stores the outcome for each individual rule within a validation run.
CREATE TABLE invoice_validation_result (
    id                  BIGSERIAL PRIMARY KEY,
    validation_run_id   UUID NOT NULL REFERENCES invoice_validation_run(id) ON DELETE CASCADE,
    rule_id             TEXT NOT NULL REFERENCES validation_rule(rule_id),
    status              TEXT NOT NULL CHECK (status IN ('PASS', 'FAIL', 'WARN')),
    message             TEXT,                       -- e.g., "Vendor GSTIN missing"
    severity            SMALLINT NOT NULL,          -- Copied from validation_rule at run time for historical accuracy
    deduction_points    NUMERIC(5, 2) NOT NULL DEFAULT 0,  -- Score deduction applied for this rule
    meta                JSONB,                      -- Extra data, e.g., { "field": "gstin", "expected": "format", "actual": "BADGST" }
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Optional View for quick access to the latest validation score for each invoice
CREATE VIEW invoice_latest_validation AS
SELECT DISTINCT ON (ivr.invoice_id)
    ivr.invoice_id,
    ivr.id AS validation_run_id,
    ivr.run_at,
    ivr.overall_score,
    ivr.status
FROM invoice_validation_run ivr
ORDER BY ivr.invoice_id, ivr.run_at DESC;

-- --- Initial Data Population for validation_rule Table ---
-- This populates the master rule list from the provided checklist.

INSERT INTO validation_rule (rule_id, category, description, severity, is_active) VALUES
-- Document Integrity
('DOC-001', 'DOCUMENT_INTEGRITY', 'File is readable and not corrupted', 5, TRUE),
('DOC-002', 'DOCUMENT_INTEGRITY', 'Average OCR confidence is above threshold', 3, TRUE),
-- Vendor Validation
('VND-001', 'VENDOR', 'Vendor name is extracted', 4, TRUE),
('VND-002', 'VENDOR', 'GSTIN / Tax ID format is valid', 4, TRUE),
('VND-003', 'VENDOR', 'Vendor exists in vendor master', 3, TRUE),
-- Invoice Header
('INV-001', 'INVOICE_HEADER', 'Invoice number exists and is valid', 5, TRUE),
('INV-002', 'INVOICE_HEADER', 'Invoice number is unique for the vendor', 5, TRUE),
('INV-003', 'INVOICE_HEADER', 'Invoice date is not in the future', 4, TRUE),
('INV-004', 'INVOICE_HEADER', 'Due date is after invoice date', 3, TRUE),
-- Line Items
('LIT-001', 'LINE_ITEMS', 'At least one line item exists', 4, TRUE),
('LIT-004', 'LINE_ITEMS', 'Line item amount equals quantity * unit price', 4, TRUE),
-- Tax
('TAX-001', 'TAX', 'Tax rate is a valid, allowed percentage', 4, TRUE),
('TAX-002', 'TAX', 'Intra/inter-state tax logic (CGST+SGST or IGST) is correct', 5, TRUE),
('TAX-003', 'TAX', 'Tax amount calculation is correct', 5, TRUE),
-- Totals
('TTL-001', 'TOTALS', 'Subtotal matches the sum of line item amounts', 5, TRUE),
('TTL-003', 'TOTALS', 'Grand total matches subtotal + taxes +/- round-off', 5, TRUE),
-- Duplicate Detection
('DUP-001', 'DUPLICATE', 'Duplicate invoice number for the same vendor', 5, TRUE),
-- Anomaly Detection
('ANM-004', 'ANOMALY', 'Field-level OCR confidence is not too low', 2, TRUE),
-- Compliance
('CMP-001', 'COMPLIANCE', 'All mandatory GST fields are present', 5, TRUE);

COMMIT;
