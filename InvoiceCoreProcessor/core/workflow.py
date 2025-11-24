from typing import Dict, Any, TypedDict
from langgraph.graph import StateGraph, END
from .models import InvoiceGraphState, StatusEnum, CanonicalInvoice, ValidationReport
from .mcp_clients import MCPClient
from .DataIntegrationAgent import integration_agent

# --- Define the State for the Graph ---
# Use TypedDict for LangGraph compatibility, but backed by Pydantic models for validation.
class GraphState(TypedDict):
    user_id: str
    file_content: bytes
    original_filename: str

    file_path: str
    mongo_document_id: str
    ocr_output: Dict[str, Any]
    canonical_invoice: Dict[str, Any]
    validation_report: Dict[str, Any]
    erp_payload: Dict[str, Any]

    current_status: StatusEnum
    error_message: str

# --- Define the Workflow Nodes ---
def ingestion_node(state: GraphState) -> GraphState:
    print("\n--- WORKFLOW: Ingestion Node ---")
    client = MCPClient()
    result = client.call_tool("datastore", "save_metadata", file_content=state["file_content"], original_filename=state["original_filename"], user_id=state["user_id"])
    state.update(result)
    state["current_status"] = result["status"]
    return state

def ocr_node(state: GraphState) -> GraphState:
    print("\n--- WORKFLOW: OCR Node ---")
    client = MCPClient()
    result = client.call_tool("ocr", "extract_text_cascading", file_path=state["file_path"])
    state.update(result)
    state["current_status"] = result["status"]
    return state

def mapping_node(state: GraphState) -> GraphState:
    print("\n--- WORKFLOW: Mapping Node ---")
    client = MCPClient()
    result = client.call_tool("mapper", "execute_mapping", ocr_output=state["ocr_output"])
    if result["status"] == "MAPPING_COMPLETE":
        # Validate against the Pydantic model
        state["canonical_invoice"] = CanonicalInvoice.model_validate(result["mapped_schema"]).model_dump()
    state["current_status"] = result["status"]
    return state

def validation_node(state: GraphState) -> GraphState:
    print("\n--- WORKFLOW: Validation Node ---")
    client = MCPClient()
    result = client.call_tool("validation", "run_checks", mapped_schema=state["canonical_invoice"])
    if result["status"] in ["VALIDATED_CLEAN", "VALIDATED_FLAGGED"]:
        state["validation_report"] = ValidationReport.model_validate(result).model_dump()
    state["current_status"] = result["status"]
    return state

def data_integration_node(state: GraphState) -> GraphState:
    print("\n--- WORKFLOW: Data Integration Node ---")
    erp_payload = integration_agent.map_to_erp(state["canonical_invoice"])
    state["erp_payload"] = erp_payload
    # In a real system, you would now push this payload. We'll just set the final status.
    state["current_status"] = "SYNCED_SUCCESS"
    return state

# ... (Error and Manual Review nodes remain the same) ...
def manual_review_node(state: GraphState) -> GraphState:
    print(f"\n--- WORKFLOW: Routing to Manual Review ---")
    return state

def error_reporting_node(state: GraphState) -> GraphState:
    print(f"\n--- WORKFLOW: Routing to Error Reporting ---")
    return state

# --- Gating Logic ---
def decide_after_ingestion(state: GraphState) -> str:
    return "continue_to_ocr" if state["current_status"] == "UPLOADED_METADATA_SAVED" else "report_error"

def decide_after_ocr(state: GraphState) -> str:
    return "continue_to_mapping" if state["current_status"] == "OCR_DONE" else "send_to_manual_review"

def decide_after_mapping(state: GraphState) -> str:
    return "continue_to_validation" if state["current_status"] == "MAPPING_COMPLETE" else "send_to_manual_review"

def decide_after_validation(state: GraphState) -> str:
    return "continue_to_integration" if state["current_status"] == "VALIDATED_CLEAN" else "send_to_manual_review"

# --- Build the Graph ---
workflow = StateGraph(GraphState)
workflow.add_node("ingestion", ingestion_node)
workflow.add_node("ocr", ocr_node)
workflow.add_node("mapping", mapping_node)
workflow.add_node("validation", validation_node)
workflow.add_node("data_integration", data_integration_node)
workflow.add_node("manual_review", manual_review_node)
workflow.add_node("error_reporting", error_reporting_node)

workflow.set_entry_point("ingestion")
workflow.add_conditional_edge("ingestion", decide_after_ingestion, {"continue_to_ocr": "ocr", "report_error": "error_reporting"})
workflow.add_conditional_edge("ocr", decide_after_ocr, {"continue_to_mapping": "mapping", "send_to_manual_review": "manual_review"})
workflow.add_conditional_edge("mapping", decide_after_mapping, {"continue_to_validation": "validation", "send_to_manual_review": "manual_review"})
workflow.add_conditional_edge("validation", decide_after_validation, {"continue_to_integration": "data_integration", "send_to_manual_review": "manual_review"})
workflow.add_edge("data_integration", END)
workflow.add_edge("manual_review", END)
workflow.add_edge("error_reporting", END)

app_graph = workflow.compile()
