#!/usr/bin/env python3
"""
Example client for interacting with the MCP Test Server
Demonstrates running tests locally or in Docker with different options
"""

import os
import sys
import json
import argparse
import requests
from typing import Dict, Any, List, Optional
from enum import Enum
from pathlib import Path
import time

# Default settings
MCP_TEST_SERVER_URL = os.environ.get("MCP_TEST_SERVER_URL", "http://localhost:8082")


class TestRunner(str, Enum):
    """Test runner options"""
    PYTEST = "pytest"
    UNITTEST = "unittest"
    UV = "uv"


class ExecutionMode(str, Enum):
    """Test execution mode"""
    LOCAL = "local"
    DOCKER = "docker"


def run_tests(
    project_path: str,
    test_path: str = "tests",
    runner: TestRunner = TestRunner.PYTEST,
    mode: ExecutionMode = ExecutionMode.LOCAL,
    max_failures: Optional[int] = None,
    run_last_failed: bool = False,
    timeout: int = 300,
    max_tokens: int = 4000,
    docker_image: Optional[str] = None,
    additional_args: List[str] = None
) -> Dict[str, Any]:
    """
    Run tests using the MCP Test Server
    
    Args:
        project_path: Absolute path to the project directory
        test_path: Path to test directory or file, relative to project_path
        runner: Test runner to use (pytest, unittest, uv)
        mode: Execution mode (local or docker)
        max_failures: Stop after N failures (None to run all)
        run_last_failed: Run only the last failed tests
        timeout: Timeout in seconds
        max_tokens: Maximum tokens for output
        docker_image: Docker image to use (defaults to python:3.11)
        additional_args: Additional arguments for the test runner
        
    Returns:
        Test result dictionary
    """
    url = f"{MCP_TEST_SERVER_URL}/run-tests"
    
    if additional_args is None:
        additional_args = []
    
    payload = {
        "project_path": os.path.abspath(project_path),
        "test_path": test_path,
        "runner": runner,
        "mode": mode,
        "max_failures": max_failures,
        "run_last_failed": run_last_failed,
        "timeout": timeout,
        "max_tokens": max_tokens,
        "docker_image": docker_image,
        "additional_args": additional_args
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {
            "status": "error",
            "summary": f"Error connecting to MCP Test Server: {str(e)}",
            "details": str(e)
        }


def get_test_result(result_id: str) -> Dict[str, Any]:
    """
    Get the result of a previous test run
    
    Args:
        result_id: ID of the test result to retrieve
        
    Returns:
        Test result dictionary
    """
    url = f"{MCP_TEST_SERVER_URL}/results/{result_id}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {
            "status": "error",
            "summary": f"Error retrieving test result: {str(e)}",
            "details": str(e)
        }


def list_test_results() -> List[str]:
    """
    List all test result IDs
    
    Returns:
        List of test result IDs
    """
    url = f"{MCP_TEST_SERVER_URL}/results"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return []


def get_last_failed_tests() -> List[str]:
    """
    Get the list of last failed tests
    
    Returns:
        List of last failed test identifiers
    """
    url = f"{MCP_TEST_SERVER_URL}/last-failed"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return []


def display_test_result(result: Dict[str, Any], show_details: bool = True):
    """Display test result in a readable format"""
    print("\n===== Test Result =====")
    print(f"Status: {result.get('status', 'Unknown')}")
    print(f"Execution Time: {result.get('execution_time', 0):.2f} seconds")
    
    passed = len(result.get('passed_tests', []))
    failed = len(result.get('failed_tests', []))
    skipped = len(result.get('skipped_tests', []))
    
    print(f"Tests: {passed} passed, {failed} failed, {skipped} skipped")
    
    if result.get('status') != 'success' and failed > 0:
        print("\n----- Failed Tests -----")
        for i, test in enumerate(result.get('failed_tests', []), 1):
            print(f"{i}. {test}")
    
    print("\n----- Summary -----")
    print(result.get('summary', 'No summary available'))
    
    if show_details and result.get('details'):
        print("\n----- Details -----")
        print(result.get('details'))


def main():
    parser = argparse.ArgumentParser(description="MCP Test Client")
    parser.add_argument("--project", "-p", required=True, help="Path to the project directory")
    parser.add_argument("--tests", "-t", default="tests", help="Path to test directory or file (relative to project)")
    parser.add_argument("--runner", "-r", choices=["pytest", "unittest", "uv"], default="pytest", help="Test runner to use")
    parser.add_argument("--mode", "-m", choices=["local", "docker"], default="local", help="Execution mode")
    parser.add_argument("--max-failures", type=int, help="Stop after N failures")
    parser.add_argument("--last-failed", action="store_true", help="Run only the last failed tests")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout in seconds")
    parser.add_argument("--max-tokens", type=int, default=4000, help="Maximum tokens for output")
    parser.add_argument("--docker-image", help="Docker image to use (for docker mode)")
    parser.add_argument("--args", nargs="*", default=[], help="Additional arguments for the test runner")
    parser.add_argument("--show-details", action="store_true", help="Show detailed test output")
    parser.add_argument("--list-results", action="store_true", help="List all test result IDs")
    parser.add_argument("--get-result", help="Get a specific test result by ID")
    parser.add_argument("--last-failed-list", action="store_true", help="Show list of last failed tests")
    
    args = parser.parse_args()
    
    if args.list_results:
        results = list_test_results()
        print("Available test results:")
        for result_id in results:
            print(f"- {result_id}")
        return
    
    if args.get_result:
        result = get_test_result(args.get_result)
        display_test_result(result, show_details=args.show_details)
        return
    
    if args.last_failed_list:
        tests = get_last_failed_tests()
        print("Last failed tests:")
        for i, test in enumerate(tests, 1):
            print(f"{i}. {test}")
        return
    
    # Run tests
    print(f"Running tests in {args.project} using {args.runner} in {args.mode} mode...")
    result = run_tests(
        project_path=args.project,
        test_path=args.tests,
        runner=args.runner,
        mode=args.mode,
        max_failures=args.max_failures,
        run_last_failed=args.last_failed,
        timeout=args.timeout,
        max_tokens=args.max_tokens,
        docker_image=args.docker_image,
        additional_args=args.args
    )
    
    display_test_result(result, show_details=args.show_details)
    
    print(f"\nTest Result ID: {result.get('id')}")
    print("You can retrieve this result later with:")
    print(f"  python {sys.argv[0]} --get-result {result.get('id')}")


if __name__ == "__main__":
    main() 