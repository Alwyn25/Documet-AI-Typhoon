import logging
import json
from datetime import datetime
from typing import Dict, Any
from pathlib import Path


class StructuredLogger:
    """Structured logger for OCR agent"""
    
    def __init__(self):
        self.logger = logging.getLogger("ocr_agent")
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
        
        info_log_path = log_dir / "ocr_service.log"
        error_log_path = log_dir / "ocr_service_error.log"
        
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
            "agent": "ocr_agent"
        }
        if data:
            log_data.update(data)
        
        self.logger.info(f"STEP: {json.dumps(log_data)}")
    
    def log_error(self, error_type: str, data: Dict[str, Any] = None):
        """Log an error"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "error": error_type,
            "agent": "ocr_agent"
        }
        if data:
            log_data.update(data)
        
        self.logger.error(f"ERROR: {json.dumps(log_data)}")
    
    def log_ocr_processing(self, document_id: str, filename: str, ocr_type: str):
        """Log OCR processing start"""
        self.log_step("ocr_processing_started", {
            "document_id": document_id,
            "filename": filename,
            "ocr_type": ocr_type
        })
    
    def log_azure_ocr(self, document_id: str, page_count: int):
        """Log Azure OCR completion"""
        self.log_step("azure_ocr_completed", {
            "document_id": document_id,
            "page_count": page_count
        })
    
    def log_tesseract_ocr(self, document_id: str, page_count: int):
        """Log Tesseract OCR completion"""
        self.log_step("tesseract_ocr_completed", {
            "document_id": document_id,
            "page_count": page_count
        })
    
    def log_easyocr_ocr(self, document_id: str, page_count: int):
        """Log EasyOCR completion"""
        self.log_step("easyocr_completed", {
            "document_id": document_id,
            "page_count": page_count
        })
    
    def log_text_merge(self, document_id: str, page_count: int):
        """Log text merging completion"""
        self.log_step("text_merge_completed", {
            "document_id": document_id,
            "page_count": page_count
        })


# Global logger instance
logger = StructuredLogger() 