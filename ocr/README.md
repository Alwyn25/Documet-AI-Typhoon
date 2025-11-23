# DocumentAI OCR Agent

The OCR Agent extracts text from images using multiple OCR engines with fallback capabilities.

## Features

- **Multi-Engine OCR**: Typhoon OCR, Azure Document Intelligence, Tesseract, and EasyOCR
- **Intelligent Fallback Strategy**: Tries Typhoon OCR first, then Azure, then Tesseract, then EasyOCR
- **Text Merging**: Appends OCR text to existing text_content per page
- **LangGraph Workflow**: Structured processing pipeline
- **MongoDB Integration**: Stores processed documents in `ocr_agent` collection

## Architecture

```
OCR Agent (Port 8002)
├── Typhoon OCR (Primary) - AI-powered OCR with markdown output
├── Azure Document Intelligence (Fallback 1) - Enterprise OCR solution
├── Tesseract OCR (Fallback 2) - Open-source OCR
└── EasyOCR (Fallback 3) - Deep learning OCR
```

> **📖 NEW:** See [README_TYPHOON_OCR.md](README_TYPHOON_OCR.md) for detailed Typhoon OCR integration guide

## Setup

1. **Install Dependencies**:
   ```bash
   cd ocr_agent
   pip install -r requirements.txt
   ```

2. **Environment Configuration**:
   Copy `env.txt` to `.env` and configure:
   ```env
   # MongoDB Configuration
   MONGODB_URI=mongodb://localhost:27017/
   DATABASE_NAME=DocumentAi
   COLLECTION_NAME=ocr_agent

   # Server Configuration
   HOST=0.0.0.0
   PORT=8002
   DEBUG=True

   # Typhoon OCR (Primary - Recommended)
   TYPHOON_OCR_API_KEY=your_typhoon_api_key

   # Azure Document Intelligence (Optional)
   AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=your_endpoint
   AZURE_DOCUMENT_INTELLIGENCE_KEY=your_key

   # OCR Configuration
   TESSERACT_CMD_PATH=path_to_tesseract
   EASYOCR_LANGUAGES=en
   ```

3. **Install Tesseract** (Optional):
   - Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
   - Linux: `sudo apt-get install tesseract-ocr`
   - macOS: `brew install tesseract`

## Usage

### Start the Agent

```bash
cd ocr_agent
python run.py
```

### API Endpoints

#### POST `/api/v1/ocr/`

Process documents with OCR.

**Request Body**:
```json
{
  "processed_documents": [
    {
      "document_id": "uuid",
      "filename": "document.pdf",
      "document_type": "pdf",
      "total_pages": 1,
      "total_images": 2,
      "total_words": 150,
      "total_characters": 1200,
      "pages": [
        {
          "page_number": 1,
          "text_content": "Existing text...",
          "images": [
            {
              "image_id": "img_1",
              "page_number": 1,
              "base64_data": "base64_encoded_image",
              "image_format": "PNG",
              "width": 800,
              "height": 600,
              "position": {
                "x": 100,
                "y": 200,
                "width": 800,
                "height": 600
              }
            }
          ],
          "word_count": 150,
          "character_count": 1200
        }
      ],
      "processing_timestamp": "2025-08-02T12:00:00",
      "processing_status": "completed",
      "processing_errors": []
    }
  ]
}
```

**Response**:
```json
{
  "success": true,
  "message": "Processed 1 documents with OCR",
  "processed_documents": [
    {
      "document_id": "uuid",
      "filename": "document.pdf",
      "pages": [
        {
          "page_number": 1,
          "text_content": "Existing text...\n\nExtracted text...",
          "ocr_texts": ["Extracted text..."],
          "ocr_used": ["Typhoon OCR"],
          "images": [
            {
              "image_id": "img_1",
              "page_number": 1,
              "base64_data": "base64_encoded_image",
              "image_format": "PNG",
              "width": 800,
              "height": 600,
              "position": {
                "x": 100,
                "y": 200,
                "width": 800,
                "height": 600
              }
            }
          ],
          "word_count": 150,
          "character_count": 1200
        }
      ],
      "total_pages": 1,
      "ocr_timestamp": "2025-08-02T12:00:00",
      "ocr_status": "completed",
      "ocr_errors": []
    }
  ],
  "total_documents": 1,
  "errors": []
}
```

#### GET `/api/v1/health`

Health check endpoint.

#### GET `/api/v1/documents/`

List all OCR processed documents.

#### GET `/api/v1/documents/{document_id}`

Get a specific OCR processed document.

> ℹ️ The `{document_id}` path value can be either the MongoDB `_id` or the OCR document's `document_id` UUID. The API automatically resolves both.

#### POST `/api/v1/typhoon/upload`

Upload a single PDF or image and call the upstream Typhoon OCR API (via `https://api.opentyphoon.ai/v1/ocr`).  
Use `multipart/form-data` with a `file` field (and optional `pages` form field for PDFs).

**Response** (excerpt):
```json
{
  "success": true,
  "message": "Typhoon OCR completed",
  "pages_processed": 1,
  "extracted_texts": [
    "Raw markdown/text transcription..."
  ]
}
```

#### Engine-specific OCR endpoints

- `POST /api/v1/ocr/typhoon/` &mdash; Run the local Typhoon-first pipeline only (no fallbacks).
- `POST /api/v1/ocr/azure/` &mdash; Force Azure Document Intelligence.
- `POST /api/v1/ocr/tesseract/` &mdash; Force Tesseract OCR.
- `POST /api/v1/ocr/easyocr/` &mdash; Force EasyOCR.
- `POST /api/v1/ocr/gpt4vision/` &mdash; Use GPT-4 Vision for high-accuracy OCR (page-by-page extraction).

Each endpoint accepts the same multipart upload format as `/api/v1/ocr/`. These dedicated endpoints replace the old automatic fallback mechanism when you want a specific engine.

## OCR Engines

### Prompt Module

All OCR prompts are centralized in the `ocr/app/prompts/` module:

- **`typhoon.py`**: Contains Typhoon OCR system prompt and extraction prompt following SCB 10X guidelines
- **`gpt4_vision.py`**: Contains GPT-4 Vision extraction prompt optimized for financial/legal documents

These prompts are imported and used by their respective services to ensure consistent, high-quality text extraction across all OCR engines.

### Token Estimation

The service includes token estimation utilities (`ocr/app/utils/token_estimator.py`) for Typhoon models:

- **Language detection**: Automatically detects Thai vs English text
- **Token estimation**: 
  - Thai text: ~2.5 tokens per word
  - English text: ~1.3 tokens per word
- **Context limit checking**: Validates requests against Typhoon's 8K token context window
- **Warnings**: Logs warnings when token limits are approached or exceeded

Token estimation is automatically performed before Typhoon API calls and logged for monitoring purposes.

### 1. Typhoon OCR (Primary) ⭐ NEW
- **Pros**: State-of-the-art AI OCR, markdown output, high accuracy
- **Cons**: Requires API key, cloud-based
- **Setup**: Configure `TYPHOON_OCR_API_KEY` in env.txt
- **Details**: See [README_TYPHOON_OCR.md](README_TYPHOON_OCR.md)

### 2. Azure Document Intelligence (Fallback 1)
- **Pros**: High accuracy, handles complex layouts
- **Cons**: Requires Azure subscription
- **Setup**: Configure `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` and `AZURE_DOCUMENT_INTELLIGENCE_KEY`

### 3. Tesseract OCR (Fallback 2)
- **Pros**: Open source, good accuracy
- **Cons**: Requires installation
- **Setup**: Install Tesseract and configure `TESSERACT_CMD_PATH`

### 4. EasyOCR (Fallback 3)
- **Pros**: Easy to use, good for simple text
- **Cons**: Slower than others
- **Setup**: Automatically installed with requirements

## Workflow

1. **Input Validation**: Validates document structure and required fields
2. **OCR Processing**:
   - Default `/api/v1/ocr/` uses the multi-engine sequence Typhoon → Azure → Tesseract → EasyOCR.
   - Engine-specific endpoints run only the selected engine (no fallbacks).
   - `/api/v1/ocr/gpt4vision/` invokes GPT-4 Vision for premium extraction when needed.
   - `/api/v1/typhoon/upload` proxies to the hosted Typhoon OCR API.
3. **Text Merging**: Appends OCR text to existing text_content
4. **Database Storage**: Saves processed documents to MongoDB

## Testing

Run the Typhoon OCR test script:
```bash
python test_typhoon_ocr.py
```

Or test the full OCR agent:
```bash
python test_ocr_agent.py  # If available
```

## Integration

The OCR Agent works with the Document Processing Agent:
1. Document Processing Agent extracts images from documents
2. OCR Agent processes those images to extract text
3. Text is merged with existing content and stored

## Logging

Structured logging with JSON format:
```json
{
  "timestamp": "2025-08-02T12:00:00",
  "step": "ocr_processing_started",
  "agent": "ocr_agent",
  "document_id": "uuid",
  "filename": "document.pdf",
  "ocr_type": "multi_engine"
}
``` 