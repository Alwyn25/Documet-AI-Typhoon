import base64
import io
import os
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

import pdfplumber
from fastapi import UploadFile
from fastapi.concurrency import run_in_threadpool
from openai import OpenAI
from pdf2image import convert_from_path
from PIL import Image

from ..config import settings
from ..prompts import GPT4_VISION_EXTRACTION_PROMPT
from ..utils.logging import logger


class GPT4VisionService:
    """Service to extract OCR text using GPT-4 Vision (page-by-page)."""

    def __init__(self) -> None:
        self.model = settings.GPT4_VISION_MODEL
        self.max_tokens = settings.GPT4_VISION_MAX_TOKENS
        self._api_key = None
        self._client: Optional[OpenAI] = None

    def _ensure_client(self) -> None:
        api_key = settings.GPT4_VISION_API_KEY or settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("GPT-4 Vision API key not configured. Set GPT4_VISION_API_KEY or OPENAI_API_KEY.")

        if self._client is None or self._api_key != api_key:
            self._client = OpenAI(api_key=api_key)
            self._api_key = api_key
            logger.log_step("gpt4_vision_client_initialized", {"model": self.model})

    async def process_upload(self, upload: UploadFile, pages: Optional[List[int]] = None) -> Dict[str, List[Dict]]:
        self._ensure_client()

        filename = upload.filename or f"upload_{uuid4().hex}.pdf"
        suffix = Path(filename).suffix or ".pdf"

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            file_bytes = await upload.read()
            tmp.write(file_bytes)
            temp_path = tmp.name

        try:
            pages_data = await run_in_threadpool(self._process_file, temp_path, filename, pages)
            return pages_data
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def _process_file(self, file_path: str, filename: str, pages: Optional[List[int]]) -> Dict[str, List[Dict]]:
        start_time = time.time()
        extension = Path(filename).suffix.lower()
        is_pdf = extension == ".pdf"

        if is_pdf:
            with pdfplumber.open(file_path) as pdf:
                total_pages = len(pdf.pages)
            page_list = sorted(pages) if pages else list(range(1, total_pages + 1))
        else:
            page_list = [1]

        logger.log_step("gpt4_vision_start", {
            "filename": filename,
            "total_pages": len(page_list),
            "engine": "gpt-4-vision"
        })

        processed_pages: List[Dict] = []
        total_prompt_tokens = 0
        total_completion_tokens = 0

        for page_num in page_list:
            text, usage = self._process_page(file_path, page_num, is_pdf)
            if text is None:
                continue

            word_count = len(text.split())
            char_count = len(text)
            
            # Build token usage info for this page
            page_token_usage = None
            if usage:
                total_prompt_tokens += usage.get("prompt_tokens", 0)
                total_completion_tokens += usage.get("completion_tokens", 0)
                page_token_usage = {
                    "input_tokens": usage.get("prompt_tokens", 0),
                    "output_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                    "engine": "gpt4vision"
                }
            
            processed_pages.append({
                "page_number": page_num,
                "text_content": text,
                "ocr_texts": [text],
                "ocr_used": ["GPT-4 Vision"],
                "word_count": word_count,
                "character_count": char_count,
                "token_usage": page_token_usage
            })

        logger.log_step("gpt4_vision_completed", {
            "filename": filename,
            "pages_extracted": len(processed_pages),
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "processing_time": time.time() - start_time
        })

        return processed_pages

    def _process_page(self, file_path: str, page_num: int, is_pdf: bool):
        try:
            if is_pdf:
                images = convert_from_path(
                    file_path,
                    dpi=200,
                    fmt="JPEG",
                    first_page=page_num,
                    last_page=page_num
                )
                if not images:
                    logger.log_step("gpt4_vision_page_convert_failed", {"page": page_num})
                    return None, None
                image = images[0]
            else:
                image = Image.open(file_path)

            # Convert to RGB if necessary (JPEG doesn't support palette mode or transparency)
            original_mode = image.mode
            if original_mode in ("RGBA", "LA"):
                # Create white background for transparent images
                rgb_image = Image.new("RGB", image.size, (255, 255, 255))
                rgb_image.paste(image, mask=image.split()[-1])
                image = rgb_image
            elif original_mode == "P":
                # Convert palette mode to RGB
                image = image.convert("RGB")
            elif original_mode != "RGB":
                # Convert any other mode to RGB
                image = image.convert("RGB")
            
            image.thumbnail((1536, 1536), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=90)
            img_base64 = base64.b64encode(buffer.getvalue()).decode()

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": GPT4_VISION_EXTRACTION_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_base64}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ]

            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=0
            )

            usage = response.usage.model_dump() if response.usage else None
            text = response.choices[0].message.content or ""
            return text.strip(), usage

        except Exception as e:
            logger.log_error("gpt4_vision_page_failed", {
                "page": page_num,
                "error": str(e)
            })
            return None, None


gpt4_vision_service = GPT4VisionService()

