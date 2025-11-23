import logging
import json
from datetime import datetime
from typing import Dict, Any
from pathlib import Path


class StructuredLogger:
    """Structured logger for Schema Mapping agent"""
    
    def __init__(self):
        self.logger = logging.getLogger("schema_mapping_agent")
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            self._configure_handlers()
    
    def _configure_handlers(self) -> None:
        """Configure logger handlers for console and file outputs."""
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handlers
        log_dir = Path(__file__).resolve().parents[2] / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        info_log_path = log_dir / "schema_mapping_service.log"
        error_log_path = log_dir / "schema_mapping_service_error.log"
        
        info_handler = logging.FileHandler(info_log_path, encoding="utf-8")
        info_handler.setLevel(logging.INFO)
        info_handler.setFormatter(formatter)
        
        error_handler = logging.FileHandler(error_log_path, encoding="utf-8")
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        
        self.logger.addHandler(info_handler)
        self.logger.addHandler(error_handler)
        self.logger.propagate = False
    
    def log_step(self, step: str, data: Dict[str, Any] = None):
        """Log a processing step"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "step": step,
            "agent": "schema_mapping_agent"
        }
        if data:
            log_data.update(data)
        
        self.logger.info(f"STEP: {json.dumps(log_data)}")
    
    def log_error(self, error_type: str, data: Dict[str, Any] = None):
        """Log an error"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "error": error_type,
            "agent": "schema_mapping_agent"
        }
        if data:
            log_data.update(data)
        
        self.logger.error(f"ERROR: {json.dumps(log_data)}")
    
    def log_extraction(self, document_id: str, schema_type: str):
        """Log schema extraction start"""
        self.log_step("schema_extraction_started", {
            "document_id": document_id,
            "schema_type": schema_type
        })
    
    def log_validation(self, document_id: str, is_valid: bool):
        """Log validation completion"""
        self.log_step("schema_validation_completed", {
            "document_id": document_id,
            "is_valid": is_valid
        })


# Global logger instance
logger = StructuredLogger()

