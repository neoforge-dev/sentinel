# Product Context Summary

## Problem
Running context-aware AI agents locally is complex (LLM integration, deps, persistence, tasks).

## Solution: BaseAgent
Integrates **Ollama**, **UV**, **MCP** (Code/Test servers), and **Communication Layer** for streamlined local agent development with local & Docker testing.

## Target Users
- Developers (local/private agents)
- Researchers (agent architectures)
- Privacy-focused builders
- Teams needing isolated test environments

## Key Goals
- Simple Setup
- Model Flexibility (Ollama)
- Specialized Tasks (MCPs)
- Extensibility (Plugins)
- Isolated Testing (Docker)
- Consistent Communication (JSON)

## How It Works (High Level)
1. **Setup**: Install Ollama, UV; Clone repo; `uv pip install -r requirements.txt`.
2. **Run**: Start MCP Servers (Code: 8081, Test: 8082); Run Agent/UI.
3. **Interact**: Agent uses Ollama (generation) & MCPs (analysis, testing via plugins).
4. **Testing**: MCP Test Server runs tests locally or in Docker.
5. **Communicate**: Components use standardized JSON schemas.

## Core Benefits
- **Privacy/Cost**: Local LLM execution.
- **Control**: Over models/agents.
- **Specialized Tasks**: MCPs handle complex logic.
- **Simplicity**: UV deps, FastAPI servers.
- **Isolation**: Docker testing.
- **Standardization**: Consistent APIs/data.
- **Flexibility**: Local/Docker testing.

## Architecture Highlights
- **MCP Servers**: Code (8081), Test (8082).
- **Agent Framework**: Core structure.
- **Communication Layer**: Standardized JSON.
- **Testing Infrastructure**: Local & Docker support.
- **Docker Integration**: Isolated environments.
- **Pydantic Models**: Data validation/schemas.
