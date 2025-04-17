# System Patterns

## Architecture Overview
- **MCP**: Central coordination.
  - **Code Server (8081)**: Code analysis, transformation, snippet storage.
  - **Test Server (8082)**: Test execution (local/Docker), result storage.
- **Agent Framework**: Base for specialized agents.
- **Testing Infra**: Local & Docker execution modes.
- **Communication Layer**: Standardized JSON APIs.

## Key Technical Decisions
- **Server Ports**: Code=8081, Test=8082.
- **Test Modes**: `run_tests_local`, `run_tests_docker`.
- **Test Status**: "success", "failed", "error" (based on test outcome, not just process exit code).
- **Error Handling**: Specific handling for `OSError`, Docker failures; Structured error responses.
- **API**: RESTful, JSON payloads, API Key auth.

## Design Patterns Used
- Server-Client
- Asynchronous Processing (asyncio)
- Context Managers (resource mgmt)
- Dependency Injection
- DTOs (Pydantic)

## Component Relationships (Key)
- Test Server -> Test Runners (pytest/unittest/nose2)
- Test Runners -> Docker (for Docker mode)
- Agent -> MCP Servers (via plugins)

## Important System Behaviors
- **Test Status**: Determined by test results (passed/failed) & execution errors.
- **Docker**: Isolated execution, log capture, result determination, cleanup.
- **Path Mgmt**: `pip install -e .` or `python -m ...` required for imports.
- **Error Propagation**: Contextual errors, appropriate HTTP codes.
- **Resource Mgmt**: Process/container termination, async cleanup.

## Architectural Constraints
- **Environment**: Python 3.10+, Docker required for Docker tests.
- **API**: REST consistency, Standard JSON formats, Consistent error structure.
- **Security**: API Key auth, Docker isolation, Input validation.
- **Scalability**: Independent components, Async support.
