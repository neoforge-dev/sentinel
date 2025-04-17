#!/usr/bin/env python3
"""
Test Agent Plugin: A plugin for the base agent that interfaces with the MCP Test Server.

This plugin enables the agent to run tests, retrieve results, analyze failures,
and format test output in a way that's most useful for debugging.

Dependencies:
- requests
- Enum from enum
- json, os, sys
"""

import os
import sys
import json
import requests
from enum import Enum
from typing import Dict, List, Optional, Any, Union
import asyncio
import aiohttp

# Get the MCP Test Server URL from environment or use default
MCP_TEST_SERVER_URL = os.environ.get("MCP_TEST_SERVER_URL", "http://localhost:8082")
API_KEY = os.environ.get("MCP_API_KEY", "test-key")  # Replace with your actual API key


class TestRunner(str, Enum):
    """Enumeration of test runners"""
    PYTEST = "pytest"
    UNITTEST = "unittest"
    UV = "uv"


class ExecutionMode(str, Enum):
    """Enumeration of execution modes"""
    LOCAL = "local"
    DOCKER = "docker"


def run_tests(
    project_path: str,
    test_path: str = None,
    runner: str = "pytest",
    mode: str = "local",
    max_failures: int = 0,
    run_last_failed: bool = False,
    timeout: int = 60,
    max_tokens: int = 4000,
    docker_image: str = None,
    additional_args: List[str] = None
) -> Dict[str, Any]:
    """
    Run tests in the specified project using the MCP Test Server.
    
    Args:
        project_path: Path to the project containing tests
        test_path: Path to tests relative to project_path (if None, uses project_path)
        runner: Test runner to use ('pytest', 'unittest', 'uv')
        mode: Execution mode ('local' or 'docker')
        max_failures: Stop after N failures (0 means run all tests)
        run_last_failed: Only run tests that failed in the last run
        timeout: Maximum time to wait for tests to complete (seconds)
        max_tokens: Maximum token count for output
        docker_image: Docker image to use (when mode is 'docker')
        additional_args: Additional arguments to pass to the test runner
        
    Returns:
        Dict containing test results with status, passed/failed/skipped tests, and details
    """
    url = f"{MCP_TEST_SERVER_URL}/run-tests"
    
    payload = {
        "project_path": project_path,
        "test_path": test_path,
        "runner": runner,
        "mode": mode,
        "max_failures": max_failures,
        "run_last_failed": run_last_failed,
        "timeout": timeout,
        "max_tokens": max_tokens
    }
    
    if docker_image and mode == "docker":
        payload["docker_image"] = docker_image
        
    if additional_args:
        payload["additional_args"] = additional_args
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": f"Failed to run tests: {str(e)}",
            "details": str(e),
            "passed_tests": [],
            "failed_tests": [],
            "skipped_tests": []
        }


def get_test_result(result_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the result of a specific test run by ID.
    
    Args:
        result_id: The ID of the test run
        
    Returns:
        Dict containing test results or None if not found
    """
    url = f"{MCP_TEST_SERVER_URL}/results/{result_id}"
    
    try:
        response = requests.get(url)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        return None


def list_test_results() -> List[str]:
    """
    List all available test result IDs.
    
    Returns:
        List of test result IDs
    """
    url = f"{MCP_TEST_SERVER_URL}/results"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        return []


def get_last_failed_tests() -> List[str]:
    """
    Get the list of tests that failed in the last run.
    
    Returns:
        List of test names that failed
    """
    url = f"{MCP_TEST_SERVER_URL}/last-failed"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        return []


def analyze_test_failures(result_id: str) -> Dict[str, Any]:
    """
    Analyze test failures to provide insights and debugging recommendations.
    
    Args:
        result_id: The ID of the test run to analyze
        
    Returns:
        Dict containing analysis of failures, including potential causes and fix recommendations
    """
    # Get the test result first
    result = get_test_result(result_id)
    if not result or result.get("status") == "success":
        return {
            "status": "no_failures",
            "message": "No failures to analyze" if result else f"Test result {result_id} not found",
            "recommendations": []
        }
    
    # Extract failure details
    failed_tests = result.get("failed_tests", [])
    details = result.get("details", "")
    
    # Basic analysis patterns
    analysis = {
        "status": "failure_analysis",
        "failure_count": len(failed_tests),
        "failed_tests": failed_tests,
        "common_patterns": [],
        "recommendations": []
    }
    
    # Look for common patterns in failures
    if "AssertionError" in details:
        analysis["common_patterns"].append("Assertion failures")
        analysis["recommendations"].append("Review assertion conditions in the failing tests")
    
    if "ImportError" in details or "ModuleNotFoundError" in details:
        analysis["common_patterns"].append("Import errors")
        analysis["recommendations"].append("Check package dependencies and virtual environment")
    
    if "TypeError" in details:
        analysis["common_patterns"].append("Type errors")
        analysis["recommendations"].append("Verify function arguments and return types")
    
    if "KeyError" in details or "AttributeError" in details:
        analysis["common_patterns"].append("Access errors")
        analysis["recommendations"].append("Check for missing dictionary keys or object attributes")
    
    # Add generic recommendations if none found
    if not analysis["recommendations"]:
        analysis["recommendations"] = [
            "Review the failing test details for specific error messages",
            "Check if test fixtures are properly set up",
            "Verify test dependencies and environment"
        ]
    
    return analysis


def format_test_result_for_agent(result: Dict[str, Any]) -> str:
    """
    Format test result in a way that's useful for the agent to analyze.
    
    Args:
        result: Test result dictionary
        
    Returns:
        Formatted string with test result summary and details
    """
    if not result:
        return "No test result available."
    
    status = result.get("status", "unknown")
    execution_time = result.get("execution_time", 0)
    
    # Format the summary
    summary = f"Test Status: {status.upper()}\n"
    summary += f"Execution Time: {execution_time:.2f}s\n"
    summary += f"Passed: {len(result.get('passed_tests', []))}, "
    summary += f"Failed: {len(result.get('failed_tests', []))}, "
    summary += f"Skipped: {len(result.get('skipped_tests', []))}\n\n"
    
    # Add failed tests with details
    failed_tests = result.get("failed_tests", [])
    if failed_tests:
        summary += "FAILED TESTS:\n"
        for test in failed_tests:
            summary += f"- {test}\n"
        summary += "\n"
    
    # Add passed tests (brief)
    passed_tests = result.get("passed_tests", [])
    if passed_tests:
        summary += "PASSED TESTS:\n"
        for test in passed_tests[:5]:  # Show first 5 passed tests
            summary += f"- {test}\n"
        
        if len(passed_tests) > 5:
            summary += f"- ... and {len(passed_tests) - 5} more passed tests\n"
        summary += "\n"
    
    # Add failure details
    if status == "failure" and result.get("details"):
        summary += "FAILURE DETAILS:\n"
        summary += result.get("details", "")
    
    return summary


def register_test_tools(agent):
    """
    Register test tools with the agent.
    
    Args:
        agent: The agent to register tools with
    """
    agent.register_tool(
        name="run_tests",
        description="Run tests in a Python project",
        function=run_tests
    )
    
    agent.register_tool(
        name="get_test_result",
        description="Get the result of a specific test run by ID",
        function=get_test_result
    )
    
    agent.register_tool(
        name="list_test_results",
        description="List all available test result IDs",
        function=list_test_results
    )
    
    agent.register_tool(
        name="get_last_failed_tests",
        description="Get tests that failed in the last run",
        function=get_last_failed_tests
    )
    
    agent.register_tool(
        name="analyze_test_failures",
        description="Analyze test failures for insights and recommendations",
        function=analyze_test_failures
    )
    
    agent.register_tool(
        name="format_test_result",
        description="Format test result for easier analysis",
        function=format_test_result_for_agent
    )


if __name__ == "__main__":
    # Example usage
    import pprint
    
    # Run a test
    result = run_tests(
        project_path="/path/to/project",
        test_path="tests",
        runner="pytest",
        max_failures=1
    )
    
    # Print the result
    print("\n===== TEST RESULT =====")
    pprint.pprint(result)
    
    # Format the result
    formatted = format_test_result_for_agent(result)
    print("\n===== FORMATTED TEST RESULT =====")
    print(formatted) 