from fastapi import FastAPI, UploadFile, File
from typing import Dict, Any

# Add the parent directory to the path to allow imports from the 'InvoiceCoreProcessor' package
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from InvoiceCoreProcessor.core.workflow import app_graph
from InvoiceCoreProcessor.core.models import StatusEnum

app = FastAPI()

@app.post("/invoice/upload")
async def process_invoice(user_id: str, file: UploadFile = File(...)):
    """
    This endpoint is the main entry point for the InvoiceCoreProcessor.
    It accepts a file upload, orchestrates the entire agentic workflow,
    and returns the final status.
    """
    print(f"--- FastAPI Gateway: Received upload for user '{user_id}' from file '{file.filename}' ---")

    file_content = await file.read()

    # Initial state for the LangGraph workflow
    initial_state = {
        "user_id": user_id,
        "file_path": "", # This will be populated by the ingestion agent
        "file_content": file_content,
        "original_filename": file.filename,
        "current_status": "UPLOADED",
    }

    # Invoke the LangGraph workflow
    final_state = app_graph.invoke(initial_state)

    print(f"--- FastAPI Gateway: Workflow finished with final state: ---")
    print(final_state)

    # Return a summary of the outcome
    return {
        "document_id": final_state.get("mongo_document_id"),
        "final_status": final_state.get("current_status"),
        "validation_flags": final_state.get("validation_flags"),
        "error": final_state.get("error_message")
    }

if __name__ == "__main__":
    import uvicorn
    from InvoiceCoreProcessor.config.settings import settings

    print("--- Starting FastAPI Gateway ---")
    uvicorn.run(
        "main_processor:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True
    )
