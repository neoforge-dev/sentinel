#!/usr/bin/env python3
"""
Unit tests for the test analysis plugin.
"""

import unittest
from unittest.mock import patch, MagicMock
import json
import sys
import os

# Add the examples directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../examples')))

import test_analysis_plugin as plugin

class TestAnalysisPluginTests(unittest.TestCase):
    """Tests for the test analysis plugin."""

    @patch('requests.post')
    def test_run_tests(self, mock_post):
        """Test the run_tests function with successful response."""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "test_id": "test123",
            "status": "success",
            "summary": "All tests passed"
        }
        mock_post.return_value = mock_response

        # Call function
        result = plugin.run_tests(
            project_path="/test/project",
            test_path="tests/",
            runner=plugin.TestRunner.PYTEST,
            mode=plugin.ExecutionMode.LOCAL
        )

        # Assertions
        self.assertTrue(result["success"])
        self.assertEqual(result["test_id"], "test123")
        mock_post.assert_called_once()
        # Verify payload
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["project_path"], "/test/project")
        self.assertEqual(kwargs["json"]["test_path"], "tests/")

    @patch('requests.post')
    def test_run_tests_error(self, mock_post):
        """Test the run_tests function with error response."""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        mock_post.return_value = mock_response

        # Call function
        result = plugin.run_tests(project_path="/test/project")

        # Assertions
        self.assertFalse(result["success"])
        self.assertIn("Error 500", result["error"])

    @patch('requests.post')
    def test_run_tests_exception(self, mock_post):
        """Test the run_tests function with exception."""
        # Mock to raise exception
        mock_post.side_effect = Exception("Connection error")

        # Call function
        result = plugin.run_tests(project_path="/test/project")

        # Assertions
        self.assertFalse(result["success"])
        self.assertIn("Exception: Connection error", result["error"])

    @patch('requests.get')
    def test_get_test_result(self, mock_get):
        """Test the get_test_result function."""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "summary": "All tests passed",
            "details": "Ran 10 tests in 0.5s",
            "passed_tests": ["test_one", "test_two"],
            "failed_tests": [],
            "skipped_tests": []
        }
        mock_get.return_value = mock_response

        # Call function
        result = plugin.get_test_result("test123")

        # Assertions
        self.assertTrue(result["success"])
        self.assertEqual(result["result"]["status"], "success")
        mock_get.assert_called_once_with(f"{plugin.MCP_TEST_SERVER_URL}/test_result/test123")

    @patch('requests.get')
    def test_list_test_results(self, mock_get):
        """Test the list_test_results function."""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = ["test123", "test456"]
        mock_get.return_value = mock_response

        # Call function
        result = plugin.list_test_results()

        # Assertions
        self.assertTrue(result["success"])
        self.assertEqual(result["result"], ["test123", "test456"])
        mock_get.assert_called_once_with(f"{plugin.MCP_TEST_SERVER_URL}/test_results")

    @patch('requests.get')
    def test_get_last_failed_tests(self, mock_get):
        """Test the get_last_failed_tests function."""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = ["test_three", "test_four"]
        mock_get.return_value = mock_response

        # Call function
        result = plugin.get_last_failed_tests()

        # Assertions
        self.assertTrue(result["success"])
        self.assertEqual(result["result"], ["test_three", "test_four"])
        mock_get.assert_called_once_with(f"{plugin.MCP_TEST_SERVER_URL}/last_failed_tests")

    def test_format_test_result(self):
        """Test the format_test_result function."""
        # Create a test result
        test_result = {
            "success": True,
            "result": {
                "status": "success",
                "summary": "All tests passed",
                "details": "Ran 10 tests in 0.5s",
                "passed_tests": ["test_one", "test_two"],
                "failed_tests": ["test_three"],
                "skipped_tests": ["test_four"]
            }
        }

        # Call function
        formatted = plugin.format_test_result(test_result)

        # Assertions
        self.assertIn("Status: success", formatted)
        self.assertIn("Summary: All tests passed", formatted)
        self.assertIn("-------- Details --------", formatted)
        self.assertIn("Ran 10 tests in 0.5s", formatted)
        self.assertIn("-------- Passed Tests --------", formatted)
        self.assertIn("test_one", formatted)
        self.assertIn("test_two", formatted)
        self.assertIn("-------- Failed Tests --------", formatted)
        self.assertIn("test_three", formatted)
        self.assertIn("-------- Skipped Tests --------", formatted)
        self.assertIn("test_four", formatted)

    def test_format_test_result_error(self):
        """Test the format_test_result function with error result."""
        # Create an error result
        error_result = {
            "success": False,
            "error": "Connection error"
        }

        # Call function
        formatted = plugin.format_test_result(error_result)

        # Assertions
        self.assertEqual(formatted, "Error: Connection error")

    def test_format_test_result_invalid(self):
        """Test the format_test_result function with invalid result."""
        # Create an invalid result
        invalid_result = {
            "success": True,
            "result": {
                "summary": "No status field"
            }
        }

        # Call function
        formatted = plugin.format_test_result(invalid_result)

        # Assertions
        self.assertEqual(formatted, "Invalid test result format")

    @patch('builtins.print')
    @patch('sys.argv', ['test_analysis_plugin.py', '/test/project', 'tests/'])
    @patch('test_analysis_plugin.run_tests')
    @patch('test_analysis_plugin.get_test_result')
    def test_main_function(self, mock_get_result, mock_run_tests, mock_print):
        """Test the main function with successful execution."""
        # Mock run_tests to return success
        mock_run_tests.return_value = {
            "success": True,
            "test_id": "test123"
        }
        
        # Mock get_test_result to return a result
        mock_get_result.return_value = {
            "success": True,
            "result": {
                "status": "success",
                "summary": "All tests passed"
            }
        }
        
        # Execute the main block
        with patch.object(plugin, "__name__", "__main__"):
            exec(open(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                    'examples', 'test_analysis_plugin.py')).read())
        
        # Assertions
        mock_run_tests.assert_called_once()
        mock_get_result.assert_called_once_with("test123")
        # Verify print calls
        mock_print.assert_any_call(f"Running tests in project: /test/project")
        mock_print.assert_any_call(f"Specific test path: tests/")
        mock_print.assert_any_call(f"Test ID: test123")

if __name__ == "__main__":
    unittest.main() 