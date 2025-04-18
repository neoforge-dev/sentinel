# Product Context: NEO Agent Framework - Optimized

## Problem Area
- Automate repetitive coding/testing tasks (analysis, format, run tests).
- Provide project-specific context missing in generic AI.
- Simplify cross-environment testing (local/Docker).

## Solution Overview
- Automated Developer Assistant (NEO Agent).
- Modular MCPs:
    - **Code MCP:** Code analysis, formatting, snippet DB.
    - **Test MCP:** Test execution (local/Docker), results DB.
- Persistence: SQLite.
- Communication: Standardized Agent-MCP APIs.

## Core Value
- Efficiency (faster cycles).
- Quality (consistent standards, reliable tests).
- Simplicity (easier test environment management).

## Key UX Goals
- Simple setup/operation.
- Clear feedback (logs, UI).
- User control (initiate tasks via Agent/UI).
- Transparency (view MCP operations/data).

## Conceptual Flow
1.  **Request:** User -> Agent/UI (e.g., "run tests", "analyze file").
2.  **Coordinate:** Agent -> Determines MCP.
3.  **Execute:** Agent -> Calls MCP API (e.g., Test Server `/run-tests`).
4.  **Process:** MCP -> Performs action (e.g., runs `pytest`).
5.  **Feedback:** MCP -> Agent -> User (e.g., streams output, shows results).
6.  **Persist:** MCP -> Stores data (test results, snippets).
