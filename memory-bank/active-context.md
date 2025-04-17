# Active Context

## Current Work Focus
- Developing Base Agent system with MCP architecture.
- Components: MCP Code Server (8081), MCP Test Server (8082), Agent Framework, Communication Layer.
- **Priority**: Stabilize test suite (address warnings).

## Recent Changes (Key Points)
- Implemented robust fixture teardown for server processes.
- Fixed `!code` command stream handling in `agents/agent.py`.
- Fixed `AttributeError` and `TypeError` in streaming tests.
- Standardized server ports (8081, 8082).
- Resolved `ModuleNotFoundError` for direct script execution (use `python -m ...`).
- Updated memory bank docs.
- Fixed intentional test failures in `tests/test_sample/test_simple.py` by marking them as `xfail`.

## Next Steps (Prioritized)
1. **Address Warnings**: Investigate and fix `pytest-asyncio` fixture/loop warnings, FastAPI `on_event` deprecation warnings, and other warnings from the test suite.
2. **Resolve Test Failures**: ~~Address remaining assertion errors in `test_mcp_test_server.py` related to stream content.~~ (Check if any actual failures remain after fixing sample tests).
3. **Logging**: Implement consistent logging across components.
4. **Error Handling**: Implement consistent error handling patterns.
5. **Web UI**: Enhance functionality.
6. **Tool Integration**: Add more tools.

## Active Decisions/Considerations
- **Architecture**: Separate MCP servers (Code/Test), FastAPI, Docker isolation.
- **Technical**: Python path (`pip install -e .` or `python -m`), Docker permissions, Port conflicts (8081/8082).
- **Auth**: Basic API Key sufficient for now.

## Open Questions
- Best approach for `pytest-asyncio` warnings?
- Optimize Docker test performance?
- Support other test frameworks?
