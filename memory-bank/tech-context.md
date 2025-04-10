# Tech Context

## Technologies Used

### Core Technologies

- **Python 3.10+**: Base programming language
- **Ollama**: Local LLM runtime
  - Support for Mistral 7B, DeepSeek-R1:32B, and other models
- **UV**: Modern Python dependency management
- **FastAPI**: Web framework for MCP servers
- **Uvicorn**: ASGI server for running FastAPI
- **Requests**: HTTP library for API communication
- **Pydantic**: Data validation and settings management

### Analysis and Testing

- **Ruff**: Python linter and formatter for code analysis
- **pytest**: Testing framework for Python
- **unittest**: Standard Python testing framework
- **Docker**: Container runtime for isolated test execution
- **tiktoken**: OpenAI's tokenizer for managing output size

### Development Tools

- **Git**: Version control
- **Bash**: Shell scripting for setup
- **Markdown**: Documentation format

## Development Setup

1. **Requirements**:
   - Python 3.10+
   - Git
   - Unix-like shell (Bash, Zsh)
   - Docker (optional, for containerized testing)

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
   - Run the main MCP server: `python src/mcp_server.py --debug`
   - Run the code analysis MCP server: `python agents/mcp_code_server.py`
   - Run the test runner MCP server: `python agents/mcp_test_server.py`
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
     - Main MCP Server: 8080
     - Code Analysis MCP Server: 8000
     - Test Runner MCP Server: 8001
   - All services run locally by default

3. **Storage Requirements**:
   - Ollama models can be large:
     - Mistral 7B: ~4GB
     - DeepSeek-R1:32B: ~16GB
   - Docker images (if using containerized testing)

## Dependencies

### Runtime Dependencies

```
fastapi>=0.104.0
uvicorn>=0.23.2
requests>=2.31.0
pydantic>=2.4.2
ruff>=0.1.0
tiktoken>=0.5.0
docker>=6.1.0
```

### External Services

1. **Ollama**:
   - GitHub: https://github.com/ollama/ollama
   - Installation: `curl -LsSf https://ollama.ai/install.sh | sh`
   - Must be running with `ollama serve`

2. **UV**:
   - GitHub: https://github.com/astral-sh/uv
   - Installation: `curl -LsSf https://astral.sh/uv/install.sh | sh`

3. **Docker** (optional):
   - Website: https://www.docker.com/
   - Used for isolated test execution
   - Installation varies by platform

## Environment Variables

- `OLLAMA_HOST`: URL for Ollama API (default: `http://localhost:11434`)
- `MCP_SERVER_URL`: URL for main MCP server (default: `http://localhost:8080`)
- `MCP_CODE_SERVER_URL`: URL for code analysis MCP server (default: `http://localhost:8000`) 
- `MCP_TEST_SERVER_URL`: URL for test runner MCP server (default: `http://localhost:8001`)
- `DEBUG`: Enable debug mode if set to "1" or "true"

## API Documentation

The MCP servers provide built-in API documentation:
- Main MCP Server: `http://localhost:8080/docs`
- Code Analysis Server: `http://localhost:8000/docs`
- Test Runner Server: `http://localhost:8001/docs` 