"""GPT-4 Vision OCR prompt definitions."""

GPT4_VISION_EXTRACTION_PROMPT = """Extract ALL text content from this document page with maximum accuracy. This may be a financial or legal document, so be extremely careful with:

*Critical Requirements:*

1. *ALL readable text* in proper reading order (left-to-right, top-to-bottom)
2. *Exact numbers, percentages, and financial figures* (preserve formatting)
3. *Complete headers, titles, and section names*
4. *Full paragraphs and sentences* (don't truncate)
5. *Legal terms, names, and proper nouns* (exact spelling)
6. *Dates and addresses* (complete and accurate)

*For tables/structured data:*
- Use clear separators like | or consistent spacing
- Maintain column alignment
- Include all rows and columns

*Text quality:*
- Include ALL text, even if small or faint
- If text is unclear, make your best attempt
- Preserve paragraph breaks and document structure
- Don't add explanations or comments

Return ONLY the extracted text content."""

