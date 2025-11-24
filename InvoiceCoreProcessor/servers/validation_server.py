from typing import Dict, Any
import psycopg2

from ..config.settings import settings
from ..core.rule_engine import RuleEngine

class ValidationAgent:
    """
    MCP Server upgraded to use a professional-grade validation rule engine.
    """
    def __init__(self):
        self.db_conn = psycopg2.connect(settings.POSTGRES_URI)
        self.rule_engine = RuleEngine(self.db_conn)
        print("ValidationAgent: Initialized RuleEngine.")

    def run_checks(self, mapped_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tool: Performs comprehensive, rule-based validation on the mapped schema.
        """
        print("ValidationAgent Tool: validate/run_checks called.")
        try:
            score, results = self.rule_engine.execute(mapped_schema)

            failed_rules = [r for r in results if r["status"] == "FAIL"]

            if failed_rules:
                return {
                    "status": "VALIDATED_FLAGGED",
                    "validation_flags": [f"{r['rule_id']}: {r.get('message', 'Failed')}" for r in failed_rules],
                    "score": score,
                    "results": results
                }
            else:
                return {
                    "status": "VALIDATED_CLEAN",
                    "score": score,
                    "results": results
                }

        except Exception as e:
            print(f"  - Error in run_checks: {e}")
            return {
                "status": "VALIDATED_FLAGGED",
                "validation_flags": [f"VALIDATION_ENGINE_ERROR: {e}"],
                "score": 0.0
            }

    def __del__(self):
        if self.db_conn:
            self.db_conn.close()
        print("ValidationAgent: DB connection closed.")
