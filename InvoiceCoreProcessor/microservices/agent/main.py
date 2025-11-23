
import grpc
from concurrent import futures
import time

from ...generated import agent_pb2, agent_pb2_grpc, common_pb2, datastore_pb2

class AgentService(agent_pb2_grpc.AgentServicer):
    def FlagAnomalies(self, request: agent_pb2.ValidationRequest, context):
        print("AgentService: Received FlagAnomalies request")

        anomaly_flags = []
        extracted_data = request.extracted_data

        if extracted_data.invoice_no in ["INV-123", "INV-456"]:
            anomaly_flags.append("DUPLICATE_FOUND")

        if extracted_data.total_amount > 10000:
            anomaly_flags.append("HIGH_VALUE_INVOICE")

        if not anomaly_flags:
            status = datastore_pb2.ValidationStatus.SUCCESS
        else:
            status = datastore_pb2.ValidationStatus.ANOMALY

        response = agent_pb2.ValidationResult(
            validation_status=status,
            anomaly_flags=anomaly_flags
        )
        print(f"AgentService: Sending response with status {datastore_pb2.ValidationStatus.Name(status)} and flags {anomaly_flags}")
        return response

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    agent_pb2_grpc.add_AgentServicer_to_server(AgentService(), server)
    server.add_insecure_port('[::]:50052')
    server.start()
    print("Agent gRPC server started on port 50052")
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == '__main__':
    serve()
