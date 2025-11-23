
import uuid
from typing import TypedDict
from contextlib import contextmanager
import os
from dotenv import load_dotenv

from fastapi import FastAPI
from pydantic import BaseModel
from langgraph.graph import StateGraph, END
import uvicorn

from .models import ExtractedInvoiceData, MappedSchema, ValidationResult, ValidatedInvoiceRecord, StoreRequest
from .mcp_client import MCPClient

# Load environment variables
load_dotenv()

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
# ... (Node definitions remain the same)
def upload_and_extract(state: GraphState) -> GraphState:
    print("--- Node: Upload & Extract ---")
    request = state['ingestion_request']
    state['raw_file_ref'] = request['raw_file_ref']
    extracted_data = ExtractedInvoiceData(invoice_no=f"INV-{uuid.uuid4().hex[:6]}", vendor_gstin="GSTIN-ABC-123", total_amount=1150.75 if "high_value" not in request['raw_file_ref'] else 20000.0, item_details=[{"item_description": "Product A", "unit_price": 500.0, "quantity": 2}, {"item_description": "Service B", "unit_price": 150.75, "quantity": 1}], confidence_score=0.97)
    state['extracted_data'] = extracted_data
    print(f"  - Extracted Invoice No: {extracted_data.invoice_no}")
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
    validation_result = client.call_agent(state['extracted_data'])
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

# --- Graph Definition & Compilation ---
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

# --- API Endpoint ---
@app.post("/invoice/upload")
async def upload_invoice(request: InvoiceIngestionRequest):
    client = MCPClient()
    try:
        inputs = {"ingestion_request": request.model_dump(), "mcp_client": client}
        final_state = app_graph.invoke(inputs)
        return {"status": "Workflow completed", "final_state": final_state['final_status']}
    finally:
        client.close()

# --- Server Startup ---
if __name__ == "__main__":
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "8080"))
    uvicorn.run(app, host=host, port=port)
