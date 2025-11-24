from typing import Dict, Any, TypedDict
from langgraph.graph import StateGraph, END
from .models import InvoiceGraphState, StatusEnum
from .mcp_clients import MCPClient

# --- Define the State for the Graph ---

class GraphState(TypedDict):
    """Represents the state of our graph."""
    user_id: str
    file_path: str
    file_content: bytes
    original_filename: str

    mongo_document_id: str
    extracted_text: str
    ocr_output: Dict[str, Any]
    mapped_schema: Dict[str, Any]
    validation_flags: list[str]

    current_status: StatusEnum
    error_message: str

# --- Define the Workflow Nodes ---

def ingestion_node(state: GraphState) -> GraphState:
    print("\n--- WORKFLOW: Ingestion Node ---")
    client = MCPClient()
    result = client.call_tool(
        "datastore",
        "save_metadata",
        file_content=state["file_content"],
        original_filename=state["original_filename"],
        user_id=state["user_id"]
    )
    state["current_status"] = result["status"]
    if result["status"] == "UPLOADED_METADATA_SAVED":
        state["mongo_document_id"] = result["mongo_document_id"]
        state["file_path"] = result["file_path"]
    else:
        state["error_message"] = result.get("error")
    return state

def ocr_node(state: GraphState) -> GraphState:
    print("\n--- WORKFLOW: OCR Node ---")
    client = MCPClient()
    result = client.call_tool("ocr", "extract_text_cascading", file_path=state["file_path"])
    state["current_status"] = result["status"]
    if result["status"] == "OCR_DONE":
        state["extracted_text"] = result["extracted_text"]
        state["ocr_output"] = result["ocr_output"]
    else:
        state["error_message"] = result.get("error")
    return state

def mapping_node(state: GraphState) -> GraphState:
    print("\n--- WORKFLOW: Mapping Node ---")
    client = MCPClient()
    result = client.call_tool("mapper", "execute_mapping", ocr_output=state["ocr_output"])
    state["current_status"] = result["status"]
    if result["status"] == "MAPPING_COMPLETE":
        state["mapped_schema"] = result["mapped_schema"]
    else:
        state["error_message"] = result.get("error")
    return state

def validation_node(state: GraphState) -> GraphState:
    print("\n--- WORKFLOW: Validation Node ---")
    client = MCPClient()
    # In a full implementation, the AnomalyAgent would also call the DataStoreAgent
    # to check for duplicates. We are simplifying that interaction here.
    result = client.call_tool("anomaly", "run_checks", mapped_schema=state["mapped_schema"])
    state["current_status"] = result["status"]
    if result["status"] == "VALIDATED_FLAGGED":
        state["validation_flags"] = result["validation_flags"]
    return state

# --- Simple nodes for terminal states ---
def manual_review_node(state: GraphState) -> GraphState:
    print(f"\n--- WORKFLOW: Routing to Manual Review ---")
    print(f"  - Reason: Status '{state['current_status']}'")
    if state.get("error_message"):
        print(f"  - Error: {state['error_message']}")
    return state

def error_reporting_node(state: GraphState) -> GraphState:
    print(f"\n--- WORKFLOW: Routing to Error Reporting ---")
    print(f"  - Reason: Status '{state['current_status']}'")
    print(f"  - Error: {state['error_message']}")
    return state

# --- Define Conditional Edges (Gating Logic) ---

def decide_after_ingestion(state: GraphState) -> str:
    if state["current_status"] == "UPLOADED_METADATA_SAVED":
        return "continue_to_ocr"
    return "report_error"

def decide_after_ocr(state: GraphState) -> str:
    if state["current_status"] == "OCR_DONE":
        return "continue_to_mapping"
    return "send_to_manual_review"

def decide_after_mapping(state: GraphState) -> str:
    if state["current_status"] == "MAPPING_COMPLETE":
        return "continue_to_validation"
    return "send_to_manual_review"

def decide_after_validation(state: GraphState) -> str:
    if state["current_status"] == "VALIDATED_FLAGGED":
        return "send_to_manual_review"
    # This assumes the next step is data integration, which we will add later.
    return "continue_to_integration"

# --- Build the Graph ---
workflow = StateGraph(GraphState)

workflow.add_node("ingestion", ingestion_node)
workflow.add_node("ocr", ocr_node)
workflow.add_node("mapping", mapping_node)
workflow.add_node("validation", validation_node)
workflow.add_node("manual_review", manual_review_node)
workflow.add_node("error_reporting", error_reporting_node)

def data_integration_node(state: GraphState) -> GraphState:
    print("\n--- WORKFLOW: Data Integration Node ---")
    # This node is simplified; a real version might have more logic
    # to select the target system, format the data, etc.
    from .integration_agent import integration_agent
    result = integration_agent.sync_to_accounting_system(
        record=state["mapped_schema"],
        target_system="TallyPrime" # Hardcoded for now
    )
    state["current_status"] = result["status"]
    if result["status"] != "SYNCED_SUCCESS":
        state["error_message"] = result.get("error")
    return state

def reporting_node(state: GraphState) -> GraphState:
    print("\n--- WORKFLOW: Reporting Node (End) ---")
    print(f"  - Final Status: {state['current_status']}")
    print(f"  - Document ID: {state['mongo_document_id']}")
    return state

# --- Define Conditional Edges (Gating Logic) ---
def decide_after_integration(state: GraphState) -> str:
    if state["current_status"] == "SYNCED_SUCCESS":
        return "continue_to_reporting"
    return "send_to_manual_review"

# --- Build the Graph ---
workflow = StateGraph(GraphState)

workflow.add_node("ingestion", ingestion_node)
workflow.add_node("ocr", ocr_node)
workflow.add_node("mapping", mapping_node)
workflow.add_node("validation", validation_node)
workflow.add_node("data_integration", data_integration_node)
workflow.add_node("manual_review", manual_review_node)
workflow.add_node("error_reporting", error_reporting_node)
workflow.add_node("reporting", reporting_node)

workflow.set_entry_point("ingestion")

workflow.add_conditional_edge("ingestion", decide_after_ingestion, {
    "continue_to_ocr": "ocr", "report_error": "error_reporting"})
workflow.add_conditional_edge("ocr", decide_after_ocr, {
    "continue_to_mapping": "mapping", "send_to_manual_review": "manual_review"})
workflow.add_conditional_edge("mapping", decide_after_mapping, {
    "continue_to_validation": "validation", "send_to_manual_review": "manual_review"})
workflow.add_conditional_edge("validation", decide_after_validation, {
    "continue_to_integration": "data_integration", "send_to_manual_review": "manual_review"})
workflow.add_conditional_edge("data_integration", decide_after_integration, {
    "continue_to_reporting": "reporting", "send_to_manual_review": "manual_review"})

workflow.add_edge("manual_review", END)
workflow.add_edge("error_reporting", END)
workflow.add_edge("reporting", END)

# Compile the graph
app_graph = workflow.compile()
