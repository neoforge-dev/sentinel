#!/usr/bin/env python3
"""
Unit tests for the MCP Test Server
"""

import sys
import os
import json
import pytest
import pytest_asyncio
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock, call
from fastapi.testclient import TestClient
import shutil
from datetime import datetime
import uvicorn
from httpx import AsyncClient, ASGITransport
import unittest
from starlette.background import BackgroundTasks
import docker # Import the real docker library to check for its exceptions
from enum import Enum
from uuid import uuid4
from typing import AsyncGenerator, List  # Added import
import inspect

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from agents.mcp_test_server import (
    app, 
    ExecutionConfig,
    ResultData,
    RunnerType,
    ExecutionMode,
    run_tests_local,
    DatabaseManager,
    get_db_manager,
    extract_test_results,
    extract_test_summary,
    get_request_db_manager,
    determine_test_status
)

# Add src directory to path so we can import storage modules
# sys.path.append(str(Path(__file__).resolve().parent.parent))
# No longer needed with pytest.ini configuration
from src.storage.database import get_db_manager, DatabaseManager

# Import security dependency
try:
    from src.security import verify_api_key, EXPECTED_API_KEY
except ImportError:
    # Define dummies if import fails
    async def verify_api_key(): pass
    EXPECTED_API_KEY = "dev_secret_key"

# Create a test client
client = TestClient(app)

# Synchronous test client
@pytest.fixture(scope="module")
def fixture_client_sync():
    headers = {"X-API-Key": EXPECTED_API_KEY}
    return TestClient(app, headers=headers)

# Asynchronous test client
@pytest_asyncio.fixture(scope="function")
async def client_async():
    # Use ASGITransport to wrap the FastAPI app for httpx.AsyncClient
    # It seems this test client needs the API key header set implicitly
    headers = {"X-API-Key": EXPECTED_API_KEY}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver", headers=headers) as client:
        yield client

# Keep the synchronous client for synchronous tests
client_sync = TestClient(app)

def test_root_endpoint(fixture_client_sync):
    """Test the root endpoint returns a 200 status code"""
    response = fixture_client_sync.get("/")
    assert response.status_code == 200
    assert "MCP Test Server" in response.text


@pytest.fixture
def mock_process():
    """Create a mock for asyncio.subprocess.Process to simulate test runs"""
    mock = MagicMock(spec=asyncio.subprocess.Process)
    
    # Mock stdout/stderr streams
    mock_stdout = AsyncMock(spec=asyncio.StreamReader)
    mock_stderr = AsyncMock(spec=asyncio.StreamReader)
    
    # Mock stdout/stderr data (as bytes)
    stdout_data = (
        b"============================= test session starts ==============================\n" 
        b"collected 2 items\n\n" 
        b"test_sample.py::test_passing PASSED\n" 
        b"test_sample.py::test_failing FAILED\n\n" 
        b"================================== FAILURES ===================================\n" 
        b"________________________________ test_failing _________________________________\n\n" 
        b"    def test_failing():\n" 
        b">       assert False\nE       assert False\n\n" 
        b"test_sample.py:6: AssertionError\n" 
        b"========================= 1 passed, 1 failed in 0.05s =========================\n"
    )
    stderr_data = b""

    # Configure readline to yield lines and then empty bytes
    # Split the data into lines and add a final empty byte string
    stdout_lines = [line + b'\n' for line in stdout_data.strip().split(b'\n')] + [b'']
    stderr_lines = [line + b'\n' for line in stderr_data.strip().split(b'\n')] + [b'']
    
    mock_stdout.readline = AsyncMock(side_effect=stdout_lines)
    mock_stderr.readline = AsyncMock(side_effect=stderr_lines)
    
    mock.stdout = mock_stdout
    mock.stderr = mock_stderr

    # Mock the communicate() method (less relevant now with streaming)
    async def mock_communicate(*args, **kwargs):
        return (stdout_data, stderr_data)

    mock.communicate = mock_communicate
    # Set returncode for the mock process
    mock.returncode = 1 # Simulate failure
    mock.pid = 12345 # Add pid attribute

    return mock


class MockDockerModule:
    """Mock Docker module for testing"""
    
    class MockContainer:
        def __init__(self, exit_code=0, logs_output=b"", status='exited'):
            self.logs_output = logs_output
            self.exit_code = exit_code
            self._status = status
            self.attrs = {'State': {'ExitCode': self.exit_code}}
            self.short_id = "mock_short_id" # Add attribute

        def attach(self, stream=False, logs=False, stdout=False, stderr=False):
            if stream and logs:
                # Simulate a stream of bytes
                def log_stream():
                    if isinstance(self.logs_output, bytes):
                         yield self.logs_output
                    elif isinstance(self.logs_output, list): # Allow list of byte strings
                         for line in self.logs_output:
                              yield line
                return log_stream()
            return self.logs_output # Return raw bytes if not streaming logs

        def wait(self, timeout=None):
            # Simulate waiting for container exit
            return {'StatusCode': self.exit_code}
        
        def reload(self): # Add mock reload
            pass # No state change needed for this mock
            
        def stop(self, timeout=None): # Add mock stop
            self._status = 'exited'
            
        def remove(self, v=False, force=False): # Add mock remove
            pass
            
        @property
        def status(self): # Make status a property
             return self._status

        # Added mock logs method
        def logs(self, stdout=True, stderr=True, stream=False, follow=False):
            if stream:
                async def stream_generator():
                    yield self.logs_output
                return stream_generator()
            else:
                return self.logs_output
    
    class MockClient:
        def __init__(self):
            self.containers = MagicMock()
            # Default mock container for the client
            self.containers.run.return_value = MockDockerModule.MockContainer()
        
        # Keep from_env here conceptually, though we patch it directly in the test
        def from_env(self):
            return self

# Fixture providing the MockClient instance
@pytest.fixture
def mock_docker_client():
    return MockDockerModule.MockClient()

# Fixture providing a default MockContainer instance (for failure)
@pytest.fixture
def mock_docker_container_fail():
    # Example: Simulate pytest output with one failure
    output_lines = [
        b"============================= test session starts ==============================",
        b"collected 1 item",
        b"",
        b"test_example.py F                                                       [100%]",
        b"",
        b"=================================== FAILURES ===================================",
        b"_________________________________ test_failure _________________________________",
        b"",
        b"    def test_failure():",
        b">       assert False",
        b"E       AssertionError: assert False",
        b"",
        b"test_example.py:2: AssertionError",
        b"=========================== short test summary info ============================",
        b"FAILED test_example.py::test_failure - AssertionError: assert False",
        b"============================== 1 failed in 0.01s ==============================="
    ]
    return MockDockerModule.MockContainer(exit_code=1, logs_output=output_lines)

@pytest.fixture
def mock_docker_container_pass():
    success_logs = (
        b"============================= test session starts ==============================\n" 
        b"collected 1 item\n\n" 
        b"test_sample.py::test_passing PASSED\n\n" 
        b"========================= 1 passed in 0.02s =========================\n"
    )
    return MockDockerModule.MockContainer(logs_output=success_logs, exit_code=0)


# Note: Re-added async def, uses async client
@pytest.mark.asyncio
async def test_run_tests_endpoint(client_async):
    """Test the /run-tests endpoint in Docker mode."""
    # Mock setup removed as it causes 400 regardless

    test_config = {
        "project_path": "/tmp/test_project",
        "test_path": "tests",
        "runner": RunnerType.PYTEST.value,
        "mode": ExecutionMode.DOCKER.value,
        "docker_image": "python:3.11-slim",
        "max_failures": 1,
        "timeout": 30,
        "max_tokens": 4000
    }

    # Use await with the async client
    # Mock the actual test execution function (run_tests_docker or run_tests_local)
    # to avoid external dependencies during this endpoint test.
    with patch("agents.mcp_test_server.run_tests_local", new_callable=AsyncMock) as mock_run_local:
        # Configure the mock to return a valid ResultData object for non-streaming
        mock_result = ResultData(
            id="test-id", project_path=test_config["project_path"], test_path=test_config["test_path"],
            runner=test_config["runner"], execution_mode=test_config["mode"], status="Passed",
            summary="Mock Pass", details="Mock Details", execution_time=1.0
        )
        mock_run_local.return_value = mock_result

        response = await client_async.post("/run-tests", json=test_config)

        # Check response code (assuming local fallback or future Docker impl)
        # If Docker were strictly required and not implemented, expect 501
        # If fallback to local is allowed (current state), expect 200
        assert response.status_code == 200

        # Verify the underlying function was called
        # Adjust the expected call based on actual logic (local fallback?)
        mock_run_local.assert_awaited_once()
        # Check the config passed to the function
        call_args, call_kwargs = mock_run_local.call_args
        passed_config = call_kwargs.get('config')
        assert passed_config is not None
        assert passed_config.project_path == test_config["project_path"]
        assert passed_config.mode == ExecutionMode.DOCKER # Even if falling back, config retains original mode


@patch("agents.mcp_test_server.asyncio.create_subprocess_exec")
async def test_run_tests_local(mock_create_subprocess, mock_process):
    """Test the run_tests_local function directly for Config Error."""
    # Dont mock subprocess creation, let the function check the path
    # mock_create_subprocess.side_effect = FileNotFoundError("[Mock] Python executable not found") 

    mock_db = MagicMock(spec=DatabaseManager)
    mock_db.store_test_result = AsyncMock()

    # Use a non-existent path to trigger the config error
    non_existent_path = "/path/that/does/not/exist/ever"
    config = ExecutionConfig(
        project_path=non_existent_path, 
        test_path="tests",
        runner=RunnerType.PYTEST,
        max_failures=1,
    )

    result = await run_tests_local(config, db=mock_db)

    assert result.status == "Config Error"
    assert f"Project path '{non_existent_path}' is not a valid directory." in result.details
    mock_db.store_test_result.assert_awaited_once() # DB should be called to store Config Error


@pytest.mark.asyncio
async def test_run_tests_docker(mock_docker_client, mock_docker_container_fail):
    """Test the run_tests_docker function directly, mocking Docker client."""
    mock_docker_client.containers.run.return_value = mock_docker_container_fail

    mock_db = MagicMock(spec=DatabaseManager)
    mock_db.store_test_result = AsyncMock()

    config = ExecutionConfig(
        project_path="/tmp/test_project",
        test_path="tests/test_fail.py",
        runner=RunnerType.PYTEST,
        mode=ExecutionMode.DOCKER
    )

    # Consume the async generator to get the final result
    result_data = None
    # stream_generator = await run_tests_docker(config, db=mock_db) # Original call causing NameError
    # # The rest of this test is now invalid as run_tests_docker doesn't exist
    # # Keeping the structure commented out for reference if needed later
    # try:
    #     async for chunk in stream_generator:
    #         # In non-streaming mode, the generator yields the final ResultData once
    #         if isinstance(chunk, ResultData):
    #             result_data = chunk
    #             break # Should only yield one item in this non-streaming test case
    #         # Handle unexpected streaming chunks if necessary for debugging
    #         # else: print(f"Unexpected chunk: {chunk}") 
    #     # Ensure generator is fully exhausted even if no ResultData was yielded (error case)
    #     async for _ in stream_generator: 
    #         pass
    # except Exception as e:
    #     pytest.fail(f"Consuming run_tests_docker generator failed: {e}")

    # # Check that the function returns a ResultData object, not a generator
    # assert isinstance(result_data, ResultData), f"Expected ResultData, got {type(result_data)}"
    # assert result_data.status == "Failed" # Based on mock_docker_container_fail
    # mock_db.store_test_result.assert_awaited_once()
    pytest.skip("Skipping test for removed run_tests_docker function.") # Skip the test instead of removing


# Fixture for overriding DB dependency
@pytest.fixture
def mock_db_manager():
    mock = MagicMock(spec=DatabaseManager)
    # Configure async methods if needed
    mock.get_test_result = AsyncMock(return_value=None) 
    mock.store_test_result = AsyncMock()
    mock.list_test_results = AsyncMock(return_value=[])
    mock.get_last_failed_tests = AsyncMock(return_value=[])
    return mock

@pytest.fixture()
def override_get_db_manager(mock_db_manager):
    """Fixture to manage overriding the DB manager dependency."""
    async def _override_get_db():
        # This needs to be an async generator if the original dependency is
        # If get_request_db_manager is just `Depends(get_db_manager)`,
        # and get_db_manager returns the instance, this override is simpler.
        # Let's assume get_request_db_manager = Depends(get_db_manager)
        # and get_db_manager returns the singleton instance.
        # We need to ensure our mock is returned when get_db_manager is accessed.
        # The structure depends heavily on how get_request_db_manager is defined.
        # Assuming a simple return for now. Check `get_request_db_manager` definition if issues persist.
        # UPDATE: Based on mcp_code_server, get_request_db_manager is likely just Depends(get_db_manager).
        # Let's mock the singleton `get_db_manager` function instead.
        # This requires careful patching.

        # ---- Alternative: Patching the source function ----
        # This approach patches the function where it's defined/imported.
        # Requires knowing the exact import path used within mcp_test_server.
        # Example patch path (adjust based on actual imports):
        # with patch("agents.mcp_test_server.get_db_manager", return_value=mock_db_manager):
        #     yield # Test runs with the patch

        # ---- Alternative: Using FastAPI Dependency Overrides ----
        # This is generally cleaner for FastAPI apps.
        original_overrides = app.dependency_overrides.copy()
        # Override the dependency *function* that FastAPI uses
        # Check if get_request_db_manager is the correct key
        app.dependency_overrides[get_request_db_manager] = lambda: mock_db_manager
        yield
        app.dependency_overrides = original_overrides # Restore

    # The fixture yields control while the override is active
    yield from _override_get_db()


@pytest.mark.asyncio
async def test_get_result_endpoint(client_async: AsyncClient, mock_db_manager, api_key_override):
    """Test GET /results/{result_id} endpoint."""
    # Apply overrides explicitly for this test
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[verify_api_key] = api_key_override
    app.dependency_overrides[get_request_db_manager] = lambda: mock_db_manager # Use the provided mock

    try:
        # Configure the mock DB manager for this specific test
        test_id = "test-id-789"
        mock_result_data = {
            "id": test_id, "project_path": "/path/project", "test_path": "tests",
            "runner": "pytest", "execution_mode": "local", "status": "success",
            "summary": "All passed", "details": "Ran 5 tests", "passed_tests": ["t1", "t2"],
            "failed_tests": [], "skipped_tests": [], "execution_time": 1.23,
            "created_at": datetime.now().isoformat()
        }
        mock_db_manager.get_test_result = AsyncMock(return_value=mock_result_data)
        
        response = await client_async.get(f"/results/{test_id}") # Use client_async

        # Assertions
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["id"] == test_id
        assert response_data["status"] == "success"
        
        # Verify DB method was called
        mock_db_manager.get_test_result.assert_awaited_once_with(test_id)
    finally:
        # Clean up the override
        app.dependency_overrides = original_overrides

@pytest.mark.asyncio
async def test_get_result_endpoint_not_found(client_async: AsyncClient, mock_db_manager, api_key_override):
    """Test GET /results/{result_id} when result not found."""
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[verify_api_key] = api_key_override
    app.dependency_overrides[get_request_db_manager] = lambda: mock_db_manager

    try:
        test_id = "non-existent-id"
        mock_db_manager.get_test_result = AsyncMock(return_value=None) # Simulate not found
        
        response = await client_async.get(f"/results/{test_id}") # Use client_async

        # Assertions
        assert response.status_code == 404
        mock_db_manager.get_test_result.assert_awaited_once_with(test_id)
    finally:
        # Clean up the override
        app.dependency_overrides = original_overrides

@pytest.mark.asyncio
async def test_list_results_endpoint(client_async: AsyncClient, mock_db_manager, api_key_override):
    """Test GET /results endpoint."""
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[verify_api_key] = api_key_override
    app.dependency_overrides[get_request_db_manager] = lambda: mock_db_manager

    try:
        # Configure mock DB to return list of dicts matching ResultData structure
        mock_results_from_db = [
            {
                "id": "id1", "project_path": "/p1", "test_path": "t1", "runner": "pytest", "execution_mode": "local",
                "status": "passed", "summary": "...", "details": "...", "passed_tests": [], "failed_tests": [], "skipped_tests": [],
                "execution_time": 1.0, "created_at": datetime.now()
            },
            {
                "id": "id2", "project_path": "/p2", "test_path": "t2", "runner": "unittest", "execution_mode": "docker",
                "status": "failed", "summary": "...", "details": "...", "passed_tests": [], "failed_tests": [], "skipped_tests": [],
                "execution_time": 2.0, "created_at": datetime.now()
            }
        ]
        # Convert datetime objects to ISO strings for JSON serialization compatibility
        mock_results_json_compatible = [
            {k: v.isoformat() if isinstance(v, datetime) else v for k, v in res.items()}
            for res in mock_results_from_db
        ]

        mock_db_manager.list_test_results = AsyncMock(return_value=mock_results_from_db) # Mock returns dicts

        response = await client_async.get("/results") # Use client_async

        assert response.status_code == 200
        mock_db_manager.list_test_results.assert_awaited_once()
        
        # Endpoint returns full ResultData objects (validate Pydantic model implicitly)
        response_data = response.json()
        assert isinstance(response_data, list)
        assert len(response_data) == 2
        assert response_data == mock_results_json_compatible # Compare with JSON-compatible version
        
        # Check a few fields from the first result
        assert response_data[0]["id"] == "id1"
        assert response_data[0]["status"] == "passed"
        assert response_data[0]["project_path"] == "/p1"

    finally:
        # Clean up override
        app.dependency_overrides = original_overrides

@pytest.mark.asyncio
async def test_last_failed_endpoint(client_async: AsyncClient, mock_db_manager, api_key_override):
    """Test GET /last-failed endpoint."""
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[verify_api_key] = api_key_override
    app.dependency_overrides[get_request_db_manager] = lambda: mock_db_manager
    
    try:
        # Configure mock DB
        mock_failed = ["test_a.py::test_fail1", "test_b.py::test_fail2"]
        project_path = "/path/to/project"
        mock_db_manager.get_last_failed_tests = AsyncMock(return_value=mock_failed)
        
        # Add required query parameter
        response = await client_async.get("/last-failed", params={"project_path": project_path}) # Use client_async

        # Assertions
        assert response.status_code == 200
        mock_db_manager.get_last_failed_tests.assert_awaited_once_with(project_path)
        assert response.json() == mock_failed
    finally:
        # Clean up override
        app.dependency_overrides = original_overrides

@pytest.mark.asyncio
async def test_last_failed_endpoint_missing_param(client_async: AsyncClient, api_key_override):
    """Test GET /last-failed endpoint without required parameter."""
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[verify_api_key] = api_key_override
    try:
        response = await client_async.get("/last-failed") # Use client_async
        assert response.status_code == 422 # Unprocessable Entity
    finally:
        app.dependency_overrides = original_overrides

# Synchronous tests need the override applied differently if they call endpoints
def test_run_tests_local_success_sync(sample_project_path, fixture_client_sync, api_key_override):
    """Test running tests locally that should succeed."""
    # Synchronous tests using fixture_client_sync which already has the key
    # If they needed other overrides, it would be trickier
    config = {
        "project_path": str(sample_project_path),
        "test_path": "test_passing.py",
        "runner": "pytest",
        "mode": "local"
    }
    # No need to manually apply api_key_override here, fixture_client_sync handles it
    response = fixture_client_sync.post("/run-tests", json=config)
    assert response.status_code == 200

def test_run_tests_local_failure_sync(sample_project_path, fixture_client_sync, api_key_override):
    """Test running tests locally that should fail."""
    config = {
        "project_path": str(sample_project_path),
        "test_path": "test_failing.py",
        "runner": "pytest",
        "mode": "local"
    }
    response = fixture_client_sync.post("/run-tests", json=config)
    assert response.status_code == 200

def test_run_tests_invalid_path_sync(fixture_client_sync, api_key_override):
    """Test running tests with an invalid project path."""
    config = {
        "project_path": "/nonexistent/path/that/hopefully/doesnt/exist",
        "test_path": "test_failing.py",
        "runner": "pytest",
        "mode": "local"
    }
    response = fixture_client_sync.post("/run-tests", json=config)
    # assert response.status_code in [400, 422] # Original assertion
    # The endpoint now returns 200 OK, with the error captured in ResultData
    assert response.status_code == 200 
    response_data = response.json()
    assert response_data["status"] == "Config Error"
    assert "not a valid directory" in response_data["details"]

@pytest.mark.asyncio
async def test_run_tests_streaming_local(client_async, mock_db_manager, sample_project_path, api_key_override):
    """Test the /run-tests endpoint with local mode for streaming response."""
    # Apply overrides manually for this test
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[verify_api_key] = api_key_override
    app.dependency_overrides[get_request_db_manager] = lambda: mock_db_manager
    # DB override handled by fixture

    try:
        config = {
            "project_path": str(sample_project_path),
            "test_path": "test_passing.py",
            "runner": "pytest",
            "mode": "local",
            "stream_output": True
        }

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock(spec=asyncio.subprocess.Process)
            mock_stdout_stream = AsyncMock(spec=asyncio.StreamReader)
            mock_stderr_stream = AsyncMock(spec=asyncio.StreamReader)
    
            # Define the lines to be returned by the mock streams
            stdout_lines = [
                b"collected 1 item\n", b"STDOUT: line 1\n",
                b"STDOUT: PASSED test_case_1\n", b"STDOUT: final line\n",
                b"=== 1 passed in 0.01s ===\n",
                b"" # Add EOF marker directly
            ]
            stderr_lines = [
                b"STDERR: warning\n",
                b"" # Add EOF marker directly
            ]
    
            # Configure readline side_effect with the final EOF marker
            mock_stdout_stream.readline.side_effect = stdout_lines
            mock_stderr_stream.readline.side_effect = stderr_lines
    
            mock_process.stdout = mock_stdout_stream
            mock_process.stderr = mock_stderr_stream
            mock_process.wait = AsyncMock(return_value=0)
            mock_process.pid = 12345
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            with patch("agents.mcp_test_server.extract_test_results") as mock_extract_results, \
                 patch("agents.mcp_test_server.extract_test_summary") as mock_extract_summary:
                
                mock_extract_results.return_value = {"passed": ["test_case_1"], "failed": [], "skipped": []}
                mock_extract_summary.return_value = "1 passed, 0 failed in 0.01s"
                mock_db_manager.store_test_result = AsyncMock(return_value = None) # Ensure DB mock is AsyncMock

                response = await client_async.post("/run-tests", json=config)

                assert response.status_code == 200
                assert response.headers["content-type"] == "text/plain; charset=utf-8"

                stream_content = await response.aread()
                assert b"collected 1 item" in stream_content
                assert b"STDOUT: PASSED test_case_1" in stream_content
                assert b"STDERR: warning" in stream_content
                assert b"=== 1 passed in 0.01s ===" in stream_content

                mock_exec.assert_called_once()
                cmd_args = mock_exec.call_args[0]
                assert "test_passing.py" in " ".join(cmd_args)
                assert "stream" not in " ".join(cmd_args)
                mock_db_manager.store_test_result.assert_awaited_once()
    finally:
        app.dependency_overrides = original_overrides

# ... (other pytest-style tests)

# --- Authentication Tests ---

def test_missing_api_key(): # Use raw client
    """Test request without API key header fails with 401."""
    raw_client = TestClient(app)
    test_config = {"project_path": "/", "test_path": "t"}
    response = raw_client.post("/run-tests", json=test_config)
    assert response.status_code == 401
    assert "missing api key" in response.json()["detail"].lower()

def test_invalid_api_key(fixture_client_sync): # Corrected: client -> fixture_client_sync
    """Test endpoint access with an invalid API key."""
    # Test accessing a protected endpoint (e.g., /results)
    response = fixture_client_sync.get("/results", headers={"X-API-Key": "invalid-key"})
    assert response.status_code == 403  # Should be Forbidden

@pytest.mark.asyncio
async def test_async_missing_api_key(): # Use raw client
    """Test async request without API key header fails with 401."""
    test_config = {"project_path": "/", "test_path": "t"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as raw_client:
        response = await raw_client.get("/results")
    assert response.status_code == 401 # Unauthorized

@pytest.mark.asyncio
async def test_async_invalid_api_key(client_async): # Corrected: async_client -> client_async
    """Test async endpoint access with an invalid API key."""
    # Test accessing a protected endpoint asynchronously
    # Need to use a client *without* the valid key. Create raw client.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as raw_client:
        response = await raw_client.get("/results", headers={"X-API-Key": "invalid-key"})
    assert response.status_code == 403 # Should be Forbidden


@pytest.fixture
def temp_db_override():
    """Fixture to temporarily override DB dependencies with a specific mock."""
    mock_db = MagicMock(spec=DatabaseManager)
    # Provide complete mock data matching ResultData schema
    mock_results_data = [
        {
            "id": "res1",
            "project_path": "/path/to/proj1",
            "test_path": "tests/test_1.py",
            "runner": RunnerType.PYTEST.value,
            "execution_mode": ExecutionMode.LOCAL.value,
            "status": "Passed",
            "summary": "All tests passed.",
            "details": "... details ...",
            "passed_tests": ["test_a"],
            "failed_tests": [],
            "skipped_tests": [],
            "execution_time": 1.23,
            "created_at": datetime.now() # Will be converted to isoformat in test
        }
    ]
    mock_db.list_test_results = AsyncMock(return_value=mock_results_data)
    
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db_manager] = lambda: mock_db
    app.dependency_overrides[get_request_db_manager] = lambda: mock_db
    yield mock_db # Provide the mock to the test if needed
    # Teardown: Restore original overrides
    app.dependency_overrides = original_overrides

# Test list results with auth (using raw clients)
@pytest.mark.asyncio
async def test_list_results_auth(temp_db_override): # Use the fixture
    """Test authentication for the /results endpoint using a real DB."""
    # Create a new client for this test to control headers precisely
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        
        # Test with valid key
        headers_good = {"X-API-Key": EXPECTED_API_KEY}
        response_good_key = await client.get("/results", headers=headers_good)
        assert response_good_key.status_code == 200
        # Verify the response data structure against the mock data (check length and ID)
        response_data = response_good_key.json()
        assert isinstance(response_data, list)
        # The mock now returns one complete result
        assert len(response_data) == 1 
        assert response_data[0]['id'] == "res1" # Check ID of the mock result

        # Test with invalid key
        headers_bad = {"X-API-Key": "invalid-key"}
        response_bad_key = await client.get("/results", headers=headers_bad)
        assert response_bad_key.status_code == 403 # Expect Forbidden

        # Test without key
        response_no_key = await client.get("/results")
        assert response_no_key.status_code == 401 # Expect Unauthorized
        # Check detail for 401 - should match the security dependency's message
        assert "Missing API Key" in response_no_key.json()["detail"]

    # Verify the mock DB method was called for the successful request
    temp_db_override.list_test_results.assert_awaited_once()

# Mock filesystem structure fixture
@pytest.fixture(scope="session")
def sample_project_path(tmp_path_factory):
    base_path = tmp_path_factory.mktemp("sample_project_session")
    # Create dummy test files
    (base_path / "test_passing.py").write_text("def test_passes(): assert True")
    (base_path / "test_failing.py").write_text("def test_fails(): assert False")
    (base_path / "__init__.py").touch() # Ensure it's treated as a package if needed
    return base_path

@pytest.fixture()
def api_key_override():
    """Provides an override function for verify_api_key."""
    async def _override_verify():
        return "test_key"
    yield _override_verify # Yield the function itself
    # No teardown needed as the override is applied/removed by the test

# Override verify_api_key dependency for most tests
# This fixture is no longer needed as tests will use api_key_override
# @pytest.fixture()
# def override_verify_api_key_dependency(monkeypatch):
#     """Override the verify_api_key dependency for most tests."""
#     async def _override_verify():
#         # Simple override that always passes
#         return "test_key"
#     original_overrides = app.dependency_overrides.copy()
#     app.dependency_overrides[verify_api_key] = _override_verify
#     yield
#     app.dependency_overrides = original_overrides

# --- Streaming Test ---

@pytest.mark.asyncio
async def test_run_tests_streaming_local(client_async, mock_db_manager, sample_project_path, api_key_override):
    """Test the /run-tests endpoint with local mode for streaming response."""
    # Apply overrides manually for this test
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[verify_api_key] = api_key_override
    app.dependency_overrides[get_request_db_manager] = lambda: mock_db_manager
    # DB override handled by fixture

    try:
        config = {
            "project_path": str(sample_project_path),
            "test_path": "test_passing.py",
            "runner": "pytest",
            "mode": "local",
            "stream_output": True
        }

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock(spec=asyncio.subprocess.Process)
            mock_stdout_stream = AsyncMock(spec=asyncio.StreamReader)
            mock_stderr_stream = AsyncMock(spec=asyncio.StreamReader)
    
            # Define the lines to be returned by the mock streams
            stdout_lines = [
                b"collected 1 item\n", b"STDOUT: line 1\n",
                b"STDOUT: PASSED test_case_1\n", b"STDOUT: final line\n",
                b"=== 1 passed in 0.01s ===\n",
                b"" # Add EOF marker directly
            ]
            stderr_lines = [
                b"STDERR: warning\n",
                b"" # Add EOF marker directly
            ]
    
            # Configure readline side_effect with the final EOF marker
            mock_stdout_stream.readline.side_effect = stdout_lines
            mock_stderr_stream.readline.side_effect = stderr_lines
    
            mock_process.stdout = mock_stdout_stream
            mock_process.stderr = mock_stderr_stream
            mock_process.wait = AsyncMock(return_value=0)
            mock_process.pid = 12345
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            with patch("agents.mcp_test_server.extract_test_results") as mock_extract_results, \
                 patch("agents.mcp_test_server.extract_test_summary") as mock_extract_summary:
                
                mock_extract_results.return_value = {"passed": ["test_case_1"], "failed": [], "skipped": []}
                mock_extract_summary.return_value = "1 passed, 0 failed in 0.01s"
                mock_db_manager.store_test_result = AsyncMock(return_value = None) # Ensure DB mock is AsyncMock

                response = await client_async.post("/run-tests", json=config)

                assert response.status_code == 200
                assert response.headers["content-type"] == "text/plain; charset=utf-8"

                stream_content = await response.aread()
                assert b"collected 1 item" in stream_content
                assert b"STDOUT: PASSED test_case_1" in stream_content
                assert b"STDERR: warning" in stream_content
                assert b"=== 1 passed in 0.01s ===" in stream_content

                mock_exec.assert_called_once()
                cmd_args = mock_exec.call_args[0]
                assert "test_passing.py" in " ".join(cmd_args)
                assert "stream" not in " ".join(cmd_args)
                mock_db_manager.store_test_result.assert_awaited_once()
    finally:
        app.dependency_overrides = original_overrides


# Helper function to create sample output
def create_sample_output(runner: RunnerType, status: str) -> str:
    if runner == RunnerType.PYTEST:
        if status == "success":
            return (
                b"============================= test session starts ==============================\n"
                b"collected 1 item\n\n"
                b"test_sample.py::test_passing PASSED [100%]\n\n"
                b"========================= 1 passed in 0.02s =========================\n"
            ).decode('utf-8')
        else: # failure
            return (
                b"============================= test session starts ==============================\n"
                b"collected 2 items\n\n"
                b"test_sample.py::test_passing PASSED [ 50%]\n"
                b"test_sample.py::test_failing FAILED [100%]\n\n"
                b"================================== FAILURES ===================================\n"
                b"________________________________ test_failing _________________________________\n\n"
                b"    def test_failing():\n"
                b">       assert False\nE       assert False\n\n"
                b"test_sample.py:6: AssertionError\n"
                b"========================= 1 passed, 1 failed in 0.05s =========================\n"
            ).decode('utf-8')
    elif runner in [RunnerType.UNITTEST, RunnerType.NOSE2]:
        if status == "success":
            return (
                "test_passing (test_module.TestClass) ... ok\n"
                "test_another (test_module.TestClass) ... ok\n"
                "----------------------------------------------------------------------\n"
                "Ran 2 tests in 0.001s\n\n"
                "OK\n"
            )
        else: # failure
            return (
                "test_passing (test_module.TestClass) ... ok\n"
                "test_failing (test_module.TestClass) ... FAIL\n"
                "test_error (test_module.TestClass) ... ERROR\n"
                "test_skipped (test_module.TestClass) ... SKIP 'reason'\n"
                "======================================================================\n"
                "FAIL: test_failing (test_module.TestClass)\n"
                "----------------------------------------------------------------------\n"
                "Traceback (most recent call last):\n"
                "  File \"test_module.py\", line 10, in test_failing\n"
                "    self.assertTrue(False)\n"
                "AssertionError: False is not true\n"
                "======================================================================\n"
                "ERROR: test_error (test_module.TestClass)\n"
                "----------------------------------------------------------------------\n"
                "Traceback (most recent call last):\n"
                "  File \"test_module.py\", line 15, in test_error\n"
                "    raise ValueError(\"Something went wrong\")\n"
                "ValueError: Something went wrong\n"
                "----------------------------------------------------------------------\n"
                "Ran 4 tests in 0.003s\n\n"
                "FAILED (failures=1, errors=1, skipped=1)\n"
             )
    return "" # Default empty

# --- Tests for Parsing Logic --- 

def test_extract_test_results_pytest_success():
    output = create_sample_output(RunnerType.PYTEST, "success")
    results = extract_test_results(output, RunnerType.PYTEST)
    assert results["passed"] == ["test_sample.py::test_passing"]
    assert results["failed"] == []
    assert results["skipped"] == []

def test_extract_test_results_pytest_failure():
    output = create_sample_output(RunnerType.PYTEST, "failure")
    results = extract_test_results(output, RunnerType.PYTEST)
    assert results["passed"] == ["test_sample.py::test_passing"]
    assert results["failed"] == ["test_sample.py::test_failing"]
    assert results["skipped"] == []

def test_extract_test_results_unittest_nose2_success():
    output = create_sample_output(RunnerType.NOSE2, "success")
    results = extract_test_results(output, RunnerType.NOSE2)
    assert results["passed"] == ["test_module.TestClass.test_passing", "test_module.TestClass.test_another"]
    assert results["failed"] == []
    assert results["skipped"] == []

def test_extract_test_results_unittest_nose2_failure():
    output = create_sample_output(RunnerType.UNITTEST, "failure")
    results = extract_test_results(output, RunnerType.UNITTEST)
    assert results["passed"] == ["test_module.TestClass.test_passing"]
    # Errors are currently grouped with failures by the parser
    assert results["failed"] == ["test_module.TestClass.test_failing", "test_module.TestClass.test_error"]
    assert results["skipped"] == ["test_module.TestClass.test_skipped"]

def test_extract_test_summary_pytest_success():
    output = create_sample_output(RunnerType.PYTEST, "success")
    summary = extract_test_summary(output, RunnerType.PYTEST)
    assert "1 passed in" in summary
    assert "FAILURES" not in summary

def test_extract_test_summary_pytest_failure():
    output = create_sample_output(RunnerType.PYTEST, "failure")
    summary = extract_test_summary(output, RunnerType.PYTEST)
    # It currently extracts the summary line rather than the whole failure block
    assert "failed" in summary.lower()
    assert "passed" in summary.lower() or "1 failed" in summary.lower()
    # The current implementation focuses on the summary line, not the details

def test_extract_test_summary_unittest_nose2_success():
    output = create_sample_output(RunnerType.NOSE2, "success")
    summary = extract_test_summary(output, RunnerType.NOSE2)
    assert summary.startswith("Ran 2 tests")
    assert summary.endswith("OK")

def test_extract_test_summary_unittest_nose2_failure():
    output = create_sample_output(RunnerType.UNITTEST, "failure")
    summary = extract_test_summary(output, RunnerType.UNITTEST)
    assert summary.startswith("Ran 4 tests")
    assert summary.endswith("FAILED (failures=1, errors=1, skipped=1)")


if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 