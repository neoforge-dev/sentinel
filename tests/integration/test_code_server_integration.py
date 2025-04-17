"""
Integration tests for the MCP Code Server API endpoints.

Requires the MCP Code Server to be running.
"""

import sys
import os
import pytest
import httpx
import asyncio
import subprocess
import time
from typing import AsyncGenerator, AsyncIterator
import pytest_asyncio
from multiprocessing import Process
import logging

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Import the correct URL from conftest
from tests.conftest import CODE_SERVER_URL, API_KEY

# Define server address (adjust if needed, could use env vars)
# Make sure this matches how you run the server during tests
# SERVER_URL = "http://localhost:8000" # Removed redundant/incorrect constant
# Use the actual API key expected by the server
# API_KEY = os.environ.get("MCP_API_KEY", "dev_secret_key") # Defined in conftest

pytest_plugins = ['pytest_asyncio']

# --- Fixtures --- 

@pytest.fixture(scope="session")
def event_loop():
    # Force loop creation for session scope if needed, handle potential deprecations
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="module") # Keep server process module-scoped
async def code_server_process(event_loop):
    """Fixture to start/stop the MCP Code Server process for the module."""
    process = None
    # Command to run the server (adjust path if needed)
    # Use python -m to ensure correct module resolution from project root
    server_command = [sys.executable, "-m", "agents.mcp_code_server"]
    logger.info(f"Starting MCP Code Server with command: {' '.join(server_command)}")
    try:
        # Use subprocess.Popen for better control
        process = subprocess.Popen(server_command, env=os.environ.copy())
        # Wait a moment for the server to start
        await asyncio.sleep(3) # Adjust sleep time if needed
        # Check if the process started successfully
        if process.poll() is not None:
            raise RuntimeError(f"MCP Code Server failed to start. Exit code: {process.poll()}")
        logger.info(f"MCP Code Server started successfully (PID: {process.pid}).")
        yield process # Yield the process object to tests
    except Exception as e:
        logger.error(f"Failed to start MCP Code Server: {e}", exc_info=True)
        if process and process.poll() is None:
            process.kill()
            process.wait()
        pytest.fail(f"Failed to start MCP Code Server: {e}", pytrace=False)
        return # Ensure no yield happens on failure
    finally:
        # --- Robust Teardown Logic --- 
        logger.info("Tearing down MCP Code Server fixture...")
        if process and process.poll() is None: # Check if process is still running
            logger.info(f"Terminating Code Server (PID: {process.pid})...")
            process.terminate()
            try:
                process.wait(timeout=5) # Wait for termination
                logger.info("Code Server terminated.")
            except subprocess.TimeoutExpired:
                logger.warning(f"Code Server (PID: {process.pid}) did not terminate gracefully. Killing...")
                process.kill() # Force kill if it doesn't terminate
                try:
                    process.wait(timeout=2)
                    logger.info("Code Server killed.")
                except Exception as e_kill:
                    logger.error(f"Error waiting for Code Server kill: {e_kill}")
            except Exception as e_term:
                logger.error(f"Error during Code Server termination: {e_term}")
                # Attempt to kill even if terminate failed
                if process.poll() is None:
                    try:
                        process.kill()
                        process.wait(timeout=2)
                        logger.info("Code Server killed after termination error.")
                    except Exception as e_kill_final:
                         logger.error(f"Error during final Code Server kill attempt: {e_kill_final}")
        elif process:
             logger.info(f"Code Server (PID: {process.pid}) already terminated (exit code: {process.poll()}).")
        else:
            logger.info("Code Server process was not started or already cleaned up.")

@pytest_asyncio.fixture(scope="function") # <<< CHANGED SCOPE TO FUNCTION
async def http_client(code_server_process) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provides an httpx AsyncClient scoped to the function, dependent on the server."""
    # base_url = f"http://localhost:8000"
    headers = {"X-API-Key": API_KEY}
    # Use the imported CODE_SERVER_URL
    async with httpx.AsyncClient(base_url=CODE_SERVER_URL, headers=headers, timeout=30.0) as client:
        # Optional: Add a check here to ensure the server is running before tests start
        # try:
        #     await client.get("/") 
        # except httpx.ConnectError:
        #     pytest.fail(f"MCP Code Server not running at {base_url}", pytrace=False)
        yield client
    # Client is automatically closed by async context manager

# --- Test Cases --- 

@pytest.mark.asyncio
async def test_root_endpoint(http_client: httpx.AsyncClient):
    """Test the root endpoint returns 200 OK."""
    response = await http_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data.get("service") == "MCP Code Server"
    assert data.get("status") == "active"

@pytest.mark.asyncio
async def test_analyze_python_code(http_client: httpx.AsyncClient):
    """Test the /analyze endpoint with simple Python code."""
    code = "import os\nprint(os.name)"
    response = await http_client.post("/analyze", json={"code": code, "language": "python"})
    assert response.status_code == 200
    data = response.json()
    assert "issues" in data
    assert isinstance(data["issues"], list)
    assert not data["issues"] # Expect no issues for this valid code
    assert "formatted_code" in data

@pytest.mark.asyncio
async def test_analyze_python_with_issues(http_client: httpx.AsyncClient):
    """Test analyzing Python code known to have issues (unused import)."""
    code = "import sys\ndef main(): pass"
    response = await http_client.post("/analyze", json={"code": code, "language": "python"})
    assert response.status_code == 200
    data = response.json()
    assert "issues" in data
    assert isinstance(data["issues"], list)
    assert len(data["issues"]) > 0
    # Check for specific Ruff code for unused import (adjust if needed)
    assert any("F401" in issue.get("code", "") for issue in data["issues"])

@pytest.mark.asyncio
async def test_format_python_code(http_client: httpx.AsyncClient):
    """Test the /format endpoint."""
    code = "def func( x ):\n  return x+1"
    response = await http_client.post("/format", json={"code": code, "language": "python"})
    assert response.status_code == 200
    data = response.json()
    assert "formatted_code" in data
    assert data["formatted_code"] == "def func(x):\n    return x + 1\n" # Expect ruff formatting

@pytest.mark.asyncio
async def test_fix_python_code(http_client: httpx.AsyncClient):
    """Test the /fix endpoint."""
    code = "import os, sys\nprint('hello')" # Unused imports
    response = await http_client.post("/fix", json={"code": code, "language": "python"})
    assert response.status_code == 200
    data = response.json()
    assert "fixed_code" in data
    assert "import os" not in data["fixed_code"]
    assert "import sys" not in data["fixed_code"] # Ruff should remove both
    assert "issues_remaining" in data
    assert isinstance(data["issues_remaining"], list)

@pytest.mark.asyncio
async def test_snippet_storage_retrieval(http_client: httpx.AsyncClient):
    """Test storing and retrieving a code snippet."""
    snippet_code = "def test_func(): return 42"
    snippet_lang = "python"
    
    # Store snippet
    store_response = await http_client.post(
        "/snippets",
        json={"code": snippet_code, "language": snippet_lang}
    )
    assert store_response.status_code == 200
    store_data = store_response.json()
    assert "id" in store_data
    snippet_id = store_data["id"]
    assert store_data.get("code") == snippet_code # Check returned data

    # Retrieve snippet
    get_response = await http_client.get(f"/snippets/{snippet_id}")
    assert get_response.status_code == 200
    get_data = get_response.json()
    assert get_data.get("id") == snippet_id
    assert get_data.get("code") == snippet_code
    assert get_data.get("language") == snippet_lang

@pytest.mark.asyncio
async def test_get_nonexistent_snippet(http_client: httpx.AsyncClient):
    """Test retrieving a non-existent snippet returns 404."""
    non_existent_id = "non-existent-snippet-id-12345"
    response = await http_client.get(f"/snippets/{non_existent_id}")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data # FastAPI 404 includes detail
    assert "not found" in data["detail"].lower()

@pytest.mark.asyncio
async def test_analyze_invalid_syntax(http_client: httpx.AsyncClient):
    """Test analyzing code with syntax errors returns issues but succeeds (200)."""
    code_with_syntax_error = "def func(:\n    pass"
    response = await http_client.post("/analyze", json={"code": code_with_syntax_error, "language": "python"})
    assert response.status_code == 200 # Analyze endpoint should still succeed
    data = response.json()
    assert "issues" in data
    assert len(data["issues"]) > 0
    # Check for Ruff syntax error code (e.g., E999) or message
    # Make the check robust against None values
    found_syntax_error = False
    for issue in data["issues"]:
        issue_code = issue.get("code")
        issue_message = issue.get("message", "").lower()
        if (issue_code and "E999" in issue_code) or ("syntax error" in issue_message):
            found_syntax_error = True
            break
    assert found_syntax_error, "Expected to find a syntax error (E999) or relevant message in issues"
    # Check that formatted code might be original on error
    assert "formatted_code" in data 

@pytest.mark.asyncio
async def test_format_invalid_syntax(http_client: httpx.AsyncClient):
    """Test formatting code with syntax errors returns a 400 error."""
    code_with_syntax_error = "def func(:\n    pass"
    response = await http_client.post("/format", json={"code": code_with_syntax_error, "language": "python"})
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data # FastAPI 400 includes detail
    assert "syntax error" in data["detail"].lower()

# Add more tests: analyze non-python, format non-python (should pass-through),
# store snippet with specific ID, handle potential 500 errors if ruff missing? 

# Remove the standalone teardown function as it's now integrated 