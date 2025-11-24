# InvoiceCoreProcessor API Documentation

## 1. Overview

### 1.1 Purpose
The InvoiceCoreProcessor API provides a programmatic entry point for initiating the automated invoice processing workflow. It exposes a simple REST endpoint to accept invoice files and trigger the backend microservice orchestration, **which now includes a real, multi-engine OCR pipeline for data extraction.**

### 1.2 Authentication
-   **Current Status**: **None**.

### 1.3 Base URL
-   **Local Development**: `http://localhost:8080`

## 2. Common API Conventions
*(No changes in this section)*

## 3. Endpoints

### 3.1 Initiate Invoice Processing
-   **Summary**: Triggers the end-to-end invoice processing workflow, starting with OCR extraction.
-   **HTTP Method**: `POST`
-   **Path**: `/invoice/upload`
-   **Description**: This is the primary endpoint to start processing a new invoice. The request body should contain a reference to the raw file. The system will then use its configured OCR engines to extract data from the referenced file.
-   **Auth**: Not Required (currently).

#### Request Body
```json
{
  "raw_file_ref": "string",
  "user_id": "string"
}
```

#### Response (200 OK)
A successful request indicates that the workflow, including the OCR step, was triggered and completed.
```json
{
  "status": "Workflow completed",
  "final_state": "SUCCESS: Invoice processed and stored."
}
```

---
*(The rest of the document, including Future Enhancements, remains the same.)*
---
