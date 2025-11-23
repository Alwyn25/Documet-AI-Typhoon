from typing import Dict, Any, Optional
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection

from .logging import logger
from ..config import settings

class MongoDBManager:
    """MongoDB manager for OCR agent"""
    
    def __init__(self):
        self.client: Optional[MongoClient] = None
        self.db: Optional[Database] = None
        self.collection: Optional[Collection] = None
        self._connect()
    
    def _connect(self):
        """Connect to MongoDB"""
        try:
            uri = settings.MONGODB_URI
            database_name = settings.DATABASE_NAME
            collection_name = settings.COLLECTION_NAME
            
            logger.log_step("mongodb_connection", {
                "uri": uri,
                "database": database_name,
                "collection": collection_name
            })
            
            self.client = MongoClient(uri)
            self.db = self.client[database_name]
            self.collection = self.db[collection_name]
            
            # Test connection
            self.client.admin.command('ping')
            
            logger.log_step("mongodb_connected", {"status": "success"})
            
        except Exception as e:
            logger.log_error("mongodb_connection_failed", {"error": str(e)})
            raise
    
    def save_document(self, document_data: Dict[str, Any]) -> str:
        """Save document to MongoDB"""
        try:
            result = self.collection.insert_one(document_data)
            return str(result.inserted_id)
        except Exception as e:
            logger.log_error("mongodb_save_failed", {"error": str(e)})
            raise
    
    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get document from MongoDB by _id"""
        try:
            from bson import ObjectId
            return self.collection.find_one({"_id": ObjectId(document_id)})
        except Exception as e:
            logger.log_error("mongodb_get_failed", {"error": str(e)})
            raise
    
    def get_document_by_field(self, field_name: str, field_value: str) -> Optional[Dict[str, Any]]:
        """Get document from MongoDB by any field"""
        try:
            return self.collection.find_one({field_name: field_value})
        except Exception as e:
            logger.log_error("mongodb_get_by_field_failed", {"error": str(e), "field": field_name, "value": field_value})
            raise
    
    def update_document(self, document_id: str, update_data: Dict[str, Any]) -> bool:
        """Update document in MongoDB"""
        try:
            from bson import ObjectId
            result = self.collection.update_one(
                {"_id": ObjectId(document_id)},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.log_error("mongodb_update_failed", {"error": str(e)})
            raise
    
    def list_documents(self, filter_criteria: Dict[str, Any] = None) -> list:
        """List documents from MongoDB"""
        try:
            if filter_criteria is None:
                filter_criteria = {}
            return list(self.collection.find(filter_criteria))
        except Exception as e:
            logger.log_error("mongodb_list_failed", {"error": str(e)})
            raise
    
    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            logger.log_step("mongodb_connection_closed")


# Global MongoDB manager instance
mongo_manager = MongoDBManager() 