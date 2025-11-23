
import grpc
from concurrent import futures
import time
import json
import os
from dotenv import load_dotenv

from ...generated import datastore_pb2, datastore_pb2_grpc, common_pb2
from google.protobuf.json_format import MessageToJson

# Load environment variables
load_dotenv()

# Mock database connections
IN_MEMORY_POSTGRES = {}
IN_MEMORY_MONGO = {}

class DataStoreService(datastore_pb2_grpc.DataStoreServicer):
    def StoreValidatedInvoice(self, request: datastore_pb2.StoreRequest, context):
        print("DataStoreService: Received StoreValidatedInvoice request")

        invoice_id = request.validated_record.extracted_data.invoice_no

        postgres_record = MessageToJson(request.validated_record, preserving_proto_field_name=True)
        IN_MEMORY_POSTGRES[invoice_id] = postgres_record
        print(f"DataStoreService: Stored record {invoice_id} in PostgreSQL.")

        mongo_record = {
            "invoice_id": invoice_id,
            "raw_file_ref": request.raw_file_ref,
            "document_ai_output": MessageToJson(request.validated_record.extracted_data, preserving_proto_field_name=True)
        }
        IN_MEMORY_MONGO[invoice_id] = json.dumps(mongo_record)
        print(f"DataStoreService: Stored document {invoice_id} in MongoDB.")

        return datastore_pb2.StoreResult(
            success=True,
            message=f"Successfully stored invoice {invoice_id}"
        )

def serve():
    host = os.getenv("DATASTORE_SERVICE_HOST", "localhost")
    port = os.getenv("DATASTORE_SERVICE_PORT", "50053")
    bind_address = f"{host}:{port}"

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    datastore_pb2_grpc.add_DataStoreServicer_to_server(DataStoreService(), server)
    server.add_insecure_port(bind_address)
    server.start()
    print(f"DataStore gRPC server started on {bind_address}")
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == '__main__':
    serve()
