import io
import os
import base64
import cv2
import numpy as np
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional, TypedDict
from datetime import datetime
from uuid import uuid4
from PIL import Image
import fitz  # PyMuPDF
import json
from bson import ObjectId

# OCR Libraries
# Note: Typhoon OCR now uses the API service (typhoon_api_service)
# We still check if typhoon_ocr package is available for compatibility
try:
    import typhoon_ocr
    TYPHOON_AVAILABLE = True
except ImportError:
    TYPHOON_AVAILABLE = False

try:
    from azure.ai.formrecognizer import DocumentAnalysisClient
    from azure.core.credentials import AzureKeyCredential
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

from langgraph.graph import StateGraph, END
from fastapi import UploadFile  # type: ignore[import-not-found]

from ..utils.logging import logger
from ..utils.mongo import mongo_manager
from ..config import settings
from ..services.typhoon_api_service import typhoon_api_service


class OCRState(TypedDict):
    """State for the OCR workflow using TypedDict for LangGraph compatibility"""
    input_data: List[Dict[str, Any]]
    processed_documents: List[Dict[str, Any]]
    errors: List[str]
    current_document: Optional[Dict[str, Any]]
    engine_sequence: List[str]


def serialize_for_json(obj):
    """Convert MongoDB objects to JSON serializable format"""
    if isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_json(item) for item in obj]
    else:
        return obj


class OCRService:
    """Service for OCR text extraction with multiple fallbacks"""
    
    def __init__(self):
        self.graph = self._build_workflow()
        self._initialize_ocr_engines()
        self.default_engine_sequence = ["typhoon", "azure", "tesseract", "easyocr"]
    
    def _initialize_ocr_engines(self):
        """Initialize OCR engines"""
        # Typhoon OCR (Primary)
        self.typhoon_available = TYPHOON_AVAILABLE
        self.typhoon_api_key = None
        if TYPHOON_AVAILABLE:
            self.typhoon_api_key = settings.TYPHOON_OCR_API_KEY or settings.OPENAI_API_KEY
            if self.typhoon_api_key:
                logger.log_step("typhoon_ocr_initialized", {"status": "success"})
            else:
                logger.log_step("typhoon_ocr_no_api_key", {"status": "warning", "message": "TYPHOON_OCR_API_KEY or OPENAI_API_KEY not set"})
        
        # Azure Document Intelligence (Fallback 1)
        self.azure_client = None
        if AZURE_AVAILABLE:
            endpoint = settings.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT
            key = settings.AZURE_DOCUMENT_INTELLIGENCE_KEY
            if endpoint and key:
                try:
                    self.azure_client = DocumentAnalysisClient(
                        endpoint=endpoint, 
                        credential=AzureKeyCredential(key)
                    )
                    logger.log_step("azure_ocr_initialized", {"status": "success"})
                except Exception as e:
                    logger.log_error("azure_ocr_init_failed", {"error": str(e)})
        
        # Tesseract (Fallback 2)
        self.tesseract_available = TESSERACT_AVAILABLE
        if TESSERACT_AVAILABLE:
            tesseract_path = settings.TESSERACT_CMD_PATH
            if tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
            logger.log_step("tesseract_ocr_initialized", {"status": "success"})
        
        # EasyOCR (Fallback 3)
        self.easyocr_reader = None
        if EASYOCR_AVAILABLE:
            try:
                languages = settings.easyocr_languages_list or ["en"]
                self.easyocr_reader = easyocr.Reader(languages)
                logger.log_step("easyocr_initialized", {"status": "success"})
            except Exception as e:
                logger.log_error("easyocr_init_failed", {"error": str(e)})
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow for OCR processing"""
        
        # Define the state schema
        workflow = StateGraph(OCRState)
        
        # Add nodes
        workflow.add_node("validate_input", self._validate_input)
        workflow.add_node("process_documents", self._process_documents)
        workflow.add_node("save_to_database", self._save_to_database)
        
        # Set entry point
        workflow.set_entry_point("validate_input")
        
        # Define edges
        workflow.add_edge("validate_input", "process_documents")
        workflow.add_edge("process_documents", "save_to_database")
        workflow.add_edge("save_to_database", END)
        
        return workflow.compile()
    
    async def prepare_documents_from_uploads(self, files: List[UploadFile]) -> List[Dict[str, Any]]:
        """Convert uploaded files into the internal processed_documents structure."""
        documents: List[Dict[str, Any]] = []
        
        for upload in files:
            filename = upload.filename or f"uploaded_{uuid4().hex}"
            content_type = (upload.content_type or "").lower()
            file_bytes = await upload.read()
            
            if not file_bytes:
                raise ValueError(f"Uploaded file '{filename}' is empty.")
            
            suffix = Path(filename).suffix.lower()
            is_pdf = content_type == "application/pdf" or suffix == ".pdf"
            
            if is_pdf:
                document = self._prepare_pdf_document(file_bytes, filename)
            else:
                document = self._prepare_image_document(file_bytes, filename, content_type or suffix)
            
            documents.append(document)
            
            logger.log_step("upload_converted", {
                "filename": filename,
                "document_id": document["document_id"],
                "document_type": document.get("document_type"),
                "total_pages": document.get("total_pages"),
                "total_images": document.get("total_images")
            })
        
        return documents
    
    def _prepare_pdf_document(self, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Prepare a PDF upload for OCR processing."""
        document_id = str(uuid4())
        pdf = fitz.open(stream=file_bytes, filetype="pdf")
        
        pages: List[Dict[str, Any]] = []
        total_images = 0
        
        for page_index, page in enumerate(pdf, start=1):
            pix = page.get_pixmap()
            img_bytes = pix.tobytes("png")
            base64_data = base64.b64encode(img_bytes).decode("utf-8")
            total_images += 1
            
            image_payload = {
                "image_id": f"{document_id}_page_{page_index}_img_1",
                "page_number": page_index,
                "base64_data": base64_data,
                "image_format": "PNG",
                "width": pix.width,
                "height": pix.height,
                "position": None
            }
            
            pages.append({
                "page_number": page_index,
                "text_content": "",
                "images": [image_payload],
                "word_count": 0,
                "character_count": 0
            })
        
        pdf.close()
        
        return {
            "document_id": document_id,
            "filename": filename,
            "document_type": "pdf",
            "total_pages": len(pages),
            "total_images": total_images,
            "pages": pages,
            "processing_timestamp": datetime.utcnow().isoformat(),
            "processing_status": "uploaded",
            "processing_errors": []
        }
    
    def _prepare_image_document(self, file_bytes: bytes, filename: str, content_type: Optional[str]) -> Dict[str, Any]:
        """Prepare an image upload for OCR processing."""
        document_id = str(uuid4())
        
        image = Image.open(io.BytesIO(file_bytes))
        width, height = image.size
        
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        normalized_bytes = buffer.getvalue()
        image.close()
        
        base64_data = base64.b64encode(normalized_bytes).decode("utf-8")
        
        image_payload = {
            "image_id": f"{document_id}_img_1",
            "page_number": 1,
            "base64_data": base64_data,
            "image_format": "PNG",
            "width": width,
            "height": height,
            "position": None,
            "original_content_type": content_type
        }
        
        pages = [{
            "page_number": 1,
            "text_content": "",
            "images": [image_payload],
            "word_count": 0,
            "character_count": 0
        }]
        
        return {
            "document_id": document_id,
            "filename": filename,
            "document_type": "image",
            "total_pages": 1,
            "total_images": 1,
            "pages": pages,
            "processing_timestamp": datetime.utcnow().isoformat(),
            "processing_status": "uploaded",
            "processing_errors": []
        }
    
    def _validate_input(self, state: OCRState) -> OCRState:
        """Validate input data"""
        logger.log_step("validating_ocr_input", {
            "document_count": len(state["input_data"])
        })
        
        errors = state.get("errors", [])
        valid_documents = []
        
        for doc_data in state["input_data"]:
            try:
                # Check required fields for document processing agent output
                required_fields = ["document_id", "filename", "pages"]
                for field in required_fields:
                    if field not in doc_data:
                        error_msg = f"Missing required field '{field}' in document data"
                        errors.append(error_msg)
                        continue
                
                # Check if pages have text_content
                if not doc_data.get("pages"):
                    error_msg = f"No pages found in document: {doc_data.get('filename', 'unknown')}"
                    errors.append(error_msg)
                    continue
                
                # Check if pages have images for OCR processing
                pages_with_images = 0
                for page in doc_data.get("pages", []):
                    if page.get("images"):
                        pages_with_images += 1
                
                # Log document info but process all documents regardless of images
                if pages_with_images == 0:
                    logger.log_step("document_no_images", {
                        "document_id": doc_data.get("document_id"),
                        "filename": doc_data.get("filename"),
                        "note": "Document will be processed without OCR (no images found)"
                    })
                else:
                    logger.log_step("document_with_images", {
                        "document_id": doc_data.get("document_id"),
                        "filename": doc_data.get("filename"),
                        "pages_with_images": pages_with_images
                    })
                
                valid_documents.append(doc_data)
                
            except Exception as e:
                error_msg = f"Error validating document data: {str(e)}"
                errors.append(error_msg)
        
        # Update state
        state["input_data"] = valid_documents
        state["errors"] = errors
        
        logger.log_step("ocr_input_validation_completed", {
            "valid_documents": len(valid_documents),
            "errors": len(errors)
        })
        
        return state
    
    def _process_documents(self, state: OCRState) -> OCRState:
        """Process documents with OCR"""
        logger.log_step("starting_ocr_processing", {
            "document_count": len(state["input_data"])
        })
        
        processed_documents = []
        errors = state.get("errors", [])
        engine_sequence = state.get("engine_sequence") or self.default_engine_sequence
        
        for doc_data in state["input_data"]:
            try:
                document_id = doc_data["document_id"]
                filename = doc_data["filename"]
                
                # Check if document has images for OCR
                total_images = doc_data.get("total_images", 0)
                if total_images > 0:
                    logger.log_ocr_processing(document_id, filename, "multi_engine")
                else:
                    logger.log_step("document_processing_no_images", {
                        "document_id": document_id,
                        "filename": filename,
                        "note": "Processing document without OCR (no images)"
                    })
                
                # Process each page with OCR
                processed_pages = []
                for page in doc_data["pages"]:
                    try:
                        processed_page = self._process_page_with_ocr(page, document_id, engine_sequence)
                        processed_pages.append(processed_page)
                    except Exception as e:
                        error_msg = f"Error processing page {page.get('page_number', 'unknown')}: {str(e)}"
                        errors.append(error_msg)
                        logger.log_error("page_ocr_failed", {
                            "document_id": document_id,
                            "page_number": page.get('page_number'),
                            "error": str(e)
                        })
                
                # Aggregate token usage for entire document
                document_token_usage = None
                all_page_tokens = [page.get("token_usage") for page in processed_pages if page.get("token_usage")]
                if all_page_tokens:
                    total_doc_input = sum(usage.get("input_tokens", 0) for usage in all_page_tokens)
                    total_doc_output = sum(usage.get("output_tokens", 0) or 0 for usage in all_page_tokens)
                    document_token_usage = {
                        "input_tokens": total_doc_input,
                        "output_tokens": total_doc_output if total_doc_output > 0 else None,
                        "total_tokens": total_doc_input + total_doc_output,
                        "pages_with_tokens": len(all_page_tokens),
                        "details": all_page_tokens
                    }
                
                # Create processed document
                processed_document = {
                    "document_id": document_id,
                    "filename": filename,
                    "pages": processed_pages,
                    "total_pages": len(processed_pages),
                    "ocr_timestamp": datetime.utcnow().isoformat(),
                    "ocr_status": "completed",
                    "ocr_errors": [],
                    "token_usage": document_token_usage
                }
                
                processed_documents.append(processed_document)
                
            except Exception as e:
                error_msg = f"Error processing document {doc_data.get('filename', 'unknown')}: {str(e)}"
                errors.append(error_msg)
                logger.log_error("document_ocr_failed", {
                    "filename": doc_data.get("filename"),
                    "error": str(e)
                })
        
        # Update state
        state["processed_documents"] = processed_documents
        state["errors"] = errors
        
        logger.log_step("ocr_processing_completed", {
            "processed_documents": len(processed_documents),
            "errors": len(errors)
        })
        
        return state
    
    def _process_page_with_ocr(self, page: Dict[str, Any], document_id: str, engine_sequence: List[str]) -> Dict[str, Any]:
        """Process a single page with OCR"""
        page_number = page["page_number"]
        original_text = page.get("text_content", "")
        images = page.get("images", [])
        
        # Extract OCR text from images
        ocr_texts: List[str] = []
        ocr_used: List[str] = []
        
        # Track token usage for this page
        page_token_usage: List[Dict[str, Any]] = []
        
        if images:
            for img_index, image in enumerate(images):
                try:
                    # Get base64 image data
                    base64_data = image.get("base64_data")
                    if not base64_data:
                        continue
                    
                    # Decode base64 to image
                    img_bytes = base64.b64decode(base64_data)
                    img = Image.open(io.BytesIO(img_bytes))
                    
                    # Convert to OpenCV format for OCR
                    img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
                    
                    for engine in engine_sequence:
                        text, token_usage = self._extract_text_by_engine(engine, img_cv, img_bytes)
                        if text:
                            ocr_texts.append(text)
                            ocr_used.append(self._engine_display_name(engine))
                            self._log_engine_success(engine, document_id, page_number)
                            
                            # Store token usage if available
                            if token_usage:
                                token_usage["engine"] = engine
                                token_usage["image_index"] = img_index
                                page_token_usage.append(token_usage)
                            break
                    
                except Exception as e:
                    logger.log_error("image_ocr_failed", {
                        "document_id": document_id,
                        "page_number": page_number,
                        "image_index": img_index,
                        "error": str(e)
                    })
        else:
            # Log that page has no images for OCR
            logger.log_step("page_no_images", {
                "document_id": document_id,
                "page_number": page_number,
                "note": "Page has no images for OCR processing"
            })
        
        # Merge original text with OCR text
        merged_text = original_text
        if ocr_texts:
            merged_text += "\n\n" + "\n\n".join(ocr_texts)
            logger.log_text_merge(document_id, page_number)
        else:
            logger.log_step("page_no_ocr_text", {
                "document_id": document_id,
                "page_number": page_number,
                "note": "No OCR text extracted from page"
            })
        
        # Aggregate token usage for this page
        aggregated_token_usage = None
        if page_token_usage:
            total_input = sum(usage.get("input_tokens", 0) for usage in page_token_usage)
            total_output = sum(usage.get("output_tokens", 0) or 0 for usage in page_token_usage)
            aggregated_token_usage = {
                "input_tokens": total_input,
                "output_tokens": total_output if total_output > 0 else None,
                "total_tokens": total_input + total_output,
                "engines": [usage.get("engine") for usage in page_token_usage],
                "details": page_token_usage  # Full details per engine/image
            }
        
        # Return processed page
        return {
            "page_number": page_number,
            "text_content": merged_text,
            "ocr_texts": ocr_texts,
            "ocr_used": ocr_used,
            "word_count": len(merged_text.split()),
            "character_count": len(merged_text),
            "token_usage": aggregated_token_usage
        }
    
    def _extract_text_by_engine(self, engine: str, img_cv: np.ndarray, img_bytes: bytes) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
        engine = engine.lower()
        if engine == "typhoon":
            return self._extract_text_typhoon(img_bytes)
        if engine == "azure":
            text = self._extract_text_azure(img_cv)
            return text, None  # Azure doesn't provide token usage
        if engine == "tesseract":
            text = self._extract_text_tesseract(img_cv)
            return text, None  # Tesseract doesn't provide token usage
        if engine == "easyocr":
            text = self._extract_text_easyocr(img_cv)
            return text, None  # EasyOCR doesn't provide token usage
        return None, None

    def _engine_display_name(self, engine: str) -> str:
        return {
            "typhoon": "Typhoon OCR",
            "azure": "Azure OCR",
            "tesseract": "Tesseract OCR",
            "easyocr": "EasyOCR",
        }.get(engine.lower(), engine)

    def _log_engine_success(self, engine: str, document_id: str, page_number: int) -> None:
        if engine == "typhoon":
            logger.log_step("typhoon_ocr_success", {
                "document_id": document_id,
                "page_number": page_number
            })
        elif engine == "azure":
            logger.log_azure_ocr(document_id, page_number)
        elif engine == "tesseract":
            logger.log_tesseract_ocr(document_id, page_number)
        elif engine == "easyocr":
            logger.log_easyocr_ocr(document_id, page_number)

    def _extract_text_typhoon(self, img_bytes: bytes) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Extract text using Typhoon OCR API service"""
        if not self.typhoon_available or not self.typhoon_api_key:
            return None, None
        
        try:
            # Use Typhoon API service for consistent token estimation and error handling
            extracted_text, token_usage = typhoon_api_service.extract_text_from_bytes(
                file_bytes=img_bytes,
                filename="ocr_image.png",
                content_type="image/png"
            )
            text = extracted_text.strip() if extracted_text and extracted_text.strip() else None
            return text, token_usage
            
        except Exception as e:
            logger.log_error("typhoon_ocr_failed", {"error": str(e)})
            return None, None
    
    def _extract_text_azure(self, image: np.ndarray) -> Optional[str]:
        """Extract text using Azure Document Intelligence"""
        if not self.azure_client:
            return None
        
        try:
            # Convert image to bytes
            _, img_encoded = cv2.imencode('.png', image)
            img_bytes = img_encoded.tobytes()
            
            # Analyze document
            poller = self.azure_client.begin_analyze_document(
                "prebuilt-document", img_bytes
            )
            result = poller.result()
            
            # Extract text
            text_parts = []
            for page in result.pages:
                for line in page.lines:
                    text_parts.append(line.content)
            
            return " ".join(text_parts) if text_parts else None
            
        except Exception as e:
            logger.log_error("azure_ocr_failed", {"error": str(e)})
            return None
    
    def _extract_text_tesseract(self, image: np.ndarray) -> Optional[str]:
        """Extract text using Tesseract OCR"""
        if not self.tesseract_available:
            return None
        
        try:
            # Preprocess image for better OCR
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Extract text
            text = pytesseract.image_to_string(binary)
            return text.strip() if text.strip() else None
            
        except Exception as e:
            logger.log_error("tesseract_ocr_failed", {"error": str(e)})
            return None
    
    def _extract_text_easyocr(self, image: np.ndarray) -> Optional[str]:
        """Extract text using EasyOCR"""
        if not self.easyocr_reader:
            return None
        
        try:
            # Extract text
            results = self.easyocr_reader.readtext(image)
            
            # Combine all detected text
            text_parts = []
            for (bbox, text, prob) in results:
                if prob > 0.5:  # Confidence threshold
                    text_parts.append(text)
            
            return " ".join(text_parts) if text_parts else None
            
        except Exception as e:
            logger.log_error("easyocr_failed", {"error": str(e)})
            return None
    
    def _save_to_database(self, state: OCRState) -> OCRState:
        """Save processed documents to MongoDB"""
        logger.log_step("saving_ocr_documents", {
            "document_count": len(state["processed_documents"])
        })
        
        errors = state.get("errors", [])
        
        for doc_data in state["processed_documents"]:
            try:
                # Save to MongoDB
                document_id = mongo_manager.save_document(doc_data)
                
                logger.log_step("database_save", {
                    "document_id": document_id,
                    "collection": "ocr_agent"
                })
                
            except Exception as e:
                error_msg = f"Error saving OCR document {doc_data.get('filename', 'unknown')}: {str(e)}"
                errors.append(error_msg)
                logger.log_error("database_save_failed", {
                    "filename": doc_data.get("filename"),
                    "document_id": doc_data.get("document_id"),
                    "error": str(e)
                })
        
        # Update state
        state["errors"] = errors
        
        logger.log_step("database_save_completed", {
            "saved_documents": len([d for d in state["processed_documents"] if d.get("document_id")]),
            "errors": len(errors)
        })
        
        return state
    
    async def process_documents(self, input_data: List[Dict[str, Any]], engine_sequence: Optional[List[str]] = None) -> Dict[str, Any]:
        """Process documents through the LangGraph workflow"""
        logger.log_step("starting_ocr_workflow", {
            "document_count": len(input_data)
        })
        
        try:
            # Serialize input data to handle MongoDB ObjectId fields
            serialized_input = serialize_for_json(input_data)
            
            # Initialize state
            initial_state: OCRState = {
                "input_data": serialized_input,
                "processed_documents": [],
                "errors": [],
                "current_document": None,
                "engine_sequence": engine_sequence or self.default_engine_sequence
            }
            
            # Run the LangGraph workflow
            final_state = await self.graph.ainvoke(initial_state)
            
            # Serialize the final state for JSON response
            serialized_processed_documents = serialize_for_json(final_state["processed_documents"])
            
            # Prepare response
            response = {
                "success": len(final_state["errors"]) == 0,
                "message": f"Processed {len(final_state['processed_documents'])} documents with OCR",
                "processed_documents": serialized_processed_documents,
                "total_documents": len(input_data),
                "errors": final_state["errors"]
            }
            
            logger.log_step("ocr_workflow_completed", {
                "success": response["success"],
                "processed_documents": len(final_state["processed_documents"]),
                "errors": len(final_state["errors"])
            })
            
            return response
            
        except Exception as e:
            logger.log_error("workflow_execution_failed", {"error": str(e)})
            # Ensure the error is also serializable
            raise Exception(f"OCR processing failed: {str(e)}")

    async def process_documents_with_engine(self, input_data: List[Dict[str, Any]], engine: str) -> Dict[str, Any]:
        engine_sequence = [engine.lower()]
        return await self.process_documents(input_data, engine_sequence)


# Global OCR service instance
ocr_service = OCRService() 