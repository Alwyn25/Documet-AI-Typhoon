from typing import Dict, Any
from ..services import mapping

class SchemaMapperAgent:
    """
    MCP Server for mapping OCR output to a structured schema.
    """
    def execute_mapping(self, ocr_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tool: Executes the LLM-based schema mapping.
        Calls the mapping service logic.
        """
        print("SchemaMapperAgent Tool: map/execute called.")
        try:
            mapped_schema = mapping.map_schema_with_llm(ocr_output)

            # Exit Criteria: All required fields are non-null
            required_fields = ["invoice_no", "date", "total_amount"]
            if mapped_schema and all(mapped_schema.get(field) is not None for field in required_fields):
                return {
                    "status": "MAPPING_COMPLETE",
                    "mapped_schema": mapped_schema
                }
            else:
                return {
                    "status": "FAILED_MAPPING",
                    "error": "LLM failed to populate all required fields."
                }
        except Exception as e:
            print(f"  - Error in execute_mapping: {e}")
            return {"status": "FAILED_MAPPING", "error": str(e)}
