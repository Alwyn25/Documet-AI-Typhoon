# DataStore Service

## Purpose

This gRPC microservice is the persistence layer for the invoice processing system. It is responsible for storing the final, validated invoice records.

It receives a `StoreRequest` containing the full `ValidatedInvoiceRecord` and stores it in the appropriate databases. While the current implementation uses in-memory mocks, it is designed to persist data to PostgreSQL (for structured records) and MongoDB (for raw document references).

## Configuration

This service is configured via environment variables.

| Variable                 | Description                                    | Default     |
| ------------------------ | ---------------------------------------------- | ----------- |
| `DATASTORE_SERVICE_HOST` | The hostname to bind the server to.            | `localhost` |
| `DATASTORE_SERVICE_PORT` | The port to bind the server to.                | `50053`     |
| `POSTGRES_DB_URL`        | The connection string for the PostgreSQL DB.   | (none)      |
| `MONGO_DB_URL`           | The connection string for the MongoDB instance.| (none)      |

## More Information

For details on the overall system architecture, local development, and API contracts, please see the [**main project README.md**](../../../README.md).
