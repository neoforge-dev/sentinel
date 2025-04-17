# BaseAgent: Ollama + UV + MCP Integration

[![Python CI](https://github.com/USER/REPO/actions/workflows/ci.yml/badge.svg)](https://github.com/USER/REPO/actions/workflows/ci.yml)

A powerful AI project that combines:
- [Ollama](https://github.com/ollama/ollama) for running local LLMs
- [UV](https://github.com/astral-sh/uv) for Python dependency management
- Multiple MCP (Model Context Protocol) servers for specialized tasks (code analysis, testing)
- A unified agent (`MCPEnhancedAgent`) to interact with these servers.

## Project Structure

```
├── agents/                     # Specialized MCP servers & clients
│   ├── mcp_code_server.py      # Server for code analysis, formatting, fixing
│   └── mcp_test_server.py      # Server for running tests
├── examples/
│   ├── mcp_code_client.py      # Client example for code server
│   ├── mcp_test_client.py      # Client example for test server
│   └── mcp_enhanced_agent_demo.py # Demo script for the enhanced agent
├── src/
│   ├── mcp_enhanced_agent.py   # Unified agent implementation
│   └── storage/
│       └── database.py         # SQLite database manager
├── tests/
│   └── test_sample/
│       └── test_simple.py      # Sample test file
├── data/
│   └── mcp.db                  # SQLite database file (created automatically)
├── memory-bank/                # Project memory and context
├── scripts/
│   └── setup.sh                # Setup script (may need updates)
├── .env.example                # Example environment variables
├── .gitignore
├── README.md
└── requirements.txt            # Project dependencies
```

## Prerequisites

- Python 3.10+
- [UV](https://github.com/astral-sh/uv) installed
- [Ollama](https://github.com/ollama/ollama) installed locally (Optional, if using Ollama-based agents)
- [Docker](https://www.docker.com/) installed (Optional, for running tests in Docker via MCP Test Server)
- `ruff` installed globally or available in the environment (`pip install ruff`)

## Quick Setup

1.  **Clone the repository**:
    ```bash
    git clone <repository-url>
    cd base-agent 
    ```

2.  **Set up virtual environment and install dependencies**:
    ```bash
    uv venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    uv pip install -r requirements.txt
    ```

3.  **(Optional) Pull Ollama models**:
    ```bash
    ollama pull mistral:7b
    ```

4.  **(Optional) Copy environment variables**:
    ```bash
    cp .env.example .env 
    # Adjust variables in .env if needed (e.g., server ports, DB path)
    ```

## MCP Servers

This project utilizes specialized MCP servers for different backend tasks. They store their data in `data/mcp.db` (SQLite).

### 1. MCP Code Server

- **Purpose**: Handles code analysis (linting), formatting, auto-fixing (using Ruff for Python), and storing/retrieving code snippets.
- **Run**: 
  ```bash
  python agents/mcp_code_server.py
  ```
- **Default Port**: 8081 (Configurable via `MCP_CODE_PORT` env var)
- **Key Endpoints**:
    - `POST /analyze`: Analyze code for issues.
    - `POST /format`: Format code.
    - `POST /fix`: Analyze and attempt to fix code.
    - `POST /snippets`: Store a code snippet.
    - `GET /snippets/{id}`: Retrieve a code snippet.
    - `GET /snippets`: List snippet IDs.
- **API Docs**: http://localhost:8081/docs (when running)

### 2. MCP Test Server

- **Purpose**: Runs tests (pytest, unittest, nose2) locally or in Docker.
- **Default Port**: 8082 (Configurable via `MCP_TEST_PORT` env var)
- **API Docs**: http://localhost:8082/docs (when running)
- **Key Features**: Local/Docker execution, result persistence, output streaming, multiple runners.

## Usage

### Running the Enhanced Agent Demo

The `MCPEnhancedAgent` (`src/mcp_enhanced_agent.py`) provides a unified Python interface to interact with both MCP servers.

To see it in action, first start both MCP servers (see above), then run the demo script:

```bash
python examples/mcp_enhanced_agent_demo.py
```

This demo will:
1.  Analyze sample code using the Code Server.
2.  Attempt to fix the sample code using the Code Server.
3.  Run sample tests located in `tests/test_sample` using the Test Server.
4.  Display the results and analysis from both servers.

### Using the Agent or Servers Directly

- You can integrate the `MCPEnhancedAgent` into your own applications.
- You can interact with the MCP servers directly via HTTP requests (see client examples in `examples/` and the server API docs).

## Development

- **Running servers with auto-reload**:
The `uvicorn.run` command in the server scripts includes `reload=True` by default for development.
- **Database**: The SQLite database is stored at `data/mcp.db`. You can inspect it using tools like DB Browser for SQLite.

## Troubleshooting

- **Server Connection Issues**: Ensure the respective MCP servers are running. Check the host and port configured in your client or the `.env` file (defaults are `localhost:8081` for code, `localhost:8082` for test).
- **`ruff` not found**: Make sure `ruff` is installed (`uv pip install ruff` or `pip install ruff`) and accessible in your PATH.
- **Database Errors**: If you encounter issues, you can try deleting the `data/mcp.db` file. The servers will recreate it on startup.
- **Docker Test Errors**: Ensure Docker Desktop (or Docker Engine) is running if you are using the 'docker' mode for the test server.
- **Weather Tool Errors**: The `mcp_enhanced_agent_demo.py` uses a weather tool (`tools/weather_tool.py`) that requires an API key from [OpenWeatherMap](https://openweathermap.org/appid). Sign up for a free key and set the `OPENWEATHERMAP_API_KEY` environment variable.

## License

MIT License

```bash
export MCP_API_KEY="your-secret-key"
export MCP_CODE_SERVER_URL="http://localhost:8081"
export MCP_TEST_SERVER_URL="http://localhost:8082"
ollama serve &
./run_mcp_server.sh --server code &
./run_mcp_server.sh --server test &
streamlit run ui/app.py
```
