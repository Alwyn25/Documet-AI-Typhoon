"""MongoDB utility for schema mapping service"""

from typing import Dict, Any, Optional
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection
from bson import ObjectId

from .logging import logger
from ..config import settings


class MongoDBManager:
    """MongoDB manager for schema mapping service"""
    
    def __init__(self):
        self.client: Optional[MongoClient] = None
        self.db: Optional[Database] = None
        self.collection: Optional[Collection] = None
        self._connected = False
        self._connect()
    
    def _connect(self):
        """Connect to MongoDB"""
        try:
            uri = settings.MONGODB_URI
            database_name = settings.DATABASE_NAME
            collection_name = settings.COLLECTION_NAME
            
            logger.log_step("mongodb_connection_attempt", {
                "uri": uri,
                "database": database_name,
                "collection": collection_name
            })
            
            self.client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            self.db = self.client[database_name]
            self.collection = self.db[collection_name]
            
            # Test connection
            self.client.admin.command('ping')
            self._connected = True
            
            logger.log_step("mongodb_connected", {"status": "success"})
            
        except Exception as e:
            self._connected = False
            logger.log_error("mongodb_connection_failed", {
                "error": str(e),
                "note": "MongoDB operations will be skipped"
            })
            # Don't raise - allow service to start without MongoDB
    
    def save_document(self, document_data: Dict[str, Any]) -> str:
        """Save document to MongoDB"""
        if not self._connected or not self.client or not self.collection:
            # Try to reconnect
            try:
                self._connect()
            except Exception:
                pass
            
            if not self._connected:
                raise Exception("MongoDB not connected. Cannot save document.")
        
        try:
            result = self.collection.insert_one(document_data)
            logger.log_step("mongodb_document_saved", {
                "document_id": str(result.inserted_id),
                "collection": self.collection.name
            })
            return str(result.inserted_id)
        except Exception as e:
            logger.log_error("mongodb_save_failed", {"error": str(e)})
            raise
    
    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get document from MongoDB by _id"""
        try:
            return self.collection.find_one({"_id": ObjectId(document_id)})
        except Exception as e:
            logger.log_error("mongodb_get_failed", {"error": str(e)})
            raise
    
    def get_document_by_field(self, field_name: str, field_value: str) -> Optional[Dict[str, Any]]:
        """Get document from MongoDB by any field"""
        try:
            return self.collection.find_one({field_name: field_value})
        except Exception as e:
            logger.log_error("mongodb_get_by_field_failed", {
                "error": str(e),
                "field": field_name,
                "value": field_value
            })
            raise
    
    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            logger.log_step("mongodb_connection_closed")


# Global MongoDB manager instance
mongo_manager = MongoDBManager()

