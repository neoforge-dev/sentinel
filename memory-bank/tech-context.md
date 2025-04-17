# Tech Context

## Technologies Used
- **Core**: Python 3.10+, FastAPI, Pydantic, asyncio, httpx
- **Testing**: pytest, pytest-asyncio, Docker
- **Storage**: SQLite (via `DatabaseManager`)
- **Deps**: UV
- **UI**: Streamlit
- **Dev Tools**: Black, isort, mypy
- **CI/CD**: GitHub Actions, GHCR

## Development Setup
- **Install**: `uv pip install -e .` (Dev mode) or `uv pip install -r requirements.txt`
- **Run (Servers)**: `python -m agents.mcp_code_server`, `python -m agents.mcp_test_server`
- **Run (UI)**: `streamlit run web/app.py`
- **Ports**: Code Server = 8081, Test Server = 8082
- **Docker**: Required for Docker test mode.
- **Python Path**: `python -m ...` preferred over setting `PYTHONPATH`.
- **API Key**: Set `AGENT_API_KEY` env var (default: `dev_secret_key`).

## Technical Constraints / Known Issues
- **Testing**: Requires pytest, Docker permissions (for Docker mode).
- **Warnings**: `pytest-asyncio` fixture/loop warnings, Docker `pip as root` warnings.
- **Docker Latency**: Docker tests are slower than local.

## Core Dependencies
- Python 3.10+, FastAPI, Docker, pytest, asyncio, httpx, pydantic, aiosqlite, requests, tenacity, colorama

## Technical Debt
- Address `pytest-asyncio` & Docker warnings.
- Consistent logging approach.
- Consistent error handling patterns.
- Improve test coverage (edge cases).

## Performance Considerations
- Docker overhead.
- Port availability (8081, 8082).
- Concurrent test resource management.

## Security Considerations
- **Auth**: Basic API Key (enhance later?).
- **Docker**: Run containers securely.
- **Input Validation**: Needed for APIs.
- **Error Reporting**: Avoid leaking sensitive info.

## CI/CD Integration
- **CI**: GitHub Actions (Lint, Test).
- **CD**: Basic Docker image build/push to GHCR.
