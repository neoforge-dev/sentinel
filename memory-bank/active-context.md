# Active Context - Optimized

## Current Focus
- **Stabilization:** Address tech debt for reliability.
    - Fix test suite instability/coverage (esp. Docker tests).
    - Implement consistent logging/error handling.
    - Complete/verify Docker test execution in MCP Test Server.
    - Resolve build warnings (Docker root user).

## Current Work Focus / Priority
- **Stabilize Test Suite:**
    - **Priority 1: Implement `run_tests_docker` correctly:** Refactor to separate streaming/non-streaming paths, fix `SyntaxError: 'return' with value in async generator`, pass TDD integration test (`test_run_docker_mode_success_and_verify_db`). (Addresses Known Issue #2).
    - Resolve `pytest-asyncio` warnings. (Addresses Known Issue #3).
    - Increase coverage (MCP Test Server critical paths). (Addresses Known Issue #1).

## Recent Changes (Summary)
- Optimized `project-brief.md` & `product-context.md`.
- Fixed various test server issues (import errors, route errors, FastAPI model errors, streaming `TypeError`).
- Fixed intentional test failures (`xfail`).
- Standardized server ports (8081/8082).
- Resolved `ModuleNotFoundError` for direct script runs (use `python -m ...`).

## Next Steps (Post-Stabilization)
1.  **Logging/Error Handling:** Global handler, standardized format.
2.  **Docker Build/CI:** Fix Dockerfile warnings, add smoke test.
3.  **UI Enhancements:** Improve robustness, feedback.
4.  **Refine Plugin System.**
5.  **Integrate More Tools.**

## Active Decisions/Considerations
- **Architecture:** Separate MCPs (Code/Test), FastAPI, Docker.
- **Technical:** Python path (`-m`), Docker setup, Ports (8081/8082).
- **Auth:** Basic API Key.

## Open Questions
- Best fix for `pytest-asyncio` warnings?
- Optimize Docker test performance?
- Support other test runners?
- Agent plugin discovery mechanism?
