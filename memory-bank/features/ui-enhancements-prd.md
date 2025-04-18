# PRD: Web UI Enhancements V1

**Status:** Proposed
**Author:** NEO (AI Agent)
**Date:** 2024-08-17

## 1. Overview

This document outlines the requirements for the first major enhancement phase of the NEO Agent Framework's Streamlit Web UI. The goal is to improve usability, clarity, and provide better feedback mechanisms based on the existing core functionalities (code analysis, test running).

**Prerequisite:** This work should only commence *after* the P0 Stabilization Blockers identified in `active-context.md` (Test Suite Stability, Logging/Error Handling, Docker Build) are resolved.

## 2. Problem Statement

The current Web UI is functional for basic operations but lacks robustness and user-friendly feedback:
*   **Limited Feedback:** Test output is streamed as raw text/logs, making it hard to quickly grasp the overall status (pass/fail counts, summaries). Error reporting is basic.
*   **No History:** Test results are transient; users cannot easily review past runs without checking logs or potentially a database directly (which isn't exposed via UI).
*   **Basic Interaction:** Configuration options are minimal, and there's no way to manage snippets or view detailed stored results.

## 3. Goals

*   Improve clarity of test execution status and results.
*   Provide access to historical test run summaries.
*   Enhance error reporting and user feedback for all operations.
*   Make the UI more resilient to backend errors.

## 4. Non-Goals

*   Complete UI framework change (sticking with Streamlit for V1).
*   Adding fundamentally new agent capabilities via the UI (focus on exposing existing ones better).
*   Advanced user management or authentication beyond the current API key.
*   Real-time collaboration features.

## 5. Proposed Solution - Key Features

### 5.1. Test Runner Enhancements
*   **Structured Output Display:** Instead of raw streaming text, parse the output (or use structured data from the Test MCP if available post-run) to show:
    *   Clear Pass/Fail/Error/Skipped counts.
    *   A concise summary section (similar to `pytest` summary).
    *   Collapsible sections for detailed stdout/stderr/failures.
*   **Status Indicators:** Use visual cues (e.g., icons, colors) for ongoing tests and final status.
*   **Result History Tab:**
    *   Add a new tab/section to the UI.
    *   Fetch and display a list of recent test runs from the MCP Test Server's result database (`/results` endpoint).
    *   Show key summary info for each run (ID, Timestamp, Status, Runner, Mode, Passed/Failed counts).
    *   Allow clicking a run to view its detailed stored results (summary, details - potentially truncated).

### 5.2. Code Operations Enhancements
*   **Clearer Status/Error Messages:** Provide more informative messages on success/failure for analyze, format, fix operations, potentially linking to specific errors.
*   **Input Persistence (Optional):** Consider retaining code input across page interactions within a session.

### 5.3. General UI Improvements
*   **Improved Error Handling:** Catch errors from agent/MCP calls gracefully and display user-friendly messages (potentially referencing a correlation ID if logging is implemented).
*   **Loading Indicators:** Use spinners more consistently during backend operations.
*   **Configuration Feedback:** Provide clearer feedback on whether the agent connection is successful.

## 6. User Stories

*   As a developer, I want to see a clear summary (pass/fail counts) after running tests via the UI, so I can quickly understand the outcome.
*   As a developer, I want to view the results of previous test runs via the UI, so I can track progress or investigate past failures without digging through logs.
*   As a developer, I want clear, actionable error messages in the UI when an operation fails, so I know what went wrong.
*   As a developer, I want the UI to indicate clearly when it's busy processing a request.

## 7. Technical Design Sketch

*   **Backend:** Requires the MCP Test Server `/results` and `/results/{result_id}` endpoints to be stable and return structured data. May require minor adjustments to agent methods (`MCPEnhancedAgent`) to return more structured error information.
*   **Frontend (`ui/app.py`):**
    *   Modify the `run_tests` function to handle streamed output differently, parsing for key information or making a final call to `/results/{result_id}` to get the structured summary.
    *   Implement a new section/tab using Streamlit components.
    *   Use `st.session_state` to manage state between interactions (e.g., selected historical run).
    *   Add more robust `try...except` blocks around agent calls, displaying formatted errors using `st.error` or `st.exception`.
    *   Utilize Streamlit caching (`@st.cache_data`) for fetching the list of historical results to improve responsiveness.

## 8. Open Questions

*   How much history should the "Result History" display by default? (Pagination?)
*   Exact format/structure returned by `/results` endpoint – does it contain everything needed?
*   Feasibility of parsing the *live* stream for summary info vs. waiting for the run to complete and fetching the final result record? (Latter might be simpler initially). 