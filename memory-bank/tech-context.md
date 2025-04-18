# Tech Context - Optimized

## Key Technologies
- **Backend**: Python 3.10+, FastAPI, Pydantic, asyncio
- **Testing**: pytest, pytest-asyncio, Docker
- **Storage**: SQLite (`DatabaseManager`)
- **Deps Mgt**: UV
- **Comms**: httpx (client)
- **UI**: Streamlit
- **Lint/Format**: Ruff (via MCP Code Server), Black, isort
- **CI/CD**: GitHub Actions

## Development Setup & Commands
- **Env Setup**: `uv venv`, `source .venv/bin/activate`
- **Install Deps**: `uv pip install -r requirements.txt`
- **Run Code Server**: `uv run python -m agents.mcp_code_server` (Port 8081)
- **Run Test Server**: `uv run python -m agents.mcp_test_server` (Port 8082)
- **Run UI**: `uv run streamlit run ui/app.py`
- **Run Tests**: `make test` / `make test-integration`
- **API Key**: Set `MCP_API_KEY` env var (default: `dev_secret_key`).

## Key Constraints & Considerations
- **Environment**: Python 3.10+, Docker required for Docker test mode.
- **Python Path**: Use `python -m ...` or `uv run ...` for module execution.
- **Known Issues / Tech Debt**:
    - `pytest-asyncio` fixture/loop warnings.
    - Docker `pip as root` build warnings.
    - Docker test latency.
    - Need for consistent logging/error handling patterns.
    - Test coverage needs improvement.
- **Security**: Basic API Key, Docker isolation needs care, Input validation required.
