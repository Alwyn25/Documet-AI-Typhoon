from typing import Dict, Any
from ..services import validation

class AnomalyAgent:
    """
    MCP Server for performing all validation checks.
    """
    def run_checks(self, mapped_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tool: Performs validation checks (Tax, Duplicates, Consistency, etc.).
        Calls the validation service logic.
        """
        print("AnomalyAgent Tool: validate/run_checks called.")
        try:
            anomalies = validation.run_validation_checks(mapped_schema)

            if anomalies:
                return {
                    "status": "VALIDATED_FLAGGED",
                    "validation_flags": anomalies
                }
            else:
                return {"status": "VALIDATED_CLEAN"}

        except Exception as e:
            print(f"  - Error in run_checks: {e}")
            # In a real system, you might want a more specific error status
            return {"status": "VALIDATED_FLAGGED", "validation_flags": [f"VALIDATION_ERROR: {e}"]}
