#!/usr/bin/env python3
"""
Unit tests for the test runner plugin
"""

import sys
import os
import json
import tempfile
import shutil
import pytest
from unittest.mock import patch, MagicMock

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import the plugin functions
from examples.test_runner_plugin import (
    run_tests_with_mcp,
    get_last_failed_tests_with_mcp,
    get_test_result_with_mcp,
    test_fix_code,
    analyze_test_failures,
    register_test_tools
)


class MockOllamaAgent:
    """Mock OllamaAgent class for testing tool registration"""
    
    def __init__(self, mcp_enabled=False):
        self.tools = {}
        self.context = type('Context', (), {'tools': self.tools})
    
    def register_tool(self, tool_config):
        """Mock tool registration"""
        self.tools[tool_config.name] = tool_config

    def execute_tool(self, tool_name, parameters):
        """Mock tool execution"""
        if tool_name in self.tools:
            return {"mock": "result"}
        return None

    def generate(self, prompt, task_type=None):
        """Mock text generation"""
        return json.dumps({
            "summary": "Mock analysis of test failures",
            "failures": [
                {
                    "test_name": "test_example",
                    "cause": "Mock cause",
                    "fix": "Mock fix"
                }
            ],
            "general_recommendations": "Mock recommendations"
        })


class MockResponse:
    """Mock response object for requests"""
    
    def __init__(self, status_code, data):
        self.status_code = status_code
        self.data = data
    
    def json(self):
        """Return the mock data"""
        return self.data
    
    def raise_for_status(self):
        """Raise an exception if status code is not 200"""
        if self.status_code != 200:
            raise Exception(f"HTTP Error {self.status_code}")


@pytest.fixture
def mock_agent():
    """Create a mock agent for testing"""
    return MockOllamaAgent()


@patch("examples.test_runner_plugin.requests.post")
def test_run_tests_success(mock_post):
    """Test successful test execution"""
    # Mock response data
    mock_data = {
        "id": "test-run-123",
        "status": "failure",
        "summary": "1 passed, 1 failed",
        "details": "Test details",
        "passed_tests": ["test_passing"],
        "failed_tests": ["test_failing"],
        "skipped_tests": []
    }
    
    # Set up the mock
    mock_post.return_value = MockResponse(200, mock_data)
    
    # Call the function
    result = run_tests_with_mcp(
        project_path="/tmp/test_project",
        test_path="tests",
        runner="pytest",
        mode="local",
        max_failures=1
    )
    
    # Verify the results
    assert result["id"] == mock_data["id"]
    assert result["status"] == mock_data["status"]
    assert result["passed_tests"] == mock_data["passed_tests"]
    assert result["failed_tests"] == mock_data["failed_tests"]
    
    # Verify the request
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0].endswith("/run-tests")
    assert kwargs["json"]["project_path"].endswith("test_project")
    assert kwargs["json"]["test_path"] == "tests"
    assert kwargs["json"]["runner"] == "pytest"
    assert kwargs["json"]["mode"] == "local"
    assert kwargs["json"]["max_failures"] == 1


@patch("examples.test_runner_plugin.requests.post")
def test_run_tests_error(mock_post):
    """Test test execution with a server error"""
    # Mock a server error
    mock_post.side_effect = Exception("Connection error")
    
    # Call the function and check it handles the error
    result = run_tests_with_mcp(
        project_path="/tmp/test_project",
        test_path="tests"
    )
    
    # Verify the error is handled
    assert result["status"] == "error"
    assert "Error connecting to MCP Test Server" in result["summary"]


@patch("examples.test_runner_plugin.requests.get")
def test_get_last_failed_tests_success(mock_get):
    """Test getting the last failed tests"""
    # Mock response data
    mock_data = ["test_one", "test_two"]
    
    # Set up the mock
    mock_get.return_value = MockResponse(200, mock_data)
    
    # Call the function
    result = get_last_failed_tests_with_mcp()
    
    # Verify the results
    assert result["success"] is True
    assert result["failed_tests"] == mock_data
    
    # Verify the request
    mock_get.assert_called_once()
    args = mock_get.call_args[0]
    assert args[0].endswith("/last-failed")


@patch("examples.test_runner_plugin.requests.get")
def test_get_last_failed_tests_error(mock_get):
    """Test getting the last failed tests with a server error"""
    # Mock a server error
    mock_get.side_effect = Exception("Connection error")
    
    # Call the function and check it handles the error
    result = get_last_failed_tests_with_mcp()
    
    # Verify the error is handled
    assert result["success"] is False
    assert "Error getting last failed tests" in result["message"]


@patch("examples.test_runner_plugin.requests.get")
def test_get_test_result_success(mock_get):
    """Test getting a specific test result"""
    # Mock response data
    mock_data = {
        "id": "test-result-123",
        "status": "success",
        "summary": "All tests passed",
        "details": "Test details",
        "passed_tests": ["test_one", "test_two"],
        "failed_tests": [],
        "skipped_tests": []
    }
    
    # Set up the mock
    mock_get.return_value = MockResponse(200, mock_data)
    
    # Call the function
    result = get_test_result_with_mcp("test-result-123")
    
    # Verify the results
    assert result["id"] == mock_data["id"]
    assert result["status"] == mock_data["status"]
    assert result["passed_tests"] == mock_data["passed_tests"]
    
    # Verify the request
    mock_get.assert_called_once()
    args = mock_get.call_args[0]
    assert args[0].endswith("/results/test-result-123")


@patch("examples.test_runner_plugin.requests.get")
def test_get_test_result_error(mock_get):
    """Test getting a test result with a server error"""
    # Mock a server error
    mock_get.side_effect = Exception("Connection error")
    
    # Call the function and check it handles the error
    result = get_test_result_with_mcp("test-result-123")
    
    # Verify the error is handled
    assert result["status"] == "error"
    assert "Error retrieving test result" in result["summary"]


@patch("examples.test_runner_plugin.get_last_failed_tests_with_mcp")
def test_test_fix_no_failing_tests(mock_get_failed):
    """Test test_fix_code when there are no failing tests"""
    # Mock empty failed tests
    mock_get_failed.return_value = {
        "success": True,
        "failed_tests": []
    }
    
    # Call the function
    result = test_fix_code(
        code="def test_func():\n    return True",
        file_path="test_file.py",
        project_path="/tmp/project"
    )
    
    # Verify the result
    assert result["success"] is False
    assert "No failing tests to fix" in result["message"]


@patch("examples.test_runner_plugin.get_last_failed_tests_with_mcp")
def test_test_fix_error_getting_failed_tests(mock_get_failed):
    """Test test_fix_code when there's an error getting failed tests"""
    # Mock error getting failed tests
    mock_get_failed.return_value = {
        "success": False,
        "message": "Error getting failed tests"
    }
    
    # Call the function
    result = test_fix_code(
        code="def test_func():\n    return True",
        file_path="test_file.py",
        project_path="/tmp/project"
    )
    
    # Verify the result
    assert result["success"] is False
    assert "Error getting failed tests" in result["message"]


@patch("examples.test_runner_plugin.get_last_failed_tests_with_mcp")
@patch("examples.test_runner_plugin.run_tests_with_mcp")
@patch("examples.test_runner_plugin.os.path.exists")
@patch("examples.test_runner_plugin.os.path.isabs")
@patch("tempfile.mkstemp")
@patch("os.close")
@patch("shutil.copy2")
@patch("builtins.open", new_callable=MagicMock)
def test_test_fix_success(mock_open, mock_copy, mock_close, mock_mkstemp, 
                          mock_isabs, mock_exists, mock_run_tests, mock_get_failed):
    """Test test_fix_code with a successful fix"""
    # Mock file path checks
    mock_isabs.return_value = True
    mock_exists.return_value = True
    
    # Mock tempfile creation
    mock_mkstemp.return_value = (5, "/tmp/backup.py.bak")
    
    # Mock failed tests
    mock_get_failed.return_value = {
        "success": True,
        "failed_tests": ["test_one", "test_two"]
    }
    
    # Mock successful test run after fix
    mock_run_tests.return_value = {
        "status": "success",
        "summary": "All tests passed",
        "passed_tests": ["test_one", "test_two"],
        "failed_tests": []
    }
    
    # Call the function
    result = test_fix_code(
        code="def fixed_function():\n    return True",
        file_path="/tmp/project/test_file.py",
        project_path="/tmp/project"
    )
    
    # Verify the result
    assert result["code_fixed_the_issue"] is True
    assert result["file_tested"] == "/tmp/project/test_file.py"
    assert result["fixed_tests"] == ["test_one", "test_two"]
    assert result["still_failing_tests"] == []
    
    # Verify the file was opened for writing
    mock_open.assert_called_with("/tmp/project/test_file.py", "w")
    
    # Verify the backup was created and restored
    mock_copy.assert_called()


@patch("examples.test_runner_plugin.get_last_failed_tests_with_mcp")
def test_analyze_test_failures_no_failures(mock_get_failed):
    """Test analyze_test_failures when there are no failing tests"""
    # Mock empty failed tests
    mock_get_failed.return_value = {
        "success": True,
        "failed_tests": []
    }
    
    # Call the function
    result = analyze_test_failures(project_path="/tmp/project")
    
    # Verify the result
    assert result["success"] is True
    assert "No failing tests to analyze" in result["message"]
    assert "All tests are passing" in result["analysis"]


@patch("examples.test_runner_plugin.get_last_failed_tests_with_mcp")
@patch("examples.test_runner_plugin.run_tests_with_mcp")
def test_analyze_test_failures_run_error(mock_run_tests, mock_get_failed):
    """Test analyze_test_failures when there's an error running tests"""
    # Mock failed tests
    mock_get_failed.return_value = {
        "success": True,
        "failed_tests": ["test_one"]
    }
    
    # Mock error running tests
    mock_run_tests.return_value = {
        "status": "error",
        "summary": "Error running tests"
    }
    
    # Call the function
    result = analyze_test_failures(project_path="/tmp/project")
    
    # Verify the result
    assert result["success"] is False
    assert "Error running tests" in result["message"]


@patch("examples.test_runner_plugin.get_last_failed_tests_with_mcp")
@patch("examples.test_runner_plugin.run_tests_with_mcp")
def test_analyze_test_failures_success(mock_run_tests, mock_get_failed, mock_agent):
    """Test analyze_test_failures with successful analysis"""
    # Mock failed tests
    mock_get_failed.return_value = {
        "success": True,
        "failed_tests": ["test_one"]
    }
    
    # Mock successful test run
    mock_run_tests.return_value = {
        "status": "failure",
        "summary": "Tests failed",
        "details": "Detailed test output",
        "passed_tests": [],
        "failed_tests": ["test_one"]
    }
    
    # Patch OllamaAgent
    with patch("examples.test_runner_plugin.OllamaAgent", return_value=mock_agent):
        # Call the function
        result = analyze_test_failures(project_path="/tmp/project")
        
        # Verify the result
        assert result["success"] is True
        assert "analysis" in result
        assert "test_result" in result
        
        # Verify the analysis structure
        analysis = result["analysis"]
        assert "summary" in analysis
        assert "failures" in analysis
        assert "general_recommendations" in analysis


def test_register_test_tools(mock_agent):
    """Test that test tools are registered with the agent"""
    # Register tools with the mock agent
    register_test_tools(mock_agent)
    
    # Verify the tools were registered
    assert "run_tests" in mock_agent.tools
    assert "get_last_failed_tests" in mock_agent.tools
    assert "test_fix" in mock_agent.tools
    assert "analyze_test_failures" in mock_agent.tools


if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 