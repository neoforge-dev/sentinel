#!/usr/bin/env python3
"""
Unit tests for the MCP Test Server
"""

import sys
import os
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from agents.mcp_test_server import (
    app, 
    TestExecutionConfig,
    TestResult,
    TestRunner,
    ExecutionMode,
    run_tests_locally,
    run_tests_in_docker
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
    """Create a mock for the subprocess.Popen to simulate test runs"""
    mock = MagicMock()
    mock.communicate.return_value = (
        b"============================= test session starts ==============================\n"
        b"collected 2 items\n\n"
        b"test_sample.py::test_passing PASSED\n"
        b"test_sample.py::test_failing FAILED\n\n"
        b"================================== FAILURES ===================================\n"
        b"________________________________ test_failing _________________________________\n\n"
        b"    def test_failing():\n"
        b">       assert False\nE       assert False\n\n"
        b"test_sample.py:6: AssertionError\n"
        b"========================= 1 passed, 1 failed in 0.05s =========================\n",
        b""
    )
    mock.returncode = 1
    return mock


@patch("agents.mcp_test_server.subprocess.Popen")
@patch("agents.mcp_test_server.store_test_result")
def test_run_tests_endpoint(mock_store, mock_popen, mock_process):
    """Test the /run-tests endpoint"""
    mock_popen.return_value = mock_process
    mock_store.return_value = "test-id-123"
    
    test_config = {
        "project_path": "/tmp/test_project",
        "test_path": "tests",
        "runner": TestRunner.PYTEST,
        "mode": ExecutionMode.LOCAL,
        "max_failures": 1,
        "timeout": 30,
        "max_tokens": 4000
    }
    
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
    
    # Verify the test results
    assert result["id"] == "test-id-123"
    assert result["status"] == "failure"  # Because we mocked a failing test
    assert len(result["passed_tests"]) == 1
    assert len(result["failed_tests"]) == 1
    assert "test_passing" in result["passed_tests"][0]
    assert "test_failing" in result["failed_tests"][0]


@patch("agents.mcp_test_server.subprocess.Popen")
@patch("agents.mcp_test_server.store_test_result")
def test_run_tests_locally(mock_store, mock_popen, mock_process):
    """Test the run_tests_locally function"""
    mock_popen.return_value = mock_process
    mock_store.return_value = "test-id-123"
    
    config = TestExecutionConfig(
        project_path="/tmp/test_project",
        test_path="tests",
        runner=TestRunner.PYTEST,
        max_failures=1
    )
    
    result = run_tests_locally(config)
    
    # Verify the result
    assert result.status == "failure"  # Because we mocked a failing test
    assert len(result.passed_tests) == 1
    assert len(result.failed_tests) == 1
    assert "test_passing" in result.passed_tests[0]
    assert "test_failing" in result.failed_tests[0]


@patch("agents.mcp_test_server.docker.from_env")
@patch("agents.mcp_test_server.store_test_result")
def test_run_tests_in_docker(mock_store, mock_docker):
    """Test the run_tests_in_docker function"""
    # Mock the Docker container
    mock_container = MagicMock()
    mock_container.logs.return_value = (
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
    mock_container.wait.return_value = {"StatusCode": 1}
    
    # Mock the Docker client
    mock_client = MagicMock()
    mock_client.containers.run.return_value = mock_container
    mock_docker.return_value = mock_client
    
    # Mock the store function
    mock_store.return_value = "test-id-456"
    
    config = TestExecutionConfig(
        project_path="/tmp/test_project",
        test_path="tests",
        runner=TestRunner.PYTEST,
        mode=ExecutionMode.DOCKER,
        docker_image="python:3.9"
    )
    
    result = run_tests_in_docker(config)
    
    # Verify the result
    assert result.status == "failure"  # Because we mocked a failing test
    assert len(result.passed_tests) == 1
    assert len(result.failed_tests) == 1
    assert "test_passing" in result.passed_tests[0]
    assert "test_failing" in result.failed_tests[0]


def test_get_result_endpoint():
    """Test the /results/{result_id} endpoint"""
    # Mock test result
    test_result = TestResult(
        id="test-id-789",
        status="success",
        summary="All tests passed",
        details="Test details here",
        execution_time=0.5,
        passed_tests=["test_one", "test_two"],
        failed_tests=[],
        skipped_tests=[]
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
    last_failed = ["test_one", "test_two"]
    
    # Patch the get_last_failed_tests function
    with patch("agents.mcp_test_server.LAST_FAILED_TESTS", last_failed):
        response = client.get("/last-failed")
        assert response.status_code == 200
        assert response.json() == last_failed


if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 