import json
import tempfile
import os
from typing import Dict, Any, List, Optional

import requests
from fastapi import UploadFile
from fastapi.concurrency import run_in_threadpool
from io import BytesIO

from ..config import settings
from ..prompts import TYPHOON_SYSTEM_PROMPT, TYPHOON_EXTRACTION_PROMPT
from ..utils.logging import logger
from ..utils.token_estimator import check_token_limits, estimate_tokens, detect_language


class TyphoonAPIService:
    """Service to call the external Typhoon OCR API for direct file uploads."""

    def __init__(self) -> None:
        self.base_url = settings.TYPHOON_BASE_URL.rstrip("/")
        self.ocr_endpoint = f"{self.base_url}/ocr"
        self.api_key = settings.TYPHOON_OCR_API_KEY or settings.OPENAI_API_KEY
        self.model = settings.TYPHOON_MODEL
        self.task_type = settings.TYPHOON_TASK_TYPE
        self.max_tokens = settings.TYPHOON_MAX_TOKENS
        self.temperature = settings.TYPHOON_TEMPERATURE
        self.top_p = settings.TYPHOON_TOP_P
        self.repetition_penalty = settings.TYPHOON_REPETITION_PENALTY

    def _ensure_api_key(self):
        if not self.api_key:
            raise ValueError("Typhoon OCR API key is not configured. Set TYPHOON_OCR_API_KEY in the environment.")

    async def extract_text(
        self,
        file: UploadFile,
        pages: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Upload a single PDF/image to the Typhoon OCR API and return the response."""
        self._ensure_api_key()
        file_bytes = await file.read()
        filename = file.filename or "uploaded_document"
        content_type = file.content_type or "application/octet-stream"

        def _call_api():
            # Prepare messages for token estimation
            # Note: We estimate based on prompts since we can't read the image content
            messages = [
                {"role": "system", "content": TYPHOON_SYSTEM_PROMPT},
                {"role": "user", "content": TYPHOON_EXTRACTION_PROMPT},
            ]
            
            # Check token limits before making the API call
            is_valid, token_info = check_token_limits(
                messages=messages,
                model=self.model,
                max_output_tokens=self.max_tokens,
                context_limit=8192  # 8K tokens for Typhoon models
            )
            
            # Log token estimation
            logger.log_step("typhoon_token_estimation", {
                "model": self.model,
                "input_tokens": token_info["input_tokens"],
                "remaining_tokens": token_info["remaining_tokens"],
                "max_output_tokens": self.max_tokens,
                "is_valid": is_valid,
                "warnings": token_info["warnings"]
            })
            
            # Adjust max_tokens to fit within available context
            # Also ensure it doesn't exceed a reasonable limit for the model
            adjusted_max_tokens = self.max_tokens
            max_reasonable_tokens = min(4000, token_info["remaining_tokens"] - 100)  # Conservative limit
            
            if token_info["remaining_tokens"] > 0:
                if self.max_tokens > token_info["remaining_tokens"]:
                    adjusted_max_tokens = max(1, max_reasonable_tokens)
                    logger.log_step("typhoon_max_tokens_adjusted", {
                        "requested_max_tokens": self.max_tokens,
                        "adjusted_max_tokens": adjusted_max_tokens,
                        "remaining_tokens": token_info["remaining_tokens"],
                        "reason": "Requested max_tokens exceeds available context"
                    })
                elif self.max_tokens > max_reasonable_tokens:
                    # Even if within context, cap to reasonable limit
                    adjusted_max_tokens = max_reasonable_tokens
                    logger.log_step("typhoon_max_tokens_capped", {
                        "requested_max_tokens": self.max_tokens,
                        "adjusted_max_tokens": adjusted_max_tokens,
                        "reason": "Capped to reasonable limit for model stability"
                    })
            
            # Warn if token limits are exceeded but don't block the request
            if not is_valid:
                for warning in token_info["warnings"]:
                    logger.log_error("typhoon_token_limit_warning", {
                        "warning": warning,
                        "token_info": token_info,
                        "adjusted_max_tokens": adjusted_max_tokens
                    })
            
            files = {
                "file": (filename, file_bytes, content_type),
            }
            data = {
                "model": self.model,
                "task_type": self.task_type,
                "max_tokens": str(adjusted_max_tokens),  # Use adjusted value
                "temperature": str(self.temperature),
                "top_p": str(self.top_p),
                "repetition_penalty": str(self.repetition_penalty),
                # Note: system_prompt and extraction_prompt may not be supported by the API endpoint
                # The API likely uses its own default prompts
                # "system_prompt": TYPHOON_SYSTEM_PROMPT,
                # "extraction_prompt": TYPHOON_EXTRACTION_PROMPT,
            }

            if pages:
                data["pages"] = json.dumps(pages)

            headers = {
                "Authorization": f"Bearer {self.api_key}",
            }

            # Log request details (without sensitive data)
            logger.log_step("typhoon_api_request_sent", {
                "endpoint": self.ocr_endpoint,
                "model": self.model,
                "task_type": self.task_type,
                "max_tokens": adjusted_max_tokens,
                "file_size_bytes": len(file_bytes),
                "filename": filename,
                "content_type": content_type
            })

            try:
                response = requests.post(self.ocr_endpoint, files=files, data=data, headers=headers, timeout=120)
                
                # Log response details
                logger.log_step("typhoon_api_response_received", {
                    "status_code": response.status_code,
                    "response_size": len(response.text),
                    "content_type": response.headers.get("content-type", "unknown")
                })
                
                if response.status_code != 200:
                    # Try to parse error response for more details
                    error_details = {}
                    try:
                        error_json = response.json()
                        error_details = error_json
                    except:
                        error_details = {"raw_response": response.text[:500]}  # Limit response size
                    
                    logger.log_error("typhoon_api_request_failed", {
                        "status_code": response.status_code,
                        "response": response.text[:1000],  # Limit response size
                        "error_details": error_details,
                        "request_params": {
                            "model": self.model,
                            "max_tokens": adjusted_max_tokens,
                            "task_type": self.task_type,
                            "file_size": len(file_bytes)
                        }
                    })
                    raise ValueError(
                        f"Typhoon OCR API failed with status {response.status_code}: {response.text[:500]}"
                    )
            except requests.exceptions.RequestException as e:
                logger.log_error("typhoon_api_request_exception", {
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "endpoint": self.ocr_endpoint
                })
                raise ValueError(f"Typhoon OCR API request failed: {str(e)}")

            return response.json()

        return await run_in_threadpool(_call_api)
    
    def extract_text_from_bytes(
        self,
        file_bytes: bytes,
        filename: str = "image.png",
        content_type: str = "image/png",
        pages: Optional[List[int]] = None,
    ) -> tuple[str, Optional[Dict[str, Any]]]:
        """
        Extract text from image bytes using Typhoon OCR API.
        Synchronous version for use in OCR service.
        
        Args:
            file_bytes: Image bytes
            filename: Filename for the upload
            content_type: MIME type of the file
            pages: Optional list of page numbers (for PDFs)
        
        Returns:
            Tuple of (extracted_text, token_usage_dict) where token_usage_dict contains:
            - input_tokens: Estimated input tokens
            - output_tokens: Actual output tokens (if available from API)
            - total_tokens: Total tokens used
            - estimated_cost: Estimated cost (if calculable)
        """
        self._ensure_api_key()
        
        # Prepare messages for token estimation
        messages = [
            {"role": "system", "content": TYPHOON_SYSTEM_PROMPT},
            {"role": "user", "content": TYPHOON_EXTRACTION_PROMPT},
        ]
        
        # Check token limits before making the API call
        is_valid, token_info = check_token_limits(
            messages=messages,
            model=self.model,
            max_output_tokens=self.max_tokens,
            context_limit=8192  # 8K tokens for Typhoon models
        )
        
        # Log token estimation
        logger.log_step("typhoon_token_estimation", {
            "model": self.model,
            "input_tokens": token_info["input_tokens"],
            "remaining_tokens": token_info["remaining_tokens"],
            "max_output_tokens": self.max_tokens,
            "is_valid": is_valid,
            "warnings": token_info["warnings"]
        })
        
        # Adjust max_tokens to fit within available context
        # If requested max_tokens exceeds remaining tokens, cap it to available
        # Also ensure it doesn't exceed a reasonable limit for the model
        adjusted_max_tokens = self.max_tokens
        max_reasonable_tokens = min(4000, token_info["remaining_tokens"] - 100)  # Conservative limit
        
        if token_info["remaining_tokens"] > 0:
            if self.max_tokens > token_info["remaining_tokens"]:
                adjusted_max_tokens = max(1, max_reasonable_tokens)
                logger.log_step("typhoon_max_tokens_adjusted", {
                    "requested_max_tokens": self.max_tokens,
                    "adjusted_max_tokens": adjusted_max_tokens,
                    "remaining_tokens": token_info["remaining_tokens"],
                    "reason": "Requested max_tokens exceeds available context"
                })
            elif self.max_tokens > max_reasonable_tokens:
                # Even if within context, cap to reasonable limit
                adjusted_max_tokens = max_reasonable_tokens
                logger.log_step("typhoon_max_tokens_capped", {
                    "requested_max_tokens": self.max_tokens,
                    "adjusted_max_tokens": adjusted_max_tokens,
                    "reason": "Capped to reasonable limit for model stability"
                })
        
        # Warn if token limits are exceeded but don't block the request
        if not is_valid:
            for warning in token_info["warnings"]:
                logger.log_error("typhoon_token_limit_warning", {
                    "warning": warning,
                    "token_info": token_info,
                    "adjusted_max_tokens": adjusted_max_tokens
                })
        
        files = {
            "file": (filename, file_bytes, content_type),
        }
        data = {
            "model": self.model,
            "task_type": self.task_type,
            "max_tokens": str(adjusted_max_tokens),  # Use adjusted value
            "temperature": str(self.temperature),
            "top_p": str(self.top_p),
            "repetition_penalty": str(self.repetition_penalty),
            # Note: system_prompt and extraction_prompt may not be supported by the API endpoint
            # The API likely uses its own default prompts
            # "system_prompt": TYPHOON_SYSTEM_PROMPT,
            # "extraction_prompt": TYPHOON_EXTRACTION_PROMPT,
        }

        if pages:
            data["pages"] = json.dumps(pages)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        # Log request details (without sensitive data)
        logger.log_step("typhoon_api_request_sent", {
            "endpoint": self.ocr_endpoint,
            "model": self.model,
            "task_type": self.task_type,
            "max_tokens": adjusted_max_tokens,
            "file_size_bytes": len(file_bytes),
            "filename": filename,
            "content_type": content_type
        })

        try:
            response = requests.post(self.ocr_endpoint, files=files, data=data, headers=headers, timeout=120)
            
            # Log response details
            logger.log_step("typhoon_api_response_received", {
                "status_code": response.status_code,
                "response_size": len(response.text),
                "content_type": response.headers.get("content-type", "unknown")
            })
            
            if response.status_code != 200:
                # Try to parse error response for more details
                error_details = {}
                try:
                    error_json = response.json()
                    error_details = error_json
                except:
                    error_details = {"raw_response": response.text[:500]}  # Limit response size
                
                logger.log_error("typhoon_api_request_failed", {
                    "status_code": response.status_code,
                    "response": response.text[:1000],  # Limit response size
                    "error_details": error_details,
                    "request_params": {
                        "model": self.model,
                        "max_tokens": adjusted_max_tokens,
                        "task_type": self.task_type,
                        "file_size": len(file_bytes)
                    }
                })
                raise ValueError(
                    f"Typhoon OCR API failed with status {response.status_code}: {response.text[:500]}"
                )
        except requests.exceptions.RequestException as e:
            logger.log_error("typhoon_api_request_exception", {
                "error": str(e),
                "error_type": type(e).__name__,
                "endpoint": self.ocr_endpoint
            })
            raise ValueError(f"Typhoon OCR API request failed: {str(e)}")

        # Extract text from response
        result = response.json()
        extracted_texts = []
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_tokens_used = 0
        
        for page_result in result.get('results', []):
            if page_result.get('success') and page_result.get('message'):
                message_data = page_result.get('message', {})
                
                # Extract content
                if 'choices' in message_data and len(message_data['choices']) > 0:
                    content = message_data['choices'][0].get('message', {}).get('content', '')
                else:
                    content = str(message_data.get('content', ''))
                
                try:
                    # Try to parse as JSON if it's structured output
                    parsed_content = json.loads(content)
                    text = parsed_content.get('natural_text', content)
                except json.JSONDecodeError:
                    text = content
                extracted_texts.append(text)
                
                # Extract token usage from response if available
                # Usage can be at message level or page_result level
                usage_data = message_data.get('usage') or page_result.get('usage')
                if usage_data:
                    total_prompt_tokens += usage_data.get('prompt_tokens', 0)
                    total_completion_tokens += usage_data.get('completion_tokens', 0)
                    total_tokens_used += usage_data.get('total_tokens', 0)
            elif not page_result.get('success'):
                error_msg = page_result.get('error', 'Unknown error')
                logger.log_error("typhoon_api_page_failed", {
                    "filename": page_result.get('filename', 'unknown'),
                    "error": error_msg
                })
        
        extracted_text = '\n'.join(extracted_texts) if extracted_texts else ""
        
        # Use actual token usage from API if available, otherwise use estimates
        actual_input_tokens = total_prompt_tokens if total_prompt_tokens > 0 else token_info["input_tokens"]
        actual_output_tokens = total_completion_tokens if total_completion_tokens > 0 else None
        actual_total_tokens = total_tokens_used if total_tokens_used > 0 else (actual_input_tokens + (actual_output_tokens or 0))
        
        # Build token usage info
        token_usage = {
            "input_tokens": actual_input_tokens,
            "output_tokens": actual_output_tokens,
            "total_tokens": actual_total_tokens,
            "estimated_cost": None,  # Can be calculated if pricing is known
            "context_limit": token_info["context_limit"],
            "remaining_tokens": token_info["context_limit"] - actual_total_tokens if actual_total_tokens > 0 else token_info["remaining_tokens"],
            "is_estimated": total_prompt_tokens == 0,  # Flag to indicate if using estimates
        }
        
        # Log actual vs estimated tokens
        if total_prompt_tokens > 0:
            logger.log_step("typhoon_actual_token_usage", {
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": total_completion_tokens,
                "total_tokens": total_tokens_used,
                "estimated_input_tokens": token_info["input_tokens"]
            })
        
        return extracted_text, token_usage


typhoon_api_service = TyphoonAPIService()

