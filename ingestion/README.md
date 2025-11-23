# DocumentAI Ingestion Service

The ingestion microservice accepts document uploads (PDF, Word, and common image formats), stores them in the configured uploads directory, and returns structured metadata for each file.

## Quick Start

```bash
cd ingestion
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS / Linux
pip install -r requirements.txt
python run.py
```

The service defaults to `http://0.0.0.0:8201`.

## Configuration

Configuration values are defined in `config/shared_settings.py` and can be overridden via environment variables.

- `INGESTION_SERVICE_HOST` / `HOST`
- `INGESTION_SERVICE_PORT` / `PORT`
- `INGESTION_DEBUG` / `DEBUG`
- `INGESTION_STORAGE_DIR` / `STORAGE_ROOT`
- `MAX_FILE_SIZE_MB`

The upload directory defaults to `ingestion/uploads`. It is created automatically on startup and during ingestion.

## API

### POST `/api/v1/ingestion/`

Upload one or more files.

**Request**  
`multipart/form-data` where `files` is a list of file inputs.

**Response**

```json
{
  "success": true,
  "message": "Ingested 2 documents successfully.",
  "total_documents": 2,
  "documents": [
    {
      "document_id": "c6a2e64a6ec04c3ea6e5a9dcba40e8df",
      "original_filename": "contract.pdf",
      "stored_filename": "c6a2e64a6ec04c3ea6e5a9dcba40e8df.pdf",
      "content_type": "application/pdf",
      "extension": "pdf",
      "size_bytes": 125467,
      "size_mb": 0.1196,
      "storage_path": "D:/Documet-AI_Typhoon/ingestion/uploads/c6a2e64a6ec04c3ea6e5a9dcba40e8df.pdf",
      "uploaded_at": "2025-11-13T04:45:09.274328Z"
    }
  ]
}
```

### GET `/api/v1/health`

Service health information.

## Logging

Structured logs are written to:

- `logs/ingestion_service.log`
- `logs/ingestion_service_error.log`

Console logging is enabled by default.

## Folder Structure

```
ingestion/
├── app/
│   ├── config.py
│   ├── main.py
│   ├── models/
│   ├── routes/
│   │   └── ingestion.py
│   ├── services/
│   │   └── ingestion_service.py
│   └── utils/
│       └── logging.py
├── uploads/
├── README.md
├── requirements.txt
└── run.py
```


