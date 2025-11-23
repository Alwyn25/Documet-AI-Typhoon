from typing import TypedDict
from langgraph.graph import StateGraph, END
from InvoiceCoreProcessor.models.protocol import ValidatedInvoiceRecord, Anomaly
from InvoiceCoreProcessor.services.extraction import simulated_document_ai_extraction
from InvoiceCoreProcessor.services.mapping import schema_mapping_service
from InvoiceCoreProcessor.services.validation import validation_service_anomaly_agent
from InvoiceCoreProcessor.core.database import check_duplicate_invoice


class InvoiceGraphState(TypedDict):
    """
    The state object passed between nodes in the LangGraph workflow.
    """
    record: ValidatedInvoiceRecord
    # Simplified flag for conditional routing
    review_needed: bool


def extraction_node(state: InvoiceGraphState) -> InvoiceGraphState:
    """Node to perform document extraction."""
    print("--- Running Document Extraction ---")
    record = state['record']
    # In a real scenario, the raw_file_ref would be used to fetch the document
    # For now, we pass it to the simulation function.
    extracted_data = simulated_document_ai_extraction(record.file_id)
    record.extracted_data = extracted_data
    return {"record": record, "review_needed": state.get("review_needed", False)}


def schema_mapping_node(state: InvoiceGraphState) -> InvoiceGraphState:
    """Node to map extracted data to the accounting schema."""
    print("--- Running Schema Mapping ---")
    record = state['record']
    accounting_schema = schema_mapping_service(record.extracted_data)
    record.accounting_system_schema = accounting_schema
    return {"record": record, "review_needed": state.get("review_needed", False)}


def validation_node(state: InvoiceGraphState) -> InvoiceGraphState:
    """Node to perform validation and anomaly detection."""
    print("--- Running Validation ---")
    record = state['record']
    # Inject the database dependency into the validation service
    validated_record = validation_service_anomaly_agent(record, check_duplicate_invoice)
    return {"record": validated_record, "review_needed": validated_record.review_required}


def data_integration_node(state: InvoiceGraphState):
    """Node to simulate data integration with accounting systems."""
    # This is a placeholder for the A2A SDK call.
    print("--- Integrating Data with Accounting System (Tally/Zoho) ---")
    # In a real implementation, you would use:
    # A2A_SDK_INTEGRATION_MODULE.sync_to_accounting_system(
    #     target="TallyPrime, ZohoBooks",
    #     data=state['record'].accounting_system_schema.dict()
    # )
    print("Data integration complete.")
    return state


def manual_review_node(state: InvoiceGraphState):
    """Node to handle invoices that require manual review."""
    print("--- Sending Invoice for Manual Review ---")
    # This is a placeholder for the A2A SDK call.
    # A2A_SDK_REPORT_MODULE.send_for_manual_review(
    #     invoice_record=state['record'].dict()
    # )
    print("Invoice flagged for manual review.")
    return state


def should_continue(state: InvoiceGraphState) -> str:
    """Conditional edge to determine the next step after validation."""
    if state["review_needed"]:
        return "manual_review"
    else:
        return "data_integration"


def create_invoice_workflow():
    """Creates and returns the LangGraph workflow for invoice processing."""
    workflow = StateGraph(InvoiceGraphState)

    workflow.add_node("document_extraction", extraction_node)
    workflow.add_node("schema_mapping", schema_mapping_node)
    workflow.add_node("validation", validation_node)
    workflow.add_node("data_integration", data_integration_node)
    workflow.add_node("manual_review", manual_review_node)

    workflow.set_entry_point("document_extraction")

    workflow.add_edge("document_extraction", "schema_mapping")
    workflow.add_edge("schema_mapping", "validation")
    workflow.add_conditional_edges(
        "validation",
        should_continue,
        {
            "manual_review": "manual_review",
            "data_integration": "data_integration",
        },
    )
    workflow.add_edge("data_integration", END)
    workflow.add_edge("manual_review", END)

    return workflow.compile()
