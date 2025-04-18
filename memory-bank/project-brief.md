# Project Brief: AI Agent Framework (NEO) - Optimized

## Core Goal
Extensible AI Agent framework (NEO) for automating coding/testing via modular MCPs.

## Key Components & Requirements
*   **Core Agent:** Task planning, code generation, MCP interaction.
*   **MCP Code Server (Port 8081):**
    *   Analyze/format/fix code (Ruff).
    *   Store/retrieve snippets (SQLite via `DatabaseManager`).
*   **MCP Test Server (Port 8082):**
    *   Execute tests (`pytest`, `unittest`, `nose2`).
    *   Local & Docker execution.
    *   Stream output.
    *   Store results (SQLite via `DatabaseManager`).
*   **Authentication:** API Key (`X-API-Key` header) for MCPs.
*   **Testing:** Unit & Integration tests required.
*   **CI/CD (GitHub Actions):**
    *   CI: Lint & Test.
    *   CD: Docker build/push (GHCR).
*   **UI:** Basic Streamlit UI for core operations.
*   **Dependencies:** Managed via UV (`requirements.txt`).

## Key Success Metrics
*   **Stability:** Passing test suite.
*   **Functionality:** Agent uses MCPs; UI controls basic tasks.
*   **Modularity:** Independent MCPs via defined APIs.

## Key Non-Functional Requirements
*   Extensibility (new tools/MCPs).
*   Security (API key).
