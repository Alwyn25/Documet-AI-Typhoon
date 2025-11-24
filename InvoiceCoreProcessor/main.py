
from dotenv import load_dotenv
from typing import TypedDict
from contextlib import contextmanager
import uuid

from fastapi import FastAPI
from pydantic import BaseModel
from langgraph.graph import StateGraph, END
import uvicorn

from .models import ExtractedInvoiceData, MappedSchema, ValidationResult, ValidatedInvoiceRecord, StoreRequest
from .mcp_client import MCPClient

# Load environment variables
load_dotenv('InvoiceCoreProcessor/.env')

# --- FastAPI App ---
app = FastAPI()

class InvoiceIngestionRequest(BaseModel):
    raw_file_ref: str
    user_id: str

# --- LangGraph State Definition ---
class GraphState(TypedDict):
    ingestion_request: dict
    raw_file_ref: str
    extracted_data: ExtractedInvoiceData
    mapped_schema: MappedSchema
    validation_result: ValidationResult
    final_status: str
    mcp_client: MCPClient

# --- LangGraph Nodes ---
def upload_and_extract(state: GraphState) -> GraphState:
    """Node 1: Generates mock extracted data."""
    print("--- Node: Upload & Extract ---")
    request = state['ingestion_request']
    state['raw_file_ref'] = request['raw_file_ref']

    # MOCK DATA to simulate extraction
    total_amount = 20000.0 if request['user_id'] == 'test_user_2' else 1150.75
    extracted_data = ExtractedInvoiceData(
        invoice_no=f"MOCK-{uuid.uuid4().hex[:6]}",
        vendor_gstin="GSTIN-MOCK-123",
        total_amount=total_amount,
        item_details=[{"item_description": "Mock Item", "unit_price": total_amount, "quantity": 1}],
        confidence_score=0.99
    )

    state['extracted_data'] = extracted_data
    print(f"  - Successfully generated mock data. Invoice No: {state['extracted_data'].invoice_no}")
    return state

def schema_mapping(state: GraphState) -> GraphState:
    print("--- Node: Schema Mapping ---")
    client = state['mcp_client']
    mapped_schema = client.call_mapper(state['extracted_data'])
    if mapped_schema:
        state['mapped_schema'] = mapped_schema
        print("  - Successfully mapped schema.")
    else:
        raise ConnectionError("Failed to map schema.")
    return state

def validation_flagging(state: GraphState) -> GraphState:
    print("--- Node: Validation & Flagging ---")
    client = state['mcp_client']
    user_id = state['ingestion_request']['user_id']
    validation_result = client.call_agent(state['extracted_data'], user_id)
    if validation_result:
        state['validation_result'] = validation_result
        print(f"  - Validation Status: {validation_result.validation_status}")
        print(f"  - Anomaly Flags: {validation_result.anomaly_flags}")
    else:
        raise ConnectionError("Failed to get validation result.")
    return state

def data_integration(state: GraphState) -> GraphState:
    print("--- Node: Data Integration ---")
    client = state['mcp_client']
    validated_record = ValidatedInvoiceRecord(extracted_data=state['extracted_data'], validation_status=state['validation_result'].validation_status, anomaly_flags=state['validation_result'].anomaly_flags, accounting_system_schema=state['mapped_schema'].model_dump_json())
    store_request = StoreRequest(validated_record=validated_record, raw_file_ref=state['raw_file_ref'])
    result = client.call_datastore(store_request)
    if result and result.success:
        state['final_status'] = "SUCCESS: Invoice processed and stored."
        print(f"  - {result.message}")
    else:
        state['final_status'] = "ERROR: Failed to store invoice."
    return state

def manual_review_queue(state: GraphState) -> GraphState:
    print("--- Node: Manual Review ---")
    status = "ANOMALY: Invoice flagged for manual review."
    flags = state['validation_result'].anomaly_flags
    state['final_status'] = f"{status} Flags: {flags}"
    print(f"  - {state['final_status']}")
    return state

def should_send_for_review(state: GraphState) -> str:
    print("--- Edge: Checking validation status... ---")
    return "continue_to_integration" if state['validation_result'].validation_status == 'SUCCESS' else "send_to_review"

workflow = StateGraph(GraphState)
workflow.add_node("UploadAndExtract", upload_and_extract)
workflow.add_node("SchemaMapping", schema_mapping)
workflow.add_node("ValidationFlagging", validation_flagging)
workflow.add_node("DataIntegration", data_integration)
workflow.add_node("ManualReviewQueue", manual_review_queue)
workflow.set_entry_point("UploadAndExtract")
workflow.add_edge("UploadAndExtract", "SchemaMapping")
workflow.add_edge("SchemaMapping", "ValidationFlagging")
workflow.add_conditional_edges("ValidationFlagging", should_send_for_review, {"continue_to_integration": "DataIntegration", "send_to_review": "ManualReviewQueue"})
workflow.add_edge("DataIntegration", END)
workflow.add_edge("ManualReviewQueue", END)
app_graph = workflow.compile()

@app.post("/invoice/upload")
async def upload_invoice(request: InvoiceIngestionRequest):
    client = MCPClient()
    try:
        inputs = {"ingestion_request": request.model_dump(), "mcp_client": client}
        final_state = app_graph.invoke(inputs)
        return {"status": "Workflow completed", "final_state": final_state['final_status']}
    finally:
        client.close()

if __name__ == "__main__":
    import os
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "8080"))
    uvicorn.run("InvoiceCoreProcessor.main:app", host=host, port=port)
