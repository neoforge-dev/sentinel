#!/usr/bin/env python3
"""
Test runner script for BaseAgent MCP integration tests
Runs all unit and integration tests
"""

import os
import sys
import pytest
import argparse
from typing import List, Optional


def run_tests(test_path: Optional[str] = None, verbose: bool = False, 
              junit_xml: Optional[str] = None, stop_on_failure: bool = False) -> int:
    """
    Run the test suite
    
    Args:
        test_path: Optional path to specific tests to run
        verbose: Whether to show verbose output
        junit_xml: Path to JUnit XML report output
        stop_on_failure: Whether to stop on the first failure
    
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    # Build pytest arguments
    pytest_args: List[str] = []
    
    # Add verbosity
    if verbose:
        pytest_args.append("-v")
    
    # Add JUnit XML report
    if junit_xml:
        pytest_args.extend(["--junitxml", junit_xml])
    
    # Add stop on failure
    if stop_on_failure:
        pytest_args.append("-x")
    
    # Add test path
    if test_path:
        pytest_args.append(test_path)
    else:
        # Run all tests
        pytest_args.append(os.path.dirname(os.path.abspath(__file__)))
    
    # Run the tests
    print(f"Running tests with args: {pytest_args}")
    return pytest.main(pytest_args)


def main() -> int:
    """
    Parse command line arguments and run tests
    
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = argparse.ArgumentParser(description="Run BaseAgent tests")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show verbose output")
    parser.add_argument("-x", "--stop-on-failure", action="store_true", help="Stop on first test failure")
    parser.add_argument("--junit-xml", help="Generate JUnit XML report")
    parser.add_argument("test_path", nargs="?", help="Specific test path to run")
    
    args = parser.parse_args()
    
    return run_tests(
        test_path=args.test_path,
        verbose=args.verbose,
        junit_xml=args.junit_xml,
        stop_on_failure=args.stop_on_failure
    )


if __name__ == "__main__":
    sys.exit(main()) 