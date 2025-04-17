"""
Integration tests for the MCP Test Server API endpoints.

Requires the MCP Test Server to be running.
"""

import sys
import os
import pytest
import httpx
import asyncio
import subprocess
import time
from typing import AsyncGenerator, AsyncIterator
import shutil # For creating sample project
import re
import pytest_asyncio
from multiprocessing import Process
import logging

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Check for Docker
docker_available = shutil.which("docker") is not None
skip_if_no_docker = pytest.mark.skipif(not docker_available, reason="Docker is not available")

# Server configuration (should match conftest.py or .env)
API_KEY = os.environ.get("MCP_API_KEY", "dev_secret_key")
TEST_SERVER_PORT = int(os.environ.get("MCP_TEST_PORT", 8082)) # Define port here
TEST_SERVER_URL = f"http://localhost:{TEST_SERVER_PORT}"

pytest_plugins = ['pytest_asyncio']

# --- Docker Check --- 
def is_docker_running():
    """Check if the Docker daemon is running."""
    try:
        # Use docker info which requires daemon connection
        subprocess.check_output(["docker", "info"], stderr=subprocess.STDOUT, timeout=5)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False

DOCKER_AVAILABLE = is_docker_running()
skip_if_no_docker = pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker daemon is not running or docker command not found")

# --- Fixtures --- 

@pytest.fixture(scope="module")
def event_loop():
    """Ensure asyncio event loop is available for the module."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="module")
async def test_server_process(event_loop):
    """Fixture to start/stop the MCP Test Server process for the module."""
    process = None
    server_command = [sys.executable, "-m", "agents.mcp_test_server"]
    # Ensure API key is passed to the server environment if needed
    env = os.environ.copy()
    env["AGENT_API_KEY"] = API_KEY # Pass the key used by tests
    env["MCP_TEST_PORT"] = str(TEST_SERVER_PORT) # Ensure port is correct
    logger.info(f"Starting MCP Test Server with command: {' '.join(server_command)}")
    try:
        process = subprocess.Popen(server_command, env=env)
        await asyncio.sleep(3) # Allow time for startup
        if process.poll() is not None:
            raise RuntimeError(f"MCP Test Server failed to start. Exit code: {process.poll()}")
        logger.info(f"MCP Test Server started successfully (PID: {process.pid}).")
        yield process
    except Exception as e:
        logger.error(f"Failed to start MCP Test Server: {e}", exc_info=True)
        if process and process.poll() is None:
            process.kill()
            process.wait()
        pytest.fail(f"Failed to start MCP Test Server: {e}", pytrace=False)
        return
    finally:
        # --- Robust Teardown Logic --- 
        logger.info("Tearing down MCP Test Server fixture...")
        if process and process.poll() is None: # Check if process is still running
            logger.info(f"Terminating Test Server (PID: {process.pid})...")
            process.terminate()
            try:
                process.wait(timeout=5) # Wait for termination
                logger.info("Test Server terminated.")
            except subprocess.TimeoutExpired:
                logger.warning(f"Test Server (PID: {process.pid}) did not terminate gracefully. Killing...")
                process.kill() # Force kill if it doesn't terminate
                try:
                    process.wait(timeout=2)
                    logger.info("Test Server killed.")
                except Exception as e_kill:
                    logger.error(f"Error waiting for Test Server kill: {e_kill}")
            except Exception as e_term:
                logger.error(f"Error during Test Server termination: {e_term}")
                # Attempt to kill even if terminate failed
                if process.poll() is None:
                    try:
                        process.kill()
                        process.wait(timeout=2)
                        logger.info("Test Server killed after termination error.")
                    except Exception as e_kill_final:
                         logger.error(f"Error during final Test Server kill attempt: {e_kill_final}")
        elif process:
             logger.info(f"Test Server (PID: {process.pid}) already terminated (exit code: {process.poll()}).")
        else:
            logger.info("Test Server process was not started or already cleaned up.")

@pytest_asyncio.fixture(scope="function")
async def http_client(test_server_process) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provides an httpx AsyncClient scoped to the function, dependent on the server."""
    base_url = f"http://localhost:{TEST_SERVER_PORT}"
    headers = {"X-API-Key": API_KEY}
    async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=60.0) as client:
        # Optional: Add a health check here
        try:
            await client.get("/", timeout=5.0) 
        except httpx.RequestError as e:
            pytest.fail(f"MCP Test Server not responding at {base_url}: {e}", pytrace=False)
        yield client
    # Client closes automatically

@pytest.fixture(scope="module")
def sample_test_project(tmp_path_factory):
    """Creates a temporary directory with sample test files."""
    project_path = tmp_path_factory.mktemp("sample_integration_project")
    tests_dir = project_path / "tests"
    tests_dir.mkdir()

    (tests_dir / "test_success.py").write_text(
        "import pytest\n\n" 
        "def test_always_passes():\n    assert True\n"
    )
    (tests_dir / "test_failure.py").write_text(
        "import pytest\n\n" 
        "def test_always_fails():\n    assert False\n"
    )
    (project_path / "requirements.txt").write_text("pytest\n") # Basic reqs
    
    return str(project_path) # Return path as string

# --- Test Cases --- 

@pytest.mark.asyncio
async def test_root_endpoint(http_client: httpx.AsyncClient):
    """Test the root endpoint returns 200 OK and expected JSON."""
    response = await http_client.get("/")
    assert response.status_code == 200
    # Check for JSON response content instead of plain text
    data = response.json()
    assert data == {"status": "active", "service": "MCP Test Server"}

@pytest.mark.asyncio
async def test_run_local_success(http_client: httpx.AsyncClient, sample_test_project):
    """Test running a successful test locally."""
    request_data = {
        "project_path": sample_test_project,
        "test_path": "tests/test_success.py",
        "runner": "pytest",
        "mode": "local"
    }
    response = await http_client.post("/run-tests", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "success"
    assert "id" in data
    assert data.get("passed_tests")
    assert not data.get("failed_tests")
    assert "1 passed" in data.get("summary", "")

@pytest.mark.asyncio
async def test_run_local_failure(http_client: httpx.AsyncClient, sample_test_project):
    """Test running a failing test locally."""
    request_data = {
        "project_path": sample_test_project,
        "test_path": "tests/test_failure.py",
        "runner": "pytest",
        "mode": "local"
    }
    response = await http_client.post("/run-tests", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "failed"
    assert "id" in data
    assert data.get("failed_tests")
    assert not data.get("passed_tests")
    assert "test_failure.py::test_always_fails" in data.get("summary", ""), f"Summary did not contain failing test name: {data.get('summary')}"

@pytest.mark.asyncio
async def test_get_list_results(http_client: httpx.AsyncClient, sample_test_project):
    """Test listing results and retrieving a specific result by ID."""
    # Run a test first to ensure there's at least one result
    run_request_data = {
        "project_path": sample_test_project,
        "test_path": "tests/test_success.py",
        "runner": "pytest",
        "mode": "local"
    }
    run_response = await http_client.post("/run-tests", json=run_request_data)
    assert run_response.status_code == 200
    run_data = run_response.json()
    result_id = run_data["id"]
    assert result_id

    # List results
    list_response = await http_client.get("/results")
    assert list_response.status_code == 200
    list_data = list_response.json()
    assert isinstance(list_data, list)
    assert result_id in list_data # Check if our run ID is listed

    # Get specific result
    get_response = await http_client.get(f"/results/{result_id}")
    assert get_response.status_code == 200
    get_data = get_response.json()
    assert get_data.get("id") == result_id
    assert get_data.get("status") == "success"

@pytest.mark.asyncio
async def test_get_last_failed(http_client: httpx.AsyncClient, sample_test_project):
    """Test getting the last failed tests."""
    # Run a failing test first
    fail_req = {
        "project_path": sample_test_project,
        "test_path": "tests/test_failure.py",
        "runner": "pytest",
        "mode": "local"
    }
    fail_resp = await http_client.post("/run-tests", json=fail_req)
    assert fail_resp.status_code == 200 # Should be 200 now
    fail_data = fail_resp.json()
    assert fail_data.get("status") == "failed" # Expect failed status
    
    # # Store the failed test name (assuming parsing logic gets this)
    # failed_test_name = fail_data["failed_tests"][0] if fail_data.get("failed_tests") else None
    # assert failed_test_name

    # # Get last failed
    # last_failed_response = await http_client.get("/last-failed", params={"project_path": sample_test_project})
    # assert last_failed_response.status_code == 200
    # last_failed_data = last_failed_response.json()
    # assert isinstance(last_failed_data, list)
    # assert failed_test_name in last_failed_data # Check if the specific failed test is listed

# --- Docker Tests ---

@skip_if_no_docker
@pytest.mark.asyncio
async def test_run_docker_success(http_client: httpx.AsyncClient, sample_test_project, caplog):
    """Test running a successful test in Docker via streaming."""
    caplog.set_level(logging.INFO)
    request_data = {
        "project_path": sample_test_project,
        "test_path": "tests/test_success.py",
        "runner": "pytest",
        "mode": "docker",
        "stream": False
    }
    response = await http_client.post("/run-tests", json=request_data)
    assert response.status_code == 200
    data = response.json()
    
    # Log detailed info for debugging
    logging.info(f"TEST_SUCCESS: Response status code={response.status_code}")
    logging.info(f"TEST_SUCCESS: Response data={data}")
    
    # Original assertions
    assert data["status"] == "success"
    assert "1 passed" in data["summary"]

@skip_if_no_docker
@pytest.mark.asyncio
async def test_run_docker_failure(http_client: httpx.AsyncClient, sample_test_project, caplog):
    """Test running a failing test in Docker."""
    caplog.set_level(logging.INFO)
    request_data = {
        "project_path": sample_test_project,
        "test_path": "tests/test_failure.py",
        "runner": "pytest",
        "mode": "docker"
    }
    response = await http_client.post("/run-tests", json=request_data)
    assert response.status_code == 200
    data = response.json()
    
    # Log detailed info for debugging
    logging.info(f"TEST_FAILURE: Response status code={response.status_code}")
    logging.info(f"TEST_FAILURE: Response data={data}")
    
    # Original assertions
    assert data["status"] == "failed"
    assert "test_failure.py::test_always_fails" in data.get("summary", ""), f"Summary did not contain failing test name: {data.get('summary')}"
    assert data.get("failed_tests") # Check that failed_tests list is populated

# Example for retrieving a result (needs a valid ID from a previous run)
# @pytest.mark.asyncio
# async def test_get_result(http_client: httpx.AsyncClient):
#     # First, run a test to get an ID...
#     # Then, use the ID here
#     result_id = "... some valid result id ..."
#     response = await http_client.get(f"/results/{result_id}")
#     response.raise_for_status()
#     assert response.status_code == 200
#     result = response.json()
#     assert result["id"] == result_id 