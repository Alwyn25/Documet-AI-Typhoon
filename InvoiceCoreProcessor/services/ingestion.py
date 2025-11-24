import os
import uuid
from datetime import datetime
from pymongo import MongoClient

def save_file_and_metadata(
    file_content: bytes,
    original_filename: str,
    user_id: str,
    mongo_client: MongoClient
) -> tuple[str, str]:
    """
    Saves a file to the 'uploads' directory and its metadata to MongoDB.
    Returns the generated document ID and the path to the saved file.
    """
    db = mongo_client.get_database() # Assumes the DB name is in the connection string
    collection = db.get_collection("invoices") # Use a hardcoded collection for now

    # 1. Save file to 'uploads' directory
    file_extension = os.path.splitext(original_filename)[1]
    storage_filename = f"{uuid.uuid4()}{file_extension}"
    storage_path = os.path.join("uploads", storage_filename)

    with open(storage_path, 'wb') as f:
        f.write(file_content)

    # 2. Save metadata to MongoDB
    document_id = str(uuid.uuid4())
    metadata = {
        "document_id": document_id,
        "user_id": user_id,
        "original_filename": original_filename,
        "storage_path": storage_path,
        "upload_timestamp": datetime.utcnow(),
        "status_history": ["UPLOADED"],
    }

    collection.insert_one(metadata)

    return document_id, storage_path
