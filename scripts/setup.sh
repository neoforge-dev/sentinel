#!/bin/bash
# BaseAgent setup script
# Sets up Ollama, UV, and MCP environment

set -e

echo "🚀 Setting up BaseAgent environment..."
echo "========================================"

# Check if Python 3.10+ is installed
echo "Checking Python version..."
python_version=$(python3 --version | cut -d' ' -f2)
if [[ $(echo "$python_version" | cut -d. -f1,2 | sed 's/\.//') -lt 310 ]]; then
    echo "❌ Error: Python 3.10 or higher is required (found $python_version)"
    echo "Please install Python 3.10+ and try again"
    exit 1
fi
echo "✅ Python $python_version found"

# Check if UV is installed
if ! command -v uv &> /dev/null; then
    echo "❌ UV is not installed"
    echo "Installing UV..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source "$HOME/.cargo/env"
fi
echo "✅ UV is installed"

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "❌ Ollama is not installed"
    echo "Installing Ollama..."
    curl -LsSf https://ollama.ai/install.sh | sh
fi
echo "✅ Ollama is installed"

# Create virtual environment
echo "Creating virtual environment..."
uv venv .venv
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
uv pip install -r requirements.txt

# Create required directories
echo "Creating project directories..."
mkdir -p agents src/baseagent config memory-bank

# Pull Ollama models
echo "Downloading required Ollama models (this may take a while)..."
ollama pull mistral:7b

echo "Do you want to download DeepSeek-R1:32B as well? (y/n)"
read -r download_deepseek
if [[ "$download_deepseek" == "y" ]]; then
    echo "Downloading DeepSeek-R1:32B (this is a large model and will take time)..."
    ollama pull deepseek-r1:32b
fi

# Create memory-bank files if they don't exist
echo "Setting up memory-bank..."
if [ ! -f "memory-bank/project-brief.md" ]; then
    echo "# Project Brief" > memory-bank/project-brief.md
    echo "BaseAgent: Ollama + UV + MCP Integration project" >> memory-bank/project-brief.md
fi

if [ ! -f "memory-bank/product-context.md" ]; then
    echo "# Product Context" > memory-bank/product-context.md
    echo "BaseAgent combines Ollama for local LLMs with UV for dependency management and MCP for context." >> memory-bank/product-context.md
fi

if [ ! -f "memory-bank/active-context.md" ]; then
    echo "# Active Context" > memory-bank/active-context.md
    echo "Project setup in progress. Next steps: test agent and MCP server." >> memory-bank/active-context.md
fi

if [ ! -f "memory-bank/system-patterns.md" ]; then
    echo "# System Patterns" > memory-bank/system-patterns.md
    echo "- Agent communicates with Ollama API" >> memory-bank/system-patterns.md
    echo "- MCP server provides context to agents" >> memory-bank/system-patterns.md
fi

if [ ! -f "memory-bank/tech-context.md" ]; then
    echo "# Tech Context" > memory-bank/tech-context.md
    echo "- Python 3.10+" >> memory-bank/tech-context.md
    echo "- UV for dependency management" >> memory-bank/tech-context.md
    echo "- Ollama for running local LLMs" >> memory-bank/tech-context.md
    echo "- FastAPI for MCP server" >> memory-bank/tech-context.md
fi

if [ ! -f "memory-bank/progress.md" ]; then
    echo "# Progress" > memory-bank/progress.md
    echo "- [x] Project structure created" >> memory-bank/progress.md
    echo "- [x] Setup script implemented" >> memory-bank/progress.md
    echo "- [ ] Test agent functionality" >> memory-bank/progress.md
    echo "- [ ] Test MCP server" >> memory-bank/progress.md
fi

# Create requirements.txt file
echo "Creating requirements.txt..."
cat > requirements.txt << EOF
fastapi>=0.104.0
uvicorn>=0.23.2
requests>=2.31.0
pydantic>=2.4.2
EOF

echo "✅ Setup complete!"
echo ""
echo "To get started:"
echo "  1. Activate the virtual environment: source .venv/bin/activate"
echo "  2. Start the MCP server: python src/mcp_server.py"
echo "  3. In a new terminal, run the agent: python agents/agent.py"
echo "" 