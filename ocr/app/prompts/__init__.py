"""Prompt package for OCR service."""

from .typhoon import (
    TYPHOON_SYSTEM_PROMPT,
    TYPHOON_EXTRACTION_PROMPT,
)
from .gpt4_vision import (
    GPT4_VISION_EXTRACTION_PROMPT,
)

__all__ = [
    "TYPHOON_SYSTEM_PROMPT",
    "TYPHOON_EXTRACTION_PROMPT",
    "GPT4_VISION_EXTRACTION_PROMPT",
]

