# Agent Service

## Purpose

This gRPC microservice is the validation and anomaly detection engine for the invoice processing workflow. It is responsible for performing business logic checks on the extracted invoice data.

It receives a `ValidationRequest` and returns a `ValidationResult` containing a status (`SUCCESS` or `ANOMALY`) and a list of any detected anomaly flags (e.g., `DUPLICATE_FOUND`, `HIGH_VALUE_INVOICE`).

## Configuration

This service is configured via environment variables.

| Variable             | Description                       | Default     |
| -------------------- | --------------------------------- | ----------- |
| `AGENT_SERVICE_HOST` | The hostname to bind the server to. | `localhost` |
| `AGENT_SERVICE_PORT` | The port to bind the server to.     | `50052`     |

## More Information

For details on the overall system architecture, local development, and API contracts, please see the [**main project README.md**](../../../README.md).
