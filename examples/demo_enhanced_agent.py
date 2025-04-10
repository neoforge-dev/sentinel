#!/usr/bin/env python3
"""
Demo script for the MCPEnhancedAgent

This script demonstrates how to use the MCPEnhancedAgent with both code analysis
and test runner capabilities in a programmatic way.

Usage:
    python examples/demo_enhanced_agent.py
"""

import os
import sys
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from agents.mcp_enhanced_agent import MCPEnhancedAgent
except ImportError as e:
    print(f"Error: Could not import required modules: {e}")
    print("Make sure you're running from the project root.")
    sys.exit(1)


def separator(title: str):
    """Print a separator with a title"""
    print("\n" + "=" * 80)
    print(f" {title} ".center(80, "="))
    print("=" * 80 + "\n")


def demo_code_analysis():
    """Demonstrate code analysis capabilities"""
    separator("Code Analysis Demo")
    
    # Sample code with issues
    sample_code = """
def calculate_sum(numbers):
    total = 0
    for num in numbers:
        total = total + num
    
    unused_var = "This is never used"
    
    return total

def greet(name):
    message = "Hello, " + name + "!"
    print (message)
    return message
    """
    
    print("Sample code:")
    print(sample_code)
    
    # Create agent with only code analysis feature
    print("\nInitializing agent with code analysis capabilities...")
    agent = MCPEnhancedAgent(
        model="mistral:7b",
        mcp_features=["code"],
        debug=True
    )
    
    print("\nAnalyzing code...")
    analysis_result = agent.analyze_code(sample_code)
    
    if analysis_result.get("success", False):
        issues = analysis_result.get("issues", [])
        if issues:
            print(f"\nFound {len(issues)} issues:")
            for i, issue in enumerate(issues, 1):
                print(f"{i}. Line {issue.get('location', {}).get('row', '?')}: "
                      f"{issue.get('message', 'Unknown issue')}")
        else:
            print("No issues found!")
            
        print("\nFormatting code...")
        format_result = agent.format_code(sample_code)
        
        if format_result.get("success", False) and format_result.get("formatted_code"):
            print("\nFormatted code:")
            print(format_result["formatted_code"])
    else:
        print(f"Error: {analysis_result.get('message', 'Unknown error')}")


def demo_test_runner():
    """Demonstrate test runner capabilities"""
    separator("Test Runner Demo")
    
    # Create agent with only test runner feature
    print("Initializing agent with test runner capabilities...")
    agent = MCPEnhancedAgent(
        model="mistral:7b",
        mcp_features=["test"],
        debug=True
    )
    
    # Path to the test sample directory
    test_path = os.path.join("tests", "test_sample")
    
    print(f"\nRunning tests in {test_path}...")
    result = agent.run_tests(
        project_path=".",
        test_path=test_path,
        runner="unittest",
        mode="local"
    )
    
    if result.get("success", False):
        test_id = result.get("test_id")
        if test_id:
            print(f"\nTest ID: {test_id}")
            
            print("\nRetrieving test result...")
            test_result = agent.execute_tool("get_test_result", {"test_id": test_id})
            
            if test_result.get("success", False):
                print("\nFormatting test result...")
                formatted = agent.execute_tool("format_test_result", {"result": test_result})
                
                print("\nTest Results:")
                print(formatted)
                
                # Get list of last failed tests
                print("\nLast failed tests:")
                failed_tests = agent.execute_tool("get_last_failed_tests", {})
                if failed_tests.get("success", False):
                    for test in failed_tests.get("result", []):
                        print(f"- {test}")
                else:
                    print("Error retrieving failed tests")
            else:
                print(f"Error: {test_result.get('error', 'Unknown error')}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")


def demo_code_generation():
    """Demonstrate code generation with analysis"""
    separator("Code Generation With Analysis Demo")
    
    # Create agent with code analysis feature
    print("Initializing agent with code analysis capabilities...")
    agent = MCPEnhancedAgent(
        model="mistral:7b",
        mcp_features=["code"],
        debug=True
    )
    
    code_description = """
    Create a Python function that fetches data from a REST API using the requests library.
    The function should:
    1. Accept a URL parameter
    2. Handle errors gracefully
    3. Return the JSON response if successful
    4. Include proper type hints
    """
    
    print("\nCode description:")
    print(code_description)
    
    print("\nGenerating and analyzing code...")
    result = agent.generate_and_analyze_code(code_description)
    
    if result.get("success", False):
        print("\nGenerated code:")
        print(result.get("original_code", ""))
        
        print("\nFormatted code:")
        print(result.get("formatted_code", ""))
        
        issues = result.get("issues", [])
        if issues:
            print(f"\nFound {len(issues)} issues:")
            for i, issue in enumerate(issues, 1):
                print(f"{i}. Line {issue.get('location', {}).get('row', '?')}: "
                      f"{issue.get('message', 'Unknown issue')}")
        else:
            print("\nNo issues found in the generated code!")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")


def main():
    """Run all demos"""
    print("Demo of MCPEnhancedAgent capabilities")
    
    try:
        # Run code analysis demo
        demo_code_analysis()
        
        # Run test runner demo
        demo_test_runner()
        
        # Run code generation demo
        demo_code_generation()
        
        separator("Demo Complete")
        print("All demos completed successfully!")
        
    except Exception as e:
        import traceback
        print(f"Error during demo: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main() 