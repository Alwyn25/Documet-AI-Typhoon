from typing import Dict, Any
from ..services import ocr_processor

class OCRAgent:
    """
    MCP Server for all OCR and data extraction operations.
    """
    def extract_text_cascading(self, file_path: str) -> Dict[str, Any]:
        """
        Tool: Executes the cascading OCR pipeline.
        Calls the ocr_processor service logic.
        """
        print("OCRAgent Tool: ocr/extract_text_cascading called.")
        try:
            result = ocr_processor.perform_cascading_ocr(file_path)

            # Exit Criteria: High confidence score
            if result and result.get("confidence_score", 0) > 80:
                return {
                    "status": "OCR_DONE",
                    "extracted_text": result.get("raw_text"),
                    "ocr_output": result # Pass the full result for the mapper
                }
            else:
                return {
                    "status": "FAILED_OCR",
                    "error": "OCR confidence score was too low or extraction failed."
                }
        except Exception as e:
            print(f"  - Error in extract_text_cascading: {e}")
            return {"status": "FAILED_OCR", "error": str(e)}
