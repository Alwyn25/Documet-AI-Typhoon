# Mapper Service

## Purpose

This gRPC microservice is responsible for mapping the structured data extracted from an invoice to one or more target accounting schemas, such as TallyPrime or Zoho Books.

It receives an `ExtractedInvoiceData` object and returns a `MappedSchema` object containing the transformed data as JSON strings.

## Configuration

This service is configured via environment variables.

| Variable              | Description                       | Default     |
| --------------------- | --------------------------------- | ----------- |
| `MAPPER_SERVICE_HOST` | The hostname to bind the server to. | `localhost` |
| `MAPPER_SERVICE_PORT` | The port to bind the server to.     | `50051`     |

## More Information

For details on the overall system architecture, local development, and API contracts, please see the [**main project README.md**](../../../README.md).
