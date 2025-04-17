#!/usr/bin/env python3
"""
Plugin for the main agent to run and analyze tests using the MCP test server.

This plugin provides tools for running tests either locally or in Docker,
retrieving test results, and listing previously run tests.

Dependencies:
- requests
"""

import os
import sys
import json
from typing import Dict, List, Optional, Any, Union
import requests
import aiohttp
import asyncio

# --- Configuration ---
MCP_CODE_SERVER_URL = os.environ.get("MCP_CODE_SERVER_URL", "http://localhost:8081")
MCP_TEST_SERVER_URL = os.environ.get("MCP_TEST_SERVER_URL", "http://localhost:8082")
API_KEY = os.environ.get("MCP_API_KEY", "test-key")  # Replace with your actual API key
# --- End Configuration ---

# Enums for test runner and execution mode
class TestRunner:
    PYTEST = "pytest"
    UNITTEST = "unittest"
    UV = "uv"

class ExecutionMode:
    LOCAL = "local"
    DOCKER = "docker"

def run_tests(
    project_path: str,
    test_path: Optional[str] = None,
    runner: str = TestRunner.PYTEST,
    mode: str = ExecutionMode.LOCAL,
    max_failures: Optional[int] = None,
    run_last_failed: bool = False,
    timeout: int = 300,
    max_tokens: int = 4000,
    docker_image: Optional[str] = None,
    additional_args: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Run tests in the specified project path using the MCP test server.
    
    Args:
        project_path: Path to the project containing tests
        test_path: Specific test path to run (optional)
        runner: Test runner to use (pytest, unittest, uv)
        mode: Execution mode (local or docker)
        max_failures: Maximum number of failures before stopping
        run_last_failed: Only run previously failed tests
        timeout: Maximum time in seconds for test execution
        max_tokens: Maximum token count for the output
        docker_image: Docker image to use if mode is docker
        additional_args: Additional arguments to pass to the test runner
        
    Returns:
        Dict containing the test results
    """
    try:
        payload = {
            "project_path": project_path,
            "test_path": test_path,
            "runner": runner,
            "mode": mode,
            "max_failures": max_failures,
            "run_last_failed": run_last_failed,
            "timeout": timeout,
            "max_tokens": max_tokens,
            "docker_image": docker_image,
            "additional_args": additional_args or []
        }
        
        response = requests.post(
            f"{MCP_TEST_SERVER_URL}/run_tests",
            json={k: v for k, v in payload.items() if v is not None}
        )
        
        if response.status_code != 200:
            return {
                "success": False,
                "error": f"Error {response.status_code}: {response.text}"
            }
            
        result = response.json()
        return {
            "success": True,
            "test_id": result.get("test_id"),
            "result": result
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Exception: {str(e)}"
        }

def get_test_result(test_id: str) -> Dict[str, Any]:
    """
    Get the result of a previously run test by its ID
    """
    # Use /results/ endpoint
    url = f"{MCP_TEST_SERVER_URL}/results/{test_id}" 
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        return {
            "success": True,
            "result": response.json()
        }
    except requests.exceptions.HTTPError as http_err:
        return {
            "success": False,
            "error": f"HTTP error occurred: {http_err}"
        }
    except requests.exceptions.RequestException as req_err:
        return {
            "success": False,
            "error": f"Request error occurred: {req_err}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Exception occurred: {str(e)}"
        }

def list_test_results() -> Dict[str, Any]:
    """
    List all test result IDs.
    
    Returns:
        Dict containing a list of test result IDs
    """
    try:
        response = requests.get(f"{MCP_TEST_SERVER_URL}/test_results")
        
        if response.status_code != 200:
            return {
                "success": False,
                "error": f"Error {response.status_code}: {response.text}"
            }
            
        result = response.json()
        return {
            "success": True,
            "result": result
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Exception: {str(e)}"
        }

def get_last_failed_tests() -> Dict[str, Any]:
    """
    Get the list of tests that failed in the last run.
    
    Returns:
        Dict containing a list of the last failed tests
    """
    try:
        response = requests.get(f"{MCP_TEST_SERVER_URL}/last_failed_tests")
        
        if response.status_code != 200:
            return {
                "success": False,
                "error": f"Error {response.status_code}: {response.text}"
            }
            
        result = response.json()
        return {
            "success": True,
            "result": result
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Exception: {str(e)}"
        }

def format_test_result(result: Dict[str, Any]) -> str:
    """
    Format the test result into a human-readable string.
    
    Args:
        result: Test result dictionary
        
    Returns:
        Formatted string representation of the test result
    """
    if not result.get("success", False):
        return f"Error: {result.get('error', 'Unknown error')}"
    
    test_result = result.get("result", {})
    if "status" not in test_result:
        return "Invalid test result format"
    
    status = test_result["status"]
    summary = test_result.get("summary", "No summary available")
    details = test_result.get("details", "No details available")
    
    output = [
        f"Status: {status}",
        f"Summary: {summary}",
        "-------- Details --------",
        details,
    ]
    
    passed_tests = test_result.get("passed_tests", [])
    failed_tests = test_result.get("failed_tests", [])
    skipped_tests = test_result.get("skipped_tests", [])
    
    if passed_tests:
        output.append("\n-------- Passed Tests --------")
        output.extend(passed_tests)
    
    if failed_tests:
        output.append("\n-------- Failed Tests --------")
        output.extend(failed_tests)
    
    if skipped_tests:
        output.append("\n-------- Skipped Tests --------")
        output.extend(skipped_tests)
    
    return "\n".join(output)

def register_test_tools(register_tool):
    """
    Register test analysis tools with the main agent.
    
    Args:
        register_tool: Function to register a tool with the agent
    """
    register_tool(
        "run_tests",
        run_tests,
        "Run tests in a project using the MCP test server"
    )
    register_tool(
        "get_test_result",
        get_test_result,
        "Get the result of a previously run test by its ID"
    )
    register_tool(
        "list_test_results",
        list_test_results,
        "List all test result IDs"
    )
    register_tool(
        "get_last_failed_tests",
        get_last_failed_tests,
        "Get the list of tests that failed in the last run"
    )
    register_tool(
        "format_test_result",
        format_test_result,
        "Format a test result into a human-readable string"
    )

if __name__ == "__main__":
    # Example usage
    if len(sys.argv) < 2:
        print("Usage: python test_analysis_plugin.py <project_path> [test_path]")
        sys.exit(1)
    
    project_path = sys.argv[1]
    test_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    print(f"Running tests in project: {project_path}")
    if test_path:
        print(f"Specific test path: {test_path}")
    
    # Run tests with default settings
    result = run_tests(
        project_path=project_path,
        test_path=test_path,
        runner=TestRunner.PYTEST,
        mode=ExecutionMode.LOCAL
    )
    
    if not result.get("success", False):
        print(f"Error: {result.get('error', 'Unknown error')}")
        sys.exit(1)
    
    test_id = result.get("test_id")
    print(f"Test ID: {test_id}")
    
    # Get and format test results
    result = get_test_result(test_id)
    if result.get("success", False):
        formatted_result = format_test_result(result)
        print("\nTest Results:")
        print(formatted_result)
    else:
        print(f"Error retrieving results: {result.get('error', 'Unknown error')}") 