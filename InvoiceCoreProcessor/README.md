# InvoiceCoreProcessor: Distributed Microservice A2A/MCP Module

This project implements an Automated Invoice Entry system using a distributed microservice architecture based on the Model Context Protocol (MCP). The system consists of a central MCP Host/Client (a FastAPI/LangGraph application) that orchestrates a series of network calls to three independent, standalone gRPC microservices that act as the true MCP Servers.

🚀 Architecture Overview

The system is a distributed, multi-process application:

| Component                 | Role                                                                                             | Technology        |
| ------------------------- | ------------------------------------------------------------------------------------------------ | ----------------- |
| **MCP Host (main_processor.py)** | The central orchestrator. It ingests files, runs the LangGraph workflow, and makes gRPC calls to the MCP servers. | FastAPI, LangGraph |
| **SchemaMapperServer**    | A standalone gRPC microservice that exposes the LLM-based schema mapping logic.                  | gRPC, Pydantic    |
| **AnomalyAgentServer**    | A standalone gRPC microservice that performs validation and anomaly detection.                 | gRPC, Pydantic    |
| **DataStoreServer**       | A standalone gRPC microservice that provides a persistence layer for the audit and real-time data. | gRPC              |

✅ Requirements Met

| Requirement               | Implementation Detail                                                                                                                                                               |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Distributed MCP System**  | The core logic is now encapsulated in three true microservices (`microservices/`) communicating over the network via gRPC, representing a robust, enterprise-grade A2A architecture. |
| **gRPC Communication**    | The service contracts are formally defined in `.proto` files (`protos/`), and the `mcp_clients.py` uses gRPC stubs to handle network communication, replacing the previous in-memory calls. |
| **Self-Contained Services** | Each microservice is a standalone, runnable application that encapsulates a specific piece of business logic from the `services/` directory.                                         |
| **Linear Agent Workflow** | The LangGraph workflow in `core/workflow.py` remains the central orchestrator, but now its nodes trigger network calls to the distributed MCP servers.                                 |
| **Complex OCR Agent Logic** | The complex OCR fallback logic remains implemented in `services/ocr_processor.py` and is called directly by the main application before the distributed workflow begins.          |

🛠️ Setup and Run

1.  **Install Dependencies:** `pip install -r requirements.txt`
2.  **Generate gRPC Code:** `python -m grpc_tools.protoc -I./protos --python_out=./generated --grpc_python_out=./generated ./protos/*.proto`
3.  **Configure:** Populate the `.env` file.
4.  **Run the System (requires multiple terminals):**
    *   `python -m InvoiceCoreProcessor.microservices.database_server`
    *   `python -m InvoiceCoreProcessor.microservices.mapper_server`
    *   `python -m InvoiceCoreProcessor.microservices.agent_server`
    *   `uvicorn InvoiceCoreProcessor.main_processor:app --reload`
5.  **Test:** Access the Swagger UI at `http://127.0.0.1:8000/docs` and use the `/upload-invoice` endpoint.
