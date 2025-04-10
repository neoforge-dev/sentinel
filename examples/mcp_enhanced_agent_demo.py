#!/usr/bin/env python3
"""
MCP Enhanced Agent Demo.

This script demonstrates the capabilities of the MCPEnhancedAgent
for code analysis and test execution.
"""

import os
import sys
import asyncio
import argparse
from pprint import pprint

# Add the parent directory to sys.path to import the agent
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.mcp_enhanced_agent import MCPEnhancedAgent

# Sample code with issues for demonstration
SAMPLE_CODE_WITH_ISSUES = """
def add_numbers(a, b):
    return a+b  # Missing spaces around operator

def process_data(data):
    result = []
    for item in data:
      result.append(item * 2)  # Inconsistent indentation
    
    return result

# Unused import
import json

class DataProcessor:
    def __init__(self, config):
        self.config = config
        
    def process(self, items):
        for i in range(0, len(items)):
            print(f"Processing {items[i]}")  # Using print instead of logging
            items[i] = items[i] * 2
        return items
"""

async def demo_code_analysis(agent):
    """Demonstrate code analysis capabilities."""
    print("\n=== Code Analysis Demo ===\n")
    
    # Analyze code
    print("Analyzing code...")
    result = await agent.analyze_code(SAMPLE_CODE_WITH_ISSUES)
    
    # Print analysis results
    print(f"\nFound {len(result.get('issues', []))} issues:")
    for i, issue in enumerate(result.get('issues', []), 1):
        print(f"{i}. Line {issue.get('line')}: {issue.get('message')}")
    
    # Analyze and fix code
    print("\n--- Analyzing and fixing code ---")
    fix_result = await agent.analyze_and_fix_code(SAMPLE_CODE_WITH_ISSUES)
    
    print("\nOriginal code:")
    print(SAMPLE_CODE_WITH_ISSUES) # Show the original code explicitly
    
    print("\nFixed code:")
    print(fix_result.get('fixed_code', "No fixed code returned."))
    
    # Print applied fixes
    applied_fixes = fix_result.get('applied_fixes', [])
    if applied_fixes:
        print(f"\nApplied {len(applied_fixes)} fixes:")
        for i, fix in enumerate(applied_fixes, 1):
            print(f"{i}. {fix}")
    else:
        print("\nNo fixes were automatically applied.")

    # Print remaining issues
    remaining_issues = fix_result.get('issues_remaining', [])
    if remaining_issues:
        print(f"\n{len(remaining_issues)} issues remaining:")
        for i, issue in enumerate(remaining_issues, 1):
            location = issue.get('location', {})
            print(f"{i}. Line {location.get('row', '?')}, Col {location.get('column', '?')}: [{issue.get('code', 'N/A')}] {issue.get('message')}")
    else:
        print("\nNo remaining issues found after fixing.")

async def demo_test_execution(agent, project_path):
    """Demonstrate test execution capabilities."""
    print("\n=== Test Execution Demo ===\n")
    
    # Run tests
    print(f"Running tests in {project_path}...")
    result = await agent.run_and_analyze_tests(
        project_path=project_path,
        test_path="tests/test_sample",
        max_failures=2
    )
    
    # Print test results
    print(f"\nTest Status: {result.get('status')}")
    print(f"Summary: {result.get('summary')}")
    
    if result.get('passed_tests'):
        print("\nPassed Tests:")
        for test in result.get('passed_tests', []):
            print(f"✓ {test}")
    
    if result.get('failed_tests'):
        print("\nFailed Tests:")
        for test in result.get('failed_tests', []):
            print(f"✗ {test}")
    
    # Print analysis
    print("\nAnalysis:")
    print(f"Total Tests: {result.get('analysis', {}).get('total_tests')}")
    print(f"Pass Rate: {result.get('analysis', {}).get('pass_rate'):.2%}")
    
    print("\nRecommendations:")
    for rec in result.get('analysis', {}).get('recommendations', []):
        print(f"• {rec}")
    
    # Get last failed tests
    last_failed = await agent.get_last_failed_tests()
    if last_failed:
        print("\nLast Failed Tests:")
        for test in last_failed:
            print(f"- {test}")

async def main():
    """Run the MCP Enhanced Agent demo."""
    parser = argparse.ArgumentParser(description='MCP Enhanced Agent Demo')
    parser.add_argument('--code-server', type=str, help='MCP Code Server URL')
    parser.add_argument('--test-server', type=str, help='MCP Test Server URL')
    parser.add_argument('--project-path', type=str, default=os.path.abspath(os.path.join(os.path.dirname(__file__), '..')),
                        help='Path to the project for test execution')
    args = parser.parse_args()

    # Create the enhanced agent
    agent = MCPEnhancedAgent(
        code_server_url=args.code_server,
        test_server_url=args.test_server
    )
    
    try:
        # Demo code analysis capabilities
        await demo_code_analysis(agent)
        
        # Demo test execution capabilities
        await demo_test_execution(agent, args.project_path)
    
    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure MCP code and test servers are running.")
        print("You can start them with:")
        print("  1. python agents/mcp_code_server.py")
        print("  2. python agents/mcp_test_server.py")
        
    print("\nDemo complete!")

if __name__ == "__main__":
    asyncio.run(main()) 