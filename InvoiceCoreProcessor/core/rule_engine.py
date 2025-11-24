from typing import Dict, Any, List, Tuple
import psycopg2

class RuleEngine:
    """
    Executes a series of validation rules against an invoice and calculates a reliability score.
    """
    def __init__(self, db_conn):
        self.db_conn = db_conn
        self.rules = self._load_rules()

    def _load_rules(self) -> List[Dict[str, Any]]:
        """Loads all active validation rules from the database."""
        print("--- RuleEngine: Loading validation rules from PostgreSQL ---")
        # In a real implementation, this would query the validation_rule table.
        # For now, we'll mock the rules based on the schema.
        mock_rules = [
            {'rule_id': 'INV-001', 'category': 'INVOICE_HEADER', 'severity': 5},
            {'rule_id': 'INV-002', 'category': 'INVOICE_HEADER', 'severity': 5},
            {'rule_id': 'TAX-003', 'category': 'TAX', 'severity': 5},
            {'rule_id': 'TTL-003', 'category': 'TOTALS', 'severity': 5},
            {'rule_id': 'VND-002', 'category': 'VENDOR', 'severity': 4},
        ]
        print(f"  - Loaded {len(mock_rules)} mock rules.")
        return mock_rules

    def execute(self, invoice_data: Dict[str, Any]) -> Tuple[float, List[Dict[str, Any]]]:
        """
        Runs all validation rules against the invoice data and calculates a score.
        Returns the final score and a list of rule results.
        """
        print("--- RuleEngine: Executing validation rules ---")
        initial_score = 100.0
        results = []
        total_deduction = 0.0

        # Mock rule execution
        # Rule INV-001: Invoice number exists
        if invoice_data.get("invoice_no"):
            results.append({"rule_id": "INV-001", "status": "PASS", "deduction": 0})
        else:
            severity = next(r['severity'] for r in self.rules if r['rule_id'] == 'INV-001')
            deduction = severity * 2 # Simple deduction logic
            total_deduction += deduction
            results.append({"rule_id": "INV-001", "status": "FAIL", "deduction": deduction})

        # Rule TTL-003: Grand total matches
        # Simulate a failure for demonstration
        severity = next(r['severity'] for r in self.rules if r['rule_id'] == 'TTL-003')
        deduction = severity * 2
        total_deduction += deduction
        results.append({
            "rule_id": "TTL-003",
            "status": "FAIL",
            "message": "Grand total does not match sum of subtotal and taxes.",
            "deduction": deduction
        })

        final_score = max(0, initial_score - total_deduction)
        print(f"  - Validation complete. Final Score: {final_score}")

        return final_score, results
