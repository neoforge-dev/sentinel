# System Patterns - Optimized

## Core Architecture
- **Agent:** Orchestrates tasks, interacts with MCPs.
- **MCPs (Modular Context Providers):** Independent FastAPI services.
    - **Code MCP (Port 8081):** Code analysis/format/fix (Ruff), Snippet DB (SQLite).
    - **Test MCP (Port 8082):** Test execution (local/Docker), Result DB (SQLite).
- **Communication:** REST/JSON APIs between Agent & MCPs.
- **Persistence:** SQLite (`DatabaseManager`).
- **Docker:** Used by Test MCP for isolated testing.

## Key Technical Decisions & Patterns
- **Modularity:** Decoupled Agent/MCPs via standard APIs.
- **Docker for Testing:** Consistent environments.
- **SQLite:** Simple persistence.
- **Async:** FastAPI & `asyncio` for IO-bound tasks.
- **Centralized DB Management:** `DatabaseManager` class.
- **API Key Auth:** Simple header-based security.

## Important Behaviors & Constraints
- **Python Path:** Requires `-m` or `pip install -e .` for imports.
- **Test Status Logic:** Based on output parsing & exit codes.
- **Docker Execution:** Isolated runs, log capture, cleanup.
- **Error Handling:** Contextual errors, standard HTTP codes.
- **Resource Management:** Process/container termination, async cleanup.
- **Environment:** Python 3.10+, Docker (for Docker tests).
- **Security:** API Key, Docker isolation, Input validation.
