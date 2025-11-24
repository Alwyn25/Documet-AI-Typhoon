
from dotenv import load_dotenv
from typing import TypedDict

from fastapi import FastAPI
from pydantic import BaseModel
from langgraph.graph import StateGraph, END
import uvicorn

# Need to navigate up to the project root for correct module resolution
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from InvoiceCoreProcessor.mcp_client import MCPClient

# Load environment variables
load_dotenv('InvoiceCoreProcessor/.env')

# --- FastAPI App ---
app = FastAPI()

class InvoiceIngestionRequest(BaseModel):
    invoice_path: str
    user_id: str

# --- LangGraph State Definition ---
class GraphState(TypedDict):
    ingestion_request: dict
    document_id: str
    final_status: str

# --- LangGraph Node ---
def ingestion(state: GraphState) -> GraphState:
    """Node 1: Calls the IngestionAgent to process and store the invoice."""
    print("--- Node: Ingestion ---")
    request = state['ingestion_request']
    client = MCPClient()
    try:
        response = client.call_ingestion(
            invoice_path=request['invoice_path'],
            user_id=request['user_id']
        )
        if response and response.success:
            state['document_id'] = response.document_id
            state['final_status'] = "SUCCESS: Invoice ingested."
            print(f"  - Ingestion successful. Document ID: {response.document_id}")
        else:
            raise ConnectionError(response.message if response else "Ingestion service call failed.")
    finally:
        client.close()

    return state

# --- Workflow Definition ---
workflow = StateGraph(GraphState)
workflow.add_node("ingestion", ingestion)
workflow.set_entry_point("ingestion")
workflow.add_edge("ingestion", END)
app_graph = workflow.compile()

# --- API Endpoint ---
@app.post("/invoice/upload")
async def upload_invoice(request: InvoiceIngestionRequest):
    try:
        inputs = {"ingestion_request": request.model_dump()}
        final_state = app_graph.invoke(inputs)
        return {"status": "Workflow completed", "final_state": final_state}
    except Exception as e:
        return {"status": "Workflow failed", "error": str(e)}

# --- Server Startup ---
if __name__ == "__main__":
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "8080"))
    uvicorn.run("InvoiceCoreProcessor.main:app", host=host, port=port)
