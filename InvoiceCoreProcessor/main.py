from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from datetime import datetime
from InvoiceCoreProcessor.models.protocol import InvoiceIngestionRequest, ValidatedInvoiceRecord
from InvoiceCoreProcessor.core.workflow import create_invoice_workflow, InvoiceGraphState
from InvoiceCoreProcessor.core.database import init_pool, close_pool

# --- App Lifecycle Management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the database connection pool on startup
    print("--- Initializing database connection pool ---")
    init_pool()
    yield
    # Close the database connection pool on shutdown
    print("--- Closing database connection pool ---")
    close_pool()

app = FastAPI(
    title="SelfContainedInvoiceProcessor",
    description="A secure, scalable, monolithic A2A module for automated invoice processing.",
    lifespan=lifespan
)

# Compile the LangGraph workflow once at startup
invoice_workflow = create_invoice_workflow()

@app.post("/invoice/upload", response_model=ValidatedInvoiceRecord)
async def start_langgraph_workflow(request: InvoiceIngestionRequest):
    """
    Starts the independent invoice processing pipeline.
    """
    # 1. Create the initial state for the workflow
    initial_record = ValidatedInvoiceRecord(
        upload_timestamp=datetime.utcnow(),
        extracted_data=None, # This is now optional
        file_id=request.raw_file_ref
    )

    initial_state = InvoiceGraphState(
        record=initial_record,
        review_needed=False
    )

    # 2. Run the LangGraph workflow
    try:
        final_state = invoice_workflow.invoke(initial_state)
        return final_state['record']
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workflow failed: {str(e)}")


@app.get("/report/summary")
async def generate_dashboard():
    """
    Retrieves the summary dashboard data from Report AI and PostgreSQL.
    (This is a mock implementation)
    """
    return {
        "total_invoices_processed": 1250,
        "invoices_in_review": 15,
        "total_amount_processed": 750000.00,
        "success_rate": "98.8%",
    }

# To run this application:
# uvicorn InvoiceCoreProcessor.main:app --reload
