# InvoiceCoreProcessor Module

This repository contains the `InvoiceCoreProcessor`, a self-contained, high-performance module for automated invoice processing, built on an **MCP-Agentic Architecture** orchestrated by LangGraph.

## 1. Architecture
The system is a self-contained Python package that simulates a microservice architecture locally. A **FastAPI Gateway** serves as the entry point, and a **LangGraph Orchestrator** manages a strictly sequential workflow. The orchestrator calls a series of local "MCP Server" agents to perform specific tasks:
-   **DataStoreAgent**: Manages all database operations (MongoDB/PostgreSQL).
-   **OCRAgent**: Performs mock data extraction.
-   **SchemaMapperAgent**: Maps extracted data to a canonical schema.
-   **ValidationAgent**: Runs a detailed, rule-based validation checklist against the data and calculates a reliability score.
-   **DataIntegrationAgent**: Transforms the validated data into an ERP-ready format.

## 2. Getting Started

### Prerequisites
-   Python 3.12+
-   `pip` for package management
-   **PostgreSQL and MongoDB**: The `DataStoreAgent` requires connections to these databases. Ensure they are running locally or accessible.

### Quick Start
1.  **Install dependencies**: `pip install -r requirements.txt`
2.  **Configure the environment**:
    -   Copy `.env.example` to `.env`.
    -   Update the `MONGODB_URI` and `POSTGRES_URI` with your database connection strings.
    -   (Optional) Add an `OPENAI_API_KEY` if you plan to replace the mock logic.
3.  **Set up the database schema**:
    -   Execute the SQL commands in `InvoiceCoreProcessor/database/schema.sql` against your PostgreSQL database to create the necessary tables and rules.
4.  **Run the application**:
    ```bash
    python main_processor.py
    ```
    The FastAPI gateway will be available at `http://localhost:8080`.

## 3. Configuration
All configuration is managed via the `.env` file and loaded by `InvoiceCoreProcessor/config/settings.py`.

## 4. Key Components
-   **`main_processor.py`**: The FastAPI entry point.
-   **`core/workflow.py`**: The LangGraph state machine definition.
-   **`servers/*.py`**: The implementations of the MCP Agent Servers.
-   **`services/*.py`**: The core, stateless business logic for each function.
-   **`database/schema.sql`**: The PostgreSQL schema for the validation engine.
-   **`core/rule_engine.py`**: The engine that runs the validation checklist and scoring.

## 5. Workflow Sequence
The system follows a strict, gated sequence:
`Ingestion` -> `OCR` -> `Mapping` -> `Validation` -> `Data Integration`
Each step must return a successful `status` for the workflow to proceed. Failures are routed to an error or manual review state.
