
import grpc
from concurrent import futures
import time
import os
import uuid
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient

# Navigate up to the project root to ensure correct module resolution
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from InvoiceCoreProcessor.generated import ingestion_pb2, ingestion_pb2_grpc

# Load environment variables
load_dotenv('InvoiceCoreProcessor/.env')

class IngestionService(ingestion_pb2_grpc.IngestionAgentServicer):
    def __init__(self):
        # Set up MongoDB connection
        mongo_uri = os.getenv("MONGODB_URI")
        db_name = os.getenv("MONGODB_DATABASE")
        collection_name = os.getenv("MONGODB_COLLECTION")

        if not all([mongo_uri, db_name, collection_name]):
            raise ValueError("MongoDB configuration is missing in the .env file.")

        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]
        print("MongoDB connection established.")

    def IngestInvoice(self, request: ingestion_pb2.IngestRequest, context):
        print(f"IngestionAgent: Received IngestInvoice request for user '{request.user_id}' and path '{request.invoice_path}'")

        try:
            # 1. Simulate file upload by creating a dummy file
            original_filename = os.path.basename(request.invoice_path)
            file_extension = os.path.splitext(original_filename)[1]
            storage_filename = f"{uuid.uuid4()}{file_extension}"
            storage_path = os.path.join("uploads", storage_filename)

            # Create a dummy file
            with open(storage_path, 'w') as f:
                f.write(f"This is a dummy file for invoice: {original_filename}")

            print(f"  - File '{original_filename}' stored at '{storage_path}'")

            # 2. Save metadata to MongoDB
            document_id = str(uuid.uuid4())
            metadata = {
                "document_id": document_id,
                "user_id": request.user_id,
                "original_filename": original_filename,
                "storage_path": storage_path,
                "upload_timestamp": datetime.utcnow(),
                "status": "INGESTED"
            }

            self.collection.insert_one(metadata)
            print(f"  - Metadata saved to MongoDB with document_id: {document_id}")

            return ingestion_pb2.IngestResponse(
                success=True,
                message="Invoice ingested successfully.",
                document_id=document_id
            )
        except Exception as e:
            print(f"  - Error during ingestion: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"An internal error occurred: {e}")
            return ingestion_pb2.IngestResponse(success=False, message=str(e))

def serve():
    host = os.getenv("INGESTION_SERVICE_HOST", "localhost")
    port = os.getenv("INGESTION_SERVICE_PORT", "50051")
    bind_address = f"{host}:{port}"

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    ingestion_pb2_grpc.add_IngestionAgentServicer_to_server(IngestionService(), server)
    server.add_insecure_port(bind_address)
    server.start()
    print(f"IngestionAgent gRPC server started on {bind_address}")
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == '__main__':
    serve()
