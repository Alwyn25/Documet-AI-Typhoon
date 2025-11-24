from pymongo import MongoClient
import psycopg2
from typing import Dict, Any

from ..config.settings import settings
from ..services import ingestion

class DataStoreAgent:
    """
    MCP Server for all database operations.
    Connects to MongoDB and PostgreSQL.
    """
    def __init__(self):
        # In a real app, these would be managed connection pools.
        self.mongo_client = MongoClient(settings.MONGODB_URI)
        self.postgres_conn = psycopg2.connect(settings.POSTGRES_URI)
        print("DataStoreAgent: Initialized DB connections.")

    def save_metadata(self, file_content: bytes, original_filename: str, user_id: str) -> Dict[str, Any]:
        """
        Tool: Saves initial file metadata to MongoDB.
        Calls the ingestion service logic.
        """
        print("DataStoreAgent Tool: mongo/save_metadata called.")
        try:
            document_id, file_path = ingestion.save_file_and_metadata(
                file_content, original_filename, user_id, self.mongo_client
            )
            return {
                "status": "UPLOADED_METADATA_SAVED",
                "mongo_document_id": document_id,
                "file_path": file_path
            }
        except Exception as e:
            print(f"  - Error in save_metadata: {e}")
            return {"status": "FAILED_INGESTION", "error": str(e)}

    def check_duplicate(self, invoice_no: str) -> Dict[str, Any]:
        """
        Tool: Checks for a duplicate invoice number in PostgreSQL.
        """
        print("DataStoreAgent Tool: postgres/check_duplicate called.")
        # Mock implementation
        if invoice_no == "INV-DUPLICATE-123":
            print("  - Duplicate found.")
            return {"status": "DUPLICATE_FOUND"}

        print("  - No duplicate found.")
        return {"status": "UNIQUE_RECORD"}

    def save_validated_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tool: Saves the final, validated record to PostgreSQL.
        """
        print("DataStoreAgent Tool: postgres/save_validated_record called.")
        # Mock implementation
        try:
            # with self.postgres_conn.cursor() as cur:
            #     cur.execute("INSERT INTO invoices (...) VALUES (...);", record)
            # self.postgres_conn.commit()
            print("  - Mock save to PostgreSQL successful.")
            return {"status": "DB_RECORD_SAVED"}
        except Exception as e:
            print(f"  - Error in save_validated_record: {e}")
            return {"status": "FAILED_DB_SAVE", "error": str(e)}

    def __del__(self):
        # Clean up connections
        if self.mongo_client:
            self.mongo_client.close()
        if self.postgres_conn:
            self.postgres_conn.close()
        print("DataStoreAgent: DB connections closed.")
