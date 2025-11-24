
import grpc
import os
from dotenv import load_dotenv

from .generated import ingestion_pb2, ingestion_pb2_grpc

# Load environment variables
load_dotenv('InvoiceCoreProcessor/.env')

class MCPClient:
    """A gRPC client for interacting with the backend microservices."""
    def __init__(self):
        self.ingestion_channel = self._create_channel("INGESTION_SERVICE")
        self.ingestion_stub = ingestion_pb2_grpc.IngestionAgentStub(self.ingestion_channel)
        print("MCPClient: gRPC channel for IngestionAgent initialized.")

    def _create_channel(self, service_prefix: str):
        host = os.getenv(f"{service_prefix}_HOST", "localhost")
        port = os.getenv(f"{service_prefix}_PORT")
        address = f"{host}:{port}"
        print(f"  - Initializing channel for {service_prefix} at {address}")
        return grpc.insecure_channel(address)

    def call_ingestion(self, invoice_path: str, user_id: str):
        print(f"MCPClient: Calling Ingestion service for user '{user_id}' and path '{invoice_path}'")
        try:
            request = ingestion_pb2.IngestRequest(invoice_path=invoice_path, user_id=user_id)
            response = self.ingestion_stub.IngestInvoice(request)
            return response
        except grpc.RpcError as e:
            print(f"MCPClient: Error calling Ingestion service: {e.status()}")
            return None

    def close(self):
        self.ingestion_channel.close()
        print("MCPClient: gRPC channel closed.")
