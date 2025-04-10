# Tech Context

## Technologies Used

### Core Technologies

- **Python 3.10+**: Base programming language
- **Ollama**: Local LLM runtime
  - Support for Mistral 7B, DeepSeek-R1:32B, and other models
- **UV**: Modern Python dependency management
- **FastAPI**: Web framework for MCP server
- **Uvicorn**: ASGI server for running FastAPI
- **Requests**: HTTP library for API communication
- **Pydantic**: Data validation and settings management

### Development Tools

- **Git**: Version control
- **Bash**: Shell scripting for setup
- **Markdown**: Documentation format

## Development Setup

1. **Requirements**:
   - Python 3.10+
   - Git
   - Unix-like shell (Bash, Zsh)

2. **Environment Setup**:
   ```bash
   # Clone the repository
   git clone <repo-url>
   cd baseagent
   
   # Run setup script
   chmod +x scripts/setup.sh
   ./scripts/setup.sh
   
   # Activate virtual environment
   source .venv/bin/activate
   ```

3. **Development Workflow**:
   - Edit files in the `src/` and `agents/` directories
   - Run the MCP server: `python src/mcp_server.py --debug`
   - Test agents: `python agents/agent.py`

## Technical Constraints

1. **LLM Requirements**:
   - Ollama must be installed and running
   - Sufficient system resources for selected models:
     - Mistral 7B: 8GB+ RAM
     - DeepSeek-R1:32B: 32GB+ RAM, GPU recommended

2. **Network Requirements**:
   - Default ports:
     - Ollama: 11434
     - MCP Server: 8080
   - Both services run locally by default

3. **Storage Requirements**:
   - Ollama models can be large:
     - Mistral 7B: ~4GB
     - DeepSeek-R1:32B: ~16GB

## Dependencies

### Runtime Dependencies

```
fastapi>=0.104.0
uvicorn>=0.23.2
requests>=2.31.0
pydantic>=2.4.2
```

### External Services

1. **Ollama**:
   - GitHub: https://github.com/ollama/ollama
   - Installation: `curl -LsSf https://ollama.ai/install.sh | sh`
   - Must be running with `ollama serve`

2. **UV**:
   - GitHub: https://github.com/astral-sh/uv
   - Installation: `curl -LsSf https://astral.sh/uv/install.sh | sh`

## Environment Variables

- `OLLAMA_HOST`: URL for Ollama API (default: `http://localhost:11434`)
- `MCP_SERVER_URL`: URL for MCP server (default: `http://localhost:8080`)
- `DEBUG`: Enable debug mode if set to "1" or "true"

## API Documentation

The MCP server provides built-in API documentation:
- Swagger UI: `http://localhost:8080/docs`
- ReDoc: `http://localhost:8080/redoc` 