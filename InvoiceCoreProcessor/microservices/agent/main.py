
import grpc
from concurrent import futures
import time
import os
from dotenv import load_dotenv

from ...generated import agent_pb2, agent_pb2_grpc, common_pb2, datastore_pb2

# Load environment variables
load_dotenv()

class AgentService(agent_pb2_grpc.AgentServicer):
    def FlagAnomalies(self, request: agent_pb2.ValidationRequest, context):
        print("AgentService: Received FlagAnomalies request")

        anomaly_flags = []
        extracted_data = request.extracted_data

        if extracted_data.invoice_no in ["INV-123", "INV-456"]:
            anomaly_flags.append("DUPLICATE_FOUND")

        if extracted_data.total_amount > 10000:
            anomaly_flags.append("HIGH_VALUE_INVOICE")

        status = datastore_pb2.ValidationStatus.ANOMALY if anomaly_flags else datastore_pb2.ValidationStatus.SUCCESS

        response = agent_pb2.ValidationResult(
            validation_status=status,
            anomaly_flags=anomaly_flags
        )
        print(f"AgentService: Sending response with status {datastore_pb2.ValidationStatus.Name(status)} and flags {anomaly_flags}")
        return response

def serve():
    host = os.getenv("AGENT_SERVICE_HOST", "localhost")
    port = os.getenv("AGENT_SERVICE_PORT", "50052")
    bind_address = f"{host}:{port}"

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    agent_pb2_grpc.add_AgentServicer_to_server(AgentService(), server)
    server.add_insecure_port(bind_address)
    server.start()
    print(f"Agent gRPC server started on {bind_address}")
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == '__main__':
    serve()
