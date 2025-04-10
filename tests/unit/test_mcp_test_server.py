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
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
import shutil

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from agents.mcp_test_server import (
    app, 
    TestExecutionConfig,
    TestResult,
    TestRunner,
    ExecutionMode,
    run_tests_local,
    run_tests_docker,
    last_failed_tests,
    DatabaseManager
)


# Create a test client
client = TestClient(app)


def test_root_endpoint():
    """Test the root endpoint returns a 200 status code"""
    response = client.get("/")
    assert response.status_code == 200
    assert "MCP Test Server" in response.text


@pytest.fixture
def mock_process():
    """Create a mock for asyncio.subprocess.Process to simulate test runs"""
    mock = MagicMock(spec=asyncio.subprocess.Process)
    
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

    # Mock the communicate() method to be async and return bytes
    async def mock_communicate(*args, **kwargs):
        return (stdout_data, stderr_data)

    mock.communicate = mock_communicate
    # Set returncode for the mock process
    mock.returncode = 1 # Simulate failure

    return mock


class MockDockerModule:
    """Mock Docker module for testing"""
    
    class MockContainer:
        def __init__(self, logs_data=None, return_code=1):
            # Allow customizing logs and return code for different test cases
            self.logs_data = logs_data or (
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
            self._return_code = return_code
        
        def logs(self):
            return self.logs_data
        
        def wait(self, timeout=None):
            return {"StatusCode": self._return_code}
        
        def inspect(self):
            return {"State": {"ExitCode": self._return_code}}
        
        def stop(self):
            pass
        
        def remove(self):
            pass
    
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
    return MockDockerModule.MockContainer(return_code=1)

# Fixture providing a MockContainer instance for success
@pytest.fixture
def mock_docker_container_pass():
    success_logs = (
        b"============================= test session starts ==============================\n" 
        b"collected 1 item\n\n" 
        b"test_sample.py::test_passing PASSED\n\n" 
        b"========================= 1 passed in 0.02s =========================\n"
    )
    return MockDockerModule.MockContainer(logs_data=success_logs, return_code=0)


@pytest.mark.asyncio
@patch("agents.mcp_test_server.asyncio.create_subprocess_exec")
async def test_run_tests_endpoint(mock_create_subprocess, mock_process):
    """Test the /run-tests endpoint, mocking asyncio subprocess execution."""
    # Configure the mock for asyncio.create_subprocess_exec to return our mock_process
    mock_create_subprocess.return_value = mock_process

    # No need to mock process_test_output anymore, let the real code run

    test_config = {
        "project_path": "/tmp/test_project",
        "test_path": "tests",
        "runner": TestRunner.PYTEST.value,
        "mode": ExecutionMode.LOCAL.value,
        "max_failures": 1,
        "timeout": 30,
        "max_tokens": 4000
    }

    # Patch os checks as before
    with patch("os.path.isdir", return_value=True), \
         patch("os.path.exists", return_value=True):
        response = client.post("/run-tests", json=test_config)

    assert response.status_code == 200
    result = response.json()

    # Verify the result has expected fields
    assert "id" in result
    assert "status" in result
    assert "summary" in result
    assert "details" in result
    assert "passed_tests" in result
    assert "failed_tests" in result
    assert "skipped_tests" in result

    # Verify the test results based on the mock_process output
    assert result["status"] == "failed" # Should now be correctly determined
    assert len(result["passed_tests"]) > 0
    assert len(result["failed_tests"]) > 0
    assert "test_passing" in result["passed_tests"][0]
    assert "test_failing" in result["failed_tests"][0]


@pytest.mark.asyncio
@patch("agents.mcp_test_server.asyncio.create_subprocess_exec")
async def test_run_tests_local(mock_create_subprocess, mock_process):
    """Test the run_tests_local function directly, mocking subprocess."""
    mock_create_subprocess.return_value = mock_process
    
    mock_db = MagicMock(spec=DatabaseManager)
    mock_db.store_test_result = AsyncMock()

    config = TestExecutionConfig(
        project_path="/tmp/test_project",
        test_path="tests",
        runner=TestRunner.PYTEST,
        max_failures=1
    )
    
    result = await run_tests_local(config, db=mock_db)
    
    assert result.status == "failed"
    assert len(result.passed_tests) > 0
    assert len(result.failed_tests) > 0
    assert "test_passing" in result.passed_tests[0]
    assert "test_failing" in result.failed_tests[0]
    
    mock_db.store_test_result.assert_called_once()


@pytest.mark.asyncio
async def test_run_tests_docker(mock_docker_client, mock_docker_container_fail):
    """Test the run_tests_docker function, mocking docker via sys.modules."""
    
    # 1. Configure the mock client's container run result
    mock_docker_client.containers.run.return_value = mock_docker_container_fail

    # 2. Create a mock 'docker' module
    mock_docker_module = MagicMock()
    # 3. Create a mock 'from_env' function on the mock module
    #    This mock function returns our pre-configured mock_docker_client
    mock_docker_module.from_env = MagicMock(return_value=mock_docker_client)

    # Mock DatabaseManager
    mock_db = MagicMock(spec=DatabaseManager)
    mock_db.store_test_result = AsyncMock()
    
    config = TestExecutionConfig(
        project_path="/tmp/test_project",
        test_path="tests",
        runner=TestRunner.PYTEST,
        mode=ExecutionMode.DOCKER,
        docker_image="python:3.9"
    )
        
    # 4. Patch sys.modules for the duration of the call
    with patch.dict("sys.modules", {"docker": mock_docker_module}):
        # Call the actual function, which will now import the mock 'docker' module
        result = await run_tests_docker(config, db=mock_db)
        
    # Verify the result (based on mock_docker_container_fail)
    assert result.status == "failed"
    assert len(result.passed_tests) > 0
    assert len(result.failed_tests) > 0
    assert "test_passing" in result.passed_tests[0]
    assert "test_failing" in result.failed_tests[0]

    # Check that the mock docker client methods were used as expected
    mock_docker_module.from_env.assert_called_once()
    mock_docker_client.containers.run.assert_called_once()
    # Check that DB was called
    mock_db.store_test_result.assert_called_once()


def test_get_result_endpoint():
    """Test the /results/{result_id} endpoint"""
    # Mock test result with all required fields
    test_result = TestResult(
        id="test-id-789",
        project_path="/tmp/test_project",
        test_path="/tmp/test_project/tests",
        runner="pytest",
        execution_mode="local",
        status="success",
        summary="All tests passed",
        details="Test details here",
        execution_time=0.5,
        passed_tests=["test_one", "test_two"],
        failed_tests=[],
        skipped_tests=[],
        timestamp=123456789.0,
        command="pytest",
        token_count=100
    )
    
    # Patch the get_test_result function to return our mock result
    with patch("agents.mcp_test_server.get_test_result", return_value=test_result):
        response = client.get("/results/test-id-789")
        assert response.status_code == 200
        result = response.json()
        
        # Verify the result
        assert result["id"] == "test-id-789"
        assert result["status"] == "success"
        assert len(result["passed_tests"]) == 2
        assert len(result["failed_tests"]) == 0


def test_get_nonexistent_result():
    """Test getting a result that doesn't exist"""
    # Patch to return None for a non-existent ID
    with patch("agents.mcp_test_server.get_test_result", return_value=None):
        response = client.get("/results/nonexistent-id")
        assert response.status_code == 404


def test_list_results_endpoint():
    """Test the /results endpoint"""
    # Mock result IDs
    result_ids = ["test-1", "test-2", "test-3"]
    
    # Patch the list_test_results function
    with patch("agents.mcp_test_server.list_test_results", return_value=result_ids):
        response = client.get("/results")
        assert response.status_code == 200
        assert response.json() == result_ids


def test_last_failed_endpoint():
    """Test the /last-failed endpoint"""
    # Mock last failed tests
    mock_failed_tests_list = ["test_one.py::test_a", "test_two.py::test_b"]
    expected_response = {"last_failed_tests": mock_failed_tests_list}

    # Properly patch the last_failed_tests variable within the server module
    # We need to patch the actual set used by the endpoint
    with patch.object(sys.modules["agents.mcp_test_server"], "last_failed_tests", set(mock_failed_tests_list)):
        response = client.get("/last-failed")
        assert response.status_code == 200
        # Assert the entire response structure
        assert response.json() == expected_response


def test_run_tests_local_success(sample_project_path):
    """Test running tests locally that should succeed."""
    config = {
        "project_path": sample_project_path,
        "test_path": "test_passing.py",
        "runner": "pytest",
        "mode": "local"
    }
    response = client.post("/run-tests", json=config)
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "passed" # Changed from "success"
    assert "PASSED test_passing.py::test_always_passes" in result["details"]
    assert len(result["failed_tests"]) == 0


def test_run_tests_local_failure(sample_project_path):
    """Test running tests locally that should fail."""
    config = {
        "project_path": sample_project_path,
        "test_path": "test_failing.py",
        "runner": "pytest",
        "mode": "local"
    }
    response = client.post("/run-tests", json=config)
    assert response.status_code == 200 # Endpoint returns 200 even on test failure
    result = response.json()
    assert result["status"] == "failed" # Changed from "failure"
    assert "FAILED test_failing.py::test_always_fails" in result["details"]
    assert len(result["failed_tests"]) > 0


# ... potentially skip Docker tests if Docker isn't available/configured ...
@pytest.mark.skipif(not shutil.which("docker"), reason="Docker not found in PATH")
def test_run_tests_docker_success(sample_project_path):
    """Test running tests in Docker that should succeed."""
    config = {
        "project_path": sample_project_path,
        "test_path": "test_passing.py",
        "runner": "pytest",
        "mode": "docker",
        "docker_image": "python:3.11-slim" # Use a specific slim image
    }
    response = client.post("/run-tests", json=config)
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "passed" # Changed from "success"
    assert "PASSED test_passing.py::test_always_passes" in result["details"]
    assert len(result["failed_tests"]) == 0


@pytest.mark.skipif(not shutil.which("docker"), reason="Docker not found in PATH")
def test_run_tests_docker_failure(sample_project_path):
    """Test running tests in Docker that should fail."""
    config = {
        "project_path": sample_project_path,
        "test_path": "test_failing.py",
        "runner": "pytest",
        "mode": "docker",
        "docker_image": "python:3.11-slim"
    }
    response = client.post("/run-tests", json=config)
    assert response.status_code == 200 # Endpoint returns 200 even on test failure
    result = response.json()
    assert result["status"] == "failed" # Changed from "failure"
    assert "FAILED test_failing.py::test_always_fails" in result["details"]
    assert len(result["failed_tests"]) > 0


def test_run_tests_invalid_path():
    """Test running tests with an invalid project path."""
    config = {
        "project_path": "/nonexistent/path/that/hopefully/doesnt/exist",
        "test_path": "test_failing.py",
        "runner": "pytest",
        "mode": "local"
    }
    response = client.post("/run-tests", json=config)
    # The server should reject this. It might be 400 (explicit check) or 422 (FastAPI validation)
    assert response.status_code in [400, 422]
    # Optionally, check the error detail structure if consistent
    # result = response.json()
    # assert "detail" in result


if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 