from pydantic import BaseModel


class DocumentMetadata(BaseModel):
    document_id: str
    original_filename: str
    stored_filename: str
    content_type: str | None
    extension: str
    size_bytes: int
    size_mb: float
    storage_path: str
    uploaded_at: str


