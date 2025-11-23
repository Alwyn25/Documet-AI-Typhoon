
import grpc
from concurrent import futures
import time
import json

from ...generated import mapper_pb2, mapper_pb2_grpc, common_pb2
from google.protobuf.json_format import MessageToDict

class MapperService(mapper_pb2_grpc.MapperServicer):
    def MapSchema(self, request: common_pb2.ExtractedInvoiceData, context):
        """
        Maps the incoming extracted invoice data to TallyPrime and Zoho Books schemas.
        """
        print("MapperService: Received MapSchema request")

        request_dict = MessageToDict(request, preserving_proto_field_name=True)

        tally_schema = {
            "VOUCHER": {
                "DATE": "2023-10-27",
                "VOUCHERTYPENAME": "Purchase",
                "PARTYLEDGERNAME": f"Vendor GSTIN: {request_dict.get('vendor_gstin', '')}",
                "NARRATION": f"Invoice {request_dict.get('invoice_no', '')}",
                "ALLLEDGERENTRIES.LIST": [
                    {
                        "LEDGERNAME": "Purchase Account",
                        "ISDEEMEDPOSITIVE": "Yes",
                        "AMOUNT": str(request_dict.get('total_amount', 0))
                    }
                ]
            }
        }

        line_items = []
        if 'item_details' in request_dict:
            for item in request_dict['item_details']:
                line_items.append({
                    "item_id": "ITEM_ID_LOOKUP",
                    "name": item.get('item_description', ''),
                    "rate": item.get('unit_price', 0),
                    "quantity": item.get('quantity', 0)
                })

        zoho_schema = {
            "customer_id": "CUSTOMER_ID_LOOKUP",
            "line_items": line_items,
            "invoice_number": request_dict.get('invoice_no', ''),
            "total": request_dict.get('total_amount', 0)
        }

        response = mapper_pb2.MappedSchema(
            tallyprime_schema=json.dumps(tally_schema),
            zoho_books_schema=json.dumps(zoho_schema)
        )

        print("MapperService: Successfully mapped schemas and sending response.")
        return response

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    mapper_pb2_grpc.add_MapperServicer_to_server(MapperService(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    print("Mapper gRPC server started on port 50051")
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == '__main__':
    serve()
