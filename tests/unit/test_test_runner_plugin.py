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
import unittest
from unittest.mock import patch, MagicMock, call, mock_open
import requests

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Define Mock URL for the test server
MOCK_URL = "http://localhost:8082"

# Import the plugin functions
from examples.test_runner_plugin import (
    run_tests_with_mcp,
    get_last_failed_tests_with_mcp,
    get_test_result_with_mcp,
    apply_fix_and_retest,
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
    
    def __init__(self, status_code, json_data=None, text_data=None):
        self.status_code = status_code
        self._json_data = json_data
        self._text_data = text_data if text_data is not None else (json.dumps(json_data) if json_data else "")
        # Add headers attribute
        self.headers = {'content-type': 'application/json'} # Default, can be overridden
    
    def json(self):
        """Return the mock data"""
        if self._json_data is not None:
            return self._json_data
        return None
    
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
    """Test test execution with a connection error"""
    # Mock a connection error
    error_message = "Connection error"
    mock_post.side_effect = requests.RequestException(error_message)
    
    # Call the function and check it handles the error
    result = run_tests_with_mcp(
        project_path="/tmp/test_project",
        test_path="tests"
    )
    
    # Verify the error structure: {success: False, status: 'error', message: ..., details: ...}
    assert result["status"] == "error"
    assert "error" in result["summary"].lower()
    assert error_message in result["details"]
    assert "summary" not in result # Ensure summary isn't present on error


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
    
    # Verify the request URL (ignoring query params for simplicity for now)
    mock_get.assert_called_once()
    args = mock_get.call_args[0]
    # Check that the base URL ends with /last-failed
    base_url = args[0].split('?')[0] 
    assert base_url.endswith("/last-failed")


@patch("examples.test_runner_plugin.requests.get")
def test_get_last_failed_tests_error(mock_get):
    """Test getting the last failed tests with a connection error"""
    # Mock a connection error
    error_message = "Connection error"
    mock_get.side_effect = requests.RequestException(error_message)
    
    # Call the function and check it handles the error
    result = get_last_failed_tests_with_mcp()
    
    # Verify the error is handled
    assert result["status"] == "error"
    assert "error" in result["summary"].lower()
    assert error_message in result["details"]


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
    """Test getting a test result with a connection error"""
    # Mock a connection error
    error_message = "Connection error"
    mock_get.side_effect = requests.RequestException(error_message)
    
    # Call the function and check it handles the error
    result = get_test_result_with_mcp("test-result-123")
    
    # Verify the error structure: {success: False, status: 'error', message: ..., details: ...}
    assert result["status"] == "error"
    assert "error" in result["summary"].lower()
    assert error_message in result["details"]
    assert "summary" not in result # Ensure summary isn't present on error


@patch("examples.test_runner_plugin.get_last_failed_tests_with_mcp")
def test_test_fix_no_failing_tests(mock_get_failed):
    """Test test_fix_code when there are no failing tests"""
    # Mock empty failed tests
    mock_get_failed.return_value = {
        "success": True,
        "failed_tests": []
    }
    
    # Call the function
    result = apply_fix_and_retest(
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
    result = apply_fix_and_retest(
        code="def test_func():\n    return True",
        file_path="test_file.py",
        project_path="/tmp/project"
    )
    
    # Verify the result
    assert result["success"] is False
    assert "Error getting failed tests" in result["message"]


class TestTestRunnerPluginTests(unittest.TestCase):
    @patch('examples.test_runner_plugin.run_tests_with_mcp')
    @patch('os.path.exists')
    @patch('tempfile.mkstemp')
    @patch('os.close')
    @patch('shutil.copy2')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.unlink')
    def test_apply_fix_and_retest_success(self, mock_unlink, mock_open_func, mock_copy, mock_close, mock_mkstemp, mock_exists, mock_run_tests):
        """Test the apply_fix_and_retest function with a successful fix test."""
        # Configure mocks
        mock_exists.return_value = True
        mock_mkstemp.return_value = (123, "/tmp/backup.py.bak")
        
        # Mock run_tests results
        mock_run_tests.return_value = {
            "success": True,
            "status": "success",
            "summary": "All tests passed after fix",
            "failed_tests": [],
            "id": "fix-test-run-123",
            "details": "...",
            "passed_tests": ["test_one", "test_two"],
            "skipped_tests": []
        }
        
        # Mock get_last_failed_tests
        with patch('examples.test_runner_plugin.get_last_failed_tests_with_mcp') as mock_get_failed:
            mock_get_failed.return_value = {
                "success": True,
                "failed_tests": ["test_one", "test_two"]
            }

            # Define inputs
            fixed_code = "def fixed_function(): return True"
            file_path = "src/my_module.py"
            project_path = "/abs/path/to/project"
            full_file_path = os.path.join(project_path, file_path)
            backup_file_path = "/tmp/backup.py.bak"

            # Call the renamed function
            result = apply_fix_and_retest(code=fixed_code, file_path=file_path, project_path=project_path)

            # Assertions
            mock_get_failed.assert_called_once()
            assert call(full_file_path) in mock_exists.call_args_list
            assert call(backup_file_path) in mock_exists.call_args_list
            assert mock_exists.call_count == 2
            
            mock_mkstemp.assert_called_once()
            mock_close.assert_called_once_with(123)
            mock_copy.assert_has_calls([
                call(full_file_path, backup_file_path),
                call(backup_file_path, full_file_path)
            ], any_order=False)

            mock_open_func.assert_called_once_with(full_file_path, 'w')
            mock_open_func().write.assert_called_once_with(fixed_code)
            mock_run_tests.assert_called_once_with(
                project_path=project_path,
                test_path="test_one test_two",
                runner="pytest",
                max_failures=None,
                run_last_failed=True,
                max_tokens=6000
            )
            mock_unlink.assert_called_once_with(backup_file_path)
            
            assert result["success"] is True
            assert result["status"] == "success"
            assert result["code_fixed_the_issue"] is True
            assert result["file_tested"] == file_path
            assert result["fixed_tests"] == ["test_one", "test_two"]
            assert result["still_failing_tests"] == []

    @patch.dict(os.environ, {"AGENT_API_KEY": "test-key"}, clear=True)
    @patch('examples.test_runner_plugin.requests.post')
    def test_run_tests_streaming(self, mock_post):
        """Test run_tests_with_mcp handling a streaming response."""
        # Mock the response object
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/plain"}
        
        # Simulate iter_lines output
        stream_lines = [
            "--- Starting test run (stream-id-123) ---",
            "STDOUT: Running tests...",
            "STDOUT: PASSED test_1",
            "STDERR: Some warning",
            "--- Test run complete (stream-id-123). Status: success ---"
        ]
        mock_response.iter_lines.return_value = iter(stream_lines)
        
        # Configure the mock post call
        mock_post.return_value = mock_response

        payload = {
            "project_path": "/path/stream", 
            "mode": "local" # Ensure mode is local to trigger streaming
        }
        
        # Patch print to capture output
        with patch('builtins.print') as mock_print:
            result = run_tests_with_mcp(**payload)

            # Verify requests.post was called with stream=True
            mock_post.assert_called_once()
            call_args, call_kwargs = mock_post.call_args
            self.assertEqual(call_args[0], f"{MOCK_URL}/run-tests")
            self.assertEqual(call_kwargs["json"]["mode"], "local")
            self.assertTrue(call_kwargs["stream"])
            self.assertIn("X-API-Key", call_kwargs["headers"])

            # Verify the streaming output was printed
            self.assertGreater(mock_print.call_count, len(stream_lines)) # Print called for each line + start/end markers
            printed_output = "\n".join([call.args[0] for call in mock_print.call_args_list])
            self.assertIn("--- Streaming Test Output ---", printed_output)
            self.assertIn("STDOUT: Running tests...", printed_output)
            self.assertIn("STDERR: Some warning", printed_output)
            self.assertIn("--- End of Stream ---", printed_output)

            # Verify the returned result dictionary
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["result_id"], "stream-id-123")
            self.assertIn("completed with status success", result["summary"])
            self.assertIn("STDOUT: PASSED test_1", result["details"]) # Check details contain full output


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