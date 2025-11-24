# InvoiceCoreProcessor API Documentation

## 1. Overview

### 1.1 Purpose
The InvoiceCoreProcessor API provides a programmatic entry point for initiating the automated invoice processing workflow. It exposes a simple REST endpoint to accept invoice files and trigger the backend microservice orchestration for data extraction, validation, and storage.

### 1.2 Authentication
-   **Current Status**: **None**. The API is currently open and does not require authentication, assuming it is deployed within a secure, internal network.
-   **Future Enhancement**: A JWT-based authentication model is planned. Clients will be required to pass a bearer token in the `Authorization` header.

### 1.3 Base URL
-   **Local Development**: `http://localhost:8080`

## 2. Common API Conventions

### 2.1 Request Format
-   All request bodies should be in JSON format with the `Content-Type: application/json` header.

### 2.2 Standard Response Model
-   **Current Status**: The API returns a simple JSON object.
-   **Future Enhancement**: A standardized response envelope will be implemented for consistency:
    ```json
    {
      "success": true,
      "data": {},
      "error": null,
      "meta": {
        "trace_id": "xyz-123",
        "timestamp": "2025-01-01T00:00:00Z"
      }
    }
    ```

### 2.3 Error Handling
-   **Current Status**: In case of a workflow failure, the API returns an `HTTP 500 Internal Server Error` with a default JSON body from the server.
-   **Future Enhancement**: A standardized error structure with specific error codes will be implemented:
    ```json
    {
      "success": false,
      "error": {
        "code": "INTERNAL_ERROR",
        "message": "A downstream microservice failed to respond."
      }
    }
    ```
    **Proposed Error Codes:**
    | Code             | Meaning                                    |
    | ---------------- | ------------------------------------------ |
    | `INVALID_PAYLOAD`  | Request body validation failed.            |
    | `UNAUTHORIZED`   | Authentication token is missing or invalid.|
    | `INTERNAL_ERROR`   | An unexpected server or workflow error.    |

## 3. Endpoints

### 3.1 Initiate Invoice Processing
-   **Summary**: Triggers the end-to-end invoice processing workflow.
-   **HTTP Method**: `POST`
-   **Path**: `/invoice/upload`
-   **Description**: This is the primary endpoint to start processing a new invoice. The request body should contain a reference to the raw file and the user associated with the request.
-   **Auth**: Not Required (currently).

#### Request Body
```json
{
  "raw_file_ref": "string",
  "user_id": "string"
}
```
-   `raw_file_ref`: A string representing the path or reference to the raw invoice file (e.g., a cloud storage path).
-   `user_id`: A unique identifier for the user initiating the request.

#### Response (200 OK)
A successful request indicates that the workflow has been triggered and completed.
```json
{
  "status": "Workflow completed",
  "final_state": "SUCCESS: Invoice processed and stored."
}
```
-   `final_state` will indicate `SUCCESS` or `ANOMALY` based on the validation result.

#### Status Codes
-   `200 OK`: The workflow was initiated and completed successfully.
-   `500 Internal Server Error`: The workflow failed due to an internal error (e.g., a microservice was unavailable).

---
## Future Enhancements (Not Yet Implemented)
---

### 3.2 Get Invoice Processing Status
-   **HTTP Method**: `GET`
-   **Path**: `/api/v1/invoices/{invoice_id}/status`
-   **Description**: Would return the real-time processing status of a specific invoice job.

### 3.3 Get Extracted Invoice Data
-   **HTTP Method**: `GET`
-   **Path**: `/api/v1/invoices/{invoice_id}/extracted`
-   **Description**: Would return all extracted and structured fields for a completed invoice.

### 3.4 Get Validation Results
-   **HTTP Method**: `GET`
-   **Path**: `/api/v1/invoices/{invoice_id}/validation`
-   **Description**: Would return any anomalies or validation flags for a processed invoice.

## 4. Webhooks
-   **Status**: Not Yet Implemented.
-   **Future Plan**: A webhook system will be developed to push real-time status updates (e.g., `invoice.validated`, `invoice.failed`) to subscribed client applications.

## 5. Rate Limits & Throttling
-   **Status**: Not Yet Implemented.
-   **Future Plan**: Rate limiting will be added to the API gateway to ensure fair usage and system stability.

## 6. Changelog
-   **v1.0.0 (Initial Release)**:
    -   Added `POST /invoice/upload` to initiate the processing workflow.
