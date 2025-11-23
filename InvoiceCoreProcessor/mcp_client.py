
import grpc
import json

from .generated import (
    mapper_pb2, mapper_pb2_grpc,
    agent_pb2, agent_pb2_grpc,
    datastore_pb2, datastore_pb2_grpc,
    common_pb2
)
from .models import (
    ExtractedInvoiceData, MappedSchema, ValidationResult,
    ValidatedInvoiceRecord, StoreRequest, StoreResult
)
from google.protobuf.json_format import ParseDict, MessageToDict

class MCPClient:
    """
    A gRPC client that interacts with the microservices.
    It handles the conversion between internal Pydantic models and external Protobuf messages.
    """
    def __init__(self):
        self.mapper_channel = grpc.insecure_channel('localhost:50051')
        self.agent_channel = grpc.insecure_channel('localhost:50052')
        self.datastore_channel = grpc.insecure_channel('localhost:50053')

        self.mapper_stub = mapper_pb2_grpc.MapperStub(self.mapper_channel)
        self.agent_stub = agent_pb2_grpc.AgentStub(self.agent_channel)
        self.datastore_stub = datastore_pb2_grpc.DataStoreStub(self.datastore_channel)
        print("MCPClient: gRPC channels initialized.")

    def call_mapper(self, extracted_data: ExtractedInvoiceData) -> MappedSchema:
        print("MCPClient: Calling Mapper service...")
        try:
            proto_request = common_pb2.ExtractedInvoiceData()
            # Convert Pydantic model to dict, then to Protobuf
            ParseDict(extracted_data.model_dump(), proto_request)

            proto_response = self.mapper_stub.MapSchema(proto_request)

            # Convert Protobuf response back to Pydantic model
            return MappedSchema(
                tallyprime_schema=json.loads(proto_response.tallyprime_schema),
                zoho_books_schema=json.loads(proto_response.zoho_books_schema)
            )
        except grpc.RpcError as e:
            print(f"MCPClient: Error calling Mapper service: {e.status()}")
            return None

    def call_agent(self, extracted_data: ExtractedInvoiceData) -> ValidationResult:
        print("MCPClient: Calling Agent service...")
        try:
            proto_extracted_data = common_pb2.ExtractedInvoiceData()
            ParseDict(extracted_data.model_dump(), proto_extracted_data)
            proto_request = agent_pb2.ValidationRequest(extracted_data=proto_extracted_data)

            proto_response = self.agent_stub.FlagAnomalies(proto_request)

            response_dict = MessageToDict(proto_response, preserving_proto_field_name=True)
            # The enum value needs to be converted to a string for Pydantic
            response_dict['validation_status'] = datastore_pb2.ValidationStatus.Name(proto_response.validation_status)

            return ValidationResult.model_validate(response_dict)
        except grpc.RpcError as e:
            print(f"MCPClient: Error calling Agent service: {e.status()}")
            return None

    def call_datastore(self, store_request: StoreRequest) -> StoreResult:
        print("MCPClient: Calling DataStore service...")
        try:
            proto_request = datastore_pb2.StoreRequest()
            # Convert the Pydantic model to a dict, carefully handling nested models and enums
            store_dict = store_request.model_dump()
            store_dict['validated_record']['validation_status'] = datastore_pb2.ValidationStatus.Value(store_dict['validated_record']['validation_status'])
            ParseDict(store_dict, proto_request)

            proto_response = self.datastore_stub.StoreValidatedInvoice(proto_request)

            return StoreResult.model_validate(MessageToDict(proto_response, preserving_proto_field_name=True))
        except grpc.RpcError as e:
            print(f"MCPClient: Error calling DataStore service: {e.status()}")
            return None

    def close(self):
        self.mapper_channel.close()
        self.agent_channel.close()
        self.datastore_channel.close()
        print("MCPClient: gRPC channels closed.")
