"""Token estimation utilities for Typhoon models."""

from typing import List, Dict, Any


def estimate_tokens(text: str, lang: str = "english") -> int:
    """
    Estimate token count for text based on language.
    
    Args:
        text: Input text to estimate tokens for
        lang: Language code ("thai" or "english")
    
    Returns:
        Estimated token count
    """
    if not text:
        return 0
    
    # Very rough estimation - use a proper tokenizer for production
    if lang.lower() == "thai":
        # Thai text: estimate 2.5 tokens per word (rough average)
        # Count Thai characters and spaces
        words = len(text.split())
        return int(words * 2.5)
    else:
        # English text: estimate 1.3 tokens per word
        words = len(text.split())
        return int(words * 1.3)


def detect_language(text: str) -> str:
    """
    Detect if text is primarily Thai or English.
    
    Args:
        text: Text to analyze
    
    Returns:
        "thai" or "english"
    """
    if not text:
        return "english"
    
    # Simple heuristic: check if most characters are ASCII
    # Thai characters are typically in Unicode ranges 0x0E00-0x0E7F
    ascii_count = sum(1 for c in text if ord(c) < 128)
    total_chars = len([c for c in text if c.isalnum() or c.isspace()])
    
    if total_chars == 0:
        return "english"
    
    ascii_ratio = ascii_count / total_chars if total_chars > 0 else 1.0
    return "english" if ascii_ratio > 0.7 else "thai"


def check_token_limits(
    messages: List[Dict[str, Any]],
    model: str = "typhoon-v2.1-12b-instruct",
    max_output_tokens: int = 500,
    context_limit: int = 8192
) -> tuple[bool, Dict[str, Any]]:
    """
    Check if messages fit within the model's context window.
    
    Args:
        messages: List of message dictionaries with "content" field
        model: Model name (for logging)
        max_output_tokens: Maximum tokens requested for output
        context_limit: Model's context window size (default 8K for Typhoon models)
    
    Returns:
        Tuple of (is_valid, info_dict) where info_dict contains:
        - input_tokens: Estimated input tokens
        - remaining_tokens: Tokens remaining for output
        - is_valid: Whether the request fits
        - warnings: List of warning messages
    """
    # Estimate total input tokens
    input_tokens = 0
    warnings = []
    
    for message in messages:
        # Add 4 tokens for message formatting
        content = message.get("content", "")
        if isinstance(content, list):
            # Handle multimodal content (text + images)
            text_content = ""
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_content += item.get("text", "")
        else:
            text_content = str(content)
        
        lang = detect_language(text_content)
        content_tokens = estimate_tokens(text_content, lang)
        input_tokens += content_tokens + 4  # +4 for message formatting
    
    # Check against model's context limit
    remaining_tokens = context_limit - input_tokens
    
    is_valid = True
    if remaining_tokens <= 0:
        warnings.append(f"Input exceeds context window of {context_limit} tokens.")
        is_valid = False
    elif remaining_tokens < max_output_tokens:
        warnings.append(
            f"Only {remaining_tokens} tokens remaining for output "
            f"(requested {max_output_tokens}). Consider reducing input length or requested output tokens."
        )
        is_valid = False
    
    info = {
        "input_tokens": input_tokens,
        "remaining_tokens": remaining_tokens,
        "is_valid": is_valid,
        "warnings": warnings,
        "context_limit": context_limit,
        "max_output_tokens": max_output_tokens,
    }
    
    return is_valid, info

