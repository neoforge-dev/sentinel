#!/usr/bin/env python3
"""
MCP Enhanced Agent Demo

This script demonstrates the capabilities of the MCP Enhanced Agent,
including code analysis, formatting, and test running.

Run this script to see the MCP Enhanced Agent in action.
"""

import os
import sys
import json
import asyncio
import argparse
from typing import Dict, Any, Optional, List
from pathlib import Path

# Add the src directory to the path so we can import the MCP enhanced agent
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.mcp_enhanced_agent import MCPEnhancedAgent

# Default URLs for the MCP servers, can be overridden by environment variables
MCP_CODE_SERVER_URL = os.environ.get("MCP_CODE_SERVER_URL", "http://localhost:8000")
MCP_TEST_SERVER_URL = os.environ.get("MCP_TEST_SERVER_URL", "http://localhost:8082")
API_KEY = os.environ.get("MCP_API_KEY", "test-key") # Replace with your actual API key

# Sample code with various issues for demonstration
SAMPLE_CODE = """
def calculate_total(items):
    # This function calculates the total price of items
    total=0  # Missing spaces around the operator
    
    for i in range(len(items)):  # Could use enumerate instead
        total += items[i]['price']
    
    unused_var = "This variable is never used"  # Unused variable
    
    return total

class ShoppingCart:
    def __init__(self):
        self.items = []
    
    def add_item(self, item):
        self.items.append(item)
    
    def get_total(self):
        return calculate_total(self.items)
    
    def empty(self):  # This method is never used
        self.items = []
"""

async def demo_code_analysis(agent: MCPEnhancedAgent) -> None:
    """
    Demonstrate code analysis capabilities.
    """
    print("\n" + "="*80)
    print("CODE ANALYSIS DEMO")
    print("="*80)
    
    print("\nSample code to analyze:")
    print("-"*50)
    print(SAMPLE_CODE)
    print("-"*50)
    
    # Analyze the code
    print("\nAnalyzing code...")
    result = await agent.analyze_code(SAMPLE_CODE)
    
    # Print the results
    print("\nAnalysis results:")
    print("-"*50)
    print(f"Found {len(result['issues'])} issues:")
    
    for i, issue in enumerate(result['issues'], 1):
        print(f"\n{i}. {issue['code']}: {issue['message']}")
        print(f"   Location: Line {issue['location']['row']}, Column {issue['location']['column']}")
        if issue.get('fix'):
            print(f"   Suggested fix: {issue['fix']}")
    
    # Format the code
    print("\n" + "-"*50)
    print("Formatting code...")
    format_result = await agent.format_code(SAMPLE_CODE)
    
    print("\nFormatted code:")
    print("-"*50)
    print(format_result['formatted_code'])
    print("-"*50)
    
    # Analyze and fix the code
    print("\nAnalyzing and fixing code automatically...")
    fix_result = await agent.analyze_and_fix_code(SAMPLE_CODE)
    
    print("\nFixed code:")
    print("-"*50)
    print(fix_result['fixed_code'])
    print("-"*50)
    
    if 'unfixable_issues' in fix_result and fix_result['unfixable_issues']:
        print("\nRemaining issues that couldn't be fixed automatically:")
        for i, issue in enumerate(fix_result['unfixable_issues'], 1):
            print(f"{i}. {issue['code']}: {issue['message']}")
    
    # Store a snippet
    print("\nStoring code snippet...")
    store_result = await agent.store_snippet(SAMPLE_CODE, "shopping_cart_example")
    print(f"Snippet stored with ID: {store_result.get('id', 'unknown')}")

async def demo_test_runner(agent: MCPEnhancedAgent, project_path: str, test_path: Optional[str] = None) -> None:
    """
    Demonstrate test running capabilities.
    
    Args:
        agent: The MCPEnhancedAgent instance
        project_path: Path to the project
        test_path: Path to tests (relative to project_path)
    """
    print("\n" + "="*80)
    print("TEST RUNNER DEMO")
    print("="*80)
    
    # Set default test path if not provided
    if not test_path:
        test_path = "tests/test_sample"
    
    print(f"\nRunning tests in {project_path}/{test_path}...")
    
    # Run tests
    test_result = await agent.run_tests(
        project_path=project_path,
        test_path=test_path,
        runner="pytest",
        mode="local",
        max_failures=2,
    )
    
    # Print test results
    print("\nTest results:")
    print("-"*50)
    print(f"Status: {test_result['status']}")
    print(f"Execution time: {test_result['execution_time']:.2f} seconds")
    print(f"Summary: {test_result['summary']}")
    print(f"Passed: {len(test_result['passed_tests'])}")
    print(f"Failed: {len(test_result['failed_tests'])}")
    print(f"Skipped: {len(test_result['skipped_tests'])}")
    
    if test_result['failed_tests']:
        print("\nFailed tests:")
        for i, test in enumerate(test_result['failed_tests'], 1):
            print(f"\n{i}. {test['name']}")
            print(f"   {test['message']}")
    
    # Analyze test results
    print("\n" + "-"*50)
    print("Analyzing test results...")
    analysis = await agent.analyze_test_results(test_result)
    
    print("\nTest analysis:")
    print("-"*50)
    print(analysis['analysis'])
    print("-"*50)
    
    # Run only failed tests
    if test_result['failed_tests']:
        print("\nRunning only the tests that failed in the previous run...")
        rerun_result = await agent.run_tests(
            project_path=project_path,
            test_path=test_path,
            runner="pytest",
            mode="local",
            run_last_failed=True,
        )
        
        print("\nRe-run results:")
        print("-"*50)
        print(f"Status: {rerun_result['status']}")
        print(f"Execution time: {rerun_result['execution_time']:.2f} seconds")
        print(f"Failed: {len(rerun_result['failed_tests'])}")

async def main():
    parser = argparse.ArgumentParser(description="MCP Enhanced Agent Demo")
    parser.add_argument("--code-server", default=MCP_CODE_SERVER_URL,
                        help=f"URL of the MCP Code Server (default: {MCP_CODE_SERVER_URL})")
    parser.add_argument("--test-server", default=MCP_TEST_SERVER_URL,
                        help=f"URL of the MCP Test Server (default: {MCP_TEST_SERVER_URL})")
    parser.add_argument("--project-path", default="./",
                        help="Path to the project for testing (default: ./)")
    parser.add_argument("--test-path", default="tests/test_sample",
                        help="Path to the tests, relative to project-path (default: tests/test_sample)")
    parser.add_argument("--code-only", action="store_true",
                        help="Run only the code analysis demo")
    parser.add_argument("--test-only", action="store_true",
                        help="Run only the test runner demo")
    
    args = parser.parse_args()
    
    # Initialize the agent
    agent = MCPEnhancedAgent(
        code_server_url=args.code_server,
        test_server_url=args.test_server,
    )
    
    try:
        if not args.test_only:
            await demo_code_analysis(agent)
        
        if not args.code_only:
            await demo_test_runner(agent, args.project_path, args.test_path)
        
        print("\n" + "="*80)
        print("Demo completed successfully!")
        print("="*80)
    
    except Exception as e:
        print(f"\nError: {e}")
        print("\nMake sure the MCP servers are running:")
        print(f"- Code Server: {args.code_server}")
        print(f"- Test Server: {args.test_server}")
        print("\nStart the servers with:")
        print("  python agents/mcp_code_server.py")
        print("  python agents/mcp_test_server.py")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 