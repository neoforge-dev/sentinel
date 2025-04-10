# BaseAgent: Ollama + UV + MCP Integration

A powerful AI project that combines:
- [Ollama](https://github.com/ollama/ollama) for running local LLMs (DeepSeek-R1:32B and Mistral 7B)
- [UV](https://github.com/astral-sh/uv) for Python dependency management and single-file agents
- [MCP](https://github.com/microsoft/mcp) (Model Context Protocol) server integration

## Project Structure

```
├── agents/                # Single-file agents
│   └── agent.py           # Main agent implementation
├── src/                   # Source code directory
│   ├── baseagent/         # Main package
│   └── mcp_server.py      # MCP server implementation
├── scripts/               # Utility scripts
│   └── setup.sh           # Setup script
├── config/                # Configuration files
├── memory-bank/           # Project memory and context
└── requirements.txt       # Project dependencies
```

## Prerequisites

- Python 3.10+
- [UV](https://github.com/astral-sh/uv) for dependency management
- [Ollama](https://github.com/ollama/ollama) installed locally

## Quick Setup

The easiest way to set up the project is using our setup script:

```bash
# Make the script executable
chmod +x scripts/setup.sh

# Run the setup script
./scripts/setup.sh
```

The setup script will:
1. Check for Python 3.10+
2. Install UV and Ollama if not already installed
3. Set up a virtual environment
4. Install required dependencies
5. Download the necessary Ollama models
6. Initialize the project structure

## Manual Setup

If you prefer to set up manually:

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd baseagent
   ```

2. **Install UV**:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. **Install Ollama**:
   ```bash
   curl -LsSf https://ollama.ai/install.sh | sh
   ```

4. **Set up a virtual environment with UV**:
   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

5. **Install dependencies**:
   ```bash
   uv pip install -r requirements.txt
   ```

6. **Pull required Ollama models**:
   ```bash
   ollama pull mistral:7b
   ollama pull deepseek-r1:32b  # Optional - large model (32B parameters)
   ```

## Usage

### Starting the MCP Server

The MCP server provides context to your agents. Start it with:

```bash
python src/mcp_server.py
```

By default, the server runs on http://localhost:8080. You can customize with options:

```bash
python src/mcp_server.py --host 127.0.0.1 --port 9000 --debug
```

### Running the Agent

To run the agent and interact with the LLM:

```bash
# Run using the default model (Mistral 7B)
python agents/agent.py

# Specify a different model
python agents/agent.py --model deepseek-r1:32b

# Disable MCP integration
python agents/agent.py --no-mcp
```

### MCP API Endpoints

The MCP server provides these endpoints:

- `GET /context` - Get full context
- `GET /context/system` - Get system context
- `POST /context/documents` - Add a document
- `DELETE /context/documents/{id}` - Delete a document
- `POST /context/conversation` - Add a conversation message
- `DELETE /context/conversation` - Clear conversation history

### Example: Adding Context

You can add context to the MCP server that will be available to your agents:

```bash
curl -X POST http://localhost:8080/context/documents \
  -H "Content-Type: application/json" \
  -d '{
    "id": "example-doc",
    "content": "This is a sample document that provides context to the agent.",
    "metadata": {"type": "note", "tags": ["example", "documentation"]}
  }'
```

## Development

- **Running the MCP server in development mode**:
  ```bash
  python src/mcp_server.py --debug
  ```

- **Examining server endpoints**:
  Once the server is running, browse to http://localhost:8080/docs for the interactive API documentation.

## Troubleshooting

- **Ollama connection issues**: Ensure Ollama is running with `ollama serve`
- **MCP server connection**: Verify the server is running and check the URL in the agent configuration
- **Model not found**: Make sure you've pulled the model with `ollama pull <model-name>`

## License

MIT License
