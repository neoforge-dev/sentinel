#!/usr/bin/env python3
"""
MCP Enhanced Agent Plugin

This plugin integrates the MCP Enhanced Agent with the main agent framework,
providing tools for code analysis, testing, and improvement.

Dependencies:
- aiohttp
- fastapi
- tiktoken
"""

import os
import sys
import json
import logging
from typing import Any, Dict, List, Optional, Callable, Union
import asyncio
import aiohttp

# Add the src directory to the path so we can import the MCP enhanced agent
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.mcp_enhanced_agent import MCPEnhancedAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("mcp_enhanced_plugin")

# Configuration
MCP_CODE_SERVER_URL = os.environ.get("MCP_CODE_SERVER_URL", "http://localhost:8081")
MCP_TEST_SERVER_URL = os.environ.get("MCP_TEST_SERVER_URL", "http://localhost:8082")
API_KEY = os.environ.get("MCP_API_KEY", "test-key") # Replace with your actual API key

# Initialize the enhanced agent
agent = MCPEnhancedAgent(
    code_server_url=MCP_CODE_SERVER_URL,
    test_server_url=MCP_TEST_SERVER_URL,
)

async def analyze_code(code: str, language: str = "python") -> Dict[str, Any]:
    """
    Analyze code for issues and return a detailed report.
    
    Args:
        code: The code to analyze
        language: The programming language of the code
        
    Returns:
        A dictionary containing analysis results
    """
    return await agent.analyze_code(code, language)

async def format_code(code: str, language: str = "python") -> Dict[str, Any]:
    """
    Format code according to language-specific style guides.
    
    Args:
        code: The code to format
        language: The programming language of the code
        
    Returns:
        A dictionary containing the formatted code
    """
    return await agent.format_code(code, language)

async def analyze_and_fix_code(code: str, language: str = "python") -> Dict[str, Any]:
    """
    Analyze code for issues, fix them automatically when possible, and return both
    analysis and fixed code.
    
    Args:
        code: The code to analyze and fix
        language: The programming language of the code
        
    Returns:
        A dictionary containing analysis results and fixed code
    """
    return await agent.analyze_and_fix_code(code, language)

async def store_code_snippet(code: str, name: str, language: str = "python") -> Dict[str, Any]:
    """
    Store a code snippet for future reference.
    
    Args:
        code: The code snippet to store
        name: A name to identify the snippet
        language: The programming language of the code
        
    Returns:
        A dictionary containing storage confirmation
    """
    return await agent.store_snippet(code, name, language)

async def run_tests(
    project_path: str,
    test_path: Optional[str] = None,
    runner: str = "pytest",
    mode: str = "local",
    max_failures: Optional[int] = None,
    run_last_failed: bool = False,
    docker_image: Optional[str] = None,
    additional_args: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Run tests for a project and return the results.
    
    Args:
        project_path: Path to the project
        test_path: Path to tests (relative to project_path)
        runner: Test runner to use (pytest, unittest, uv)
        mode: Execution mode (local or docker)
        max_failures: Maximum number of failures before stopping
        run_last_failed: Whether to run only tests that failed last time
        docker_image: Docker image to use (if mode is docker)
        additional_args: Additional arguments to pass to the test runner
        
    Returns:
        A dictionary containing test results
    """
    return await agent.run_tests(
        project_path=project_path,
        test_path=test_path,
        runner=runner,
        mode=mode,
        max_failures=max_failures,
        run_last_failed=run_last_failed,
        docker_image=docker_image,
        additional_args=additional_args or [],
    )

async def analyze_test_results(test_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze test results and provide insights.
    
    Args:
        test_result: The test result to analyze
        
    Returns:
        A dictionary containing the analysis
    """
    return await agent.analyze_test_results(test_result)

async def run_and_analyze_tests(**kwargs) -> Dict[str, Any]:
    """
    Run tests and analyze the results in one step.
    
    Args:
        **kwargs: Arguments to pass to run_tests
        
    Returns:
        A dictionary containing test results with analysis
    """
    return await agent.run_and_analyze_tests(**kwargs)

def register_mcp_tools(register_tool_fn: Callable) -> None:
    """
    Register all MCP tools with the agent.
    
    Args:
        register_tool_fn: Function to register a tool with the agent
    """
    register_tool_fn(
        "analyze_code",
        analyze_code,
        "Analyze code for issues and style violations",
    )
    
    register_tool_fn(
        "format_code",
        format_code,
        "Format code according to language-specific style guides",
    )
    
    register_tool_fn(
        "analyze_and_fix_code",
        analyze_and_fix_code,
        "Analyze code for issues and automatically fix them when possible",
    )
    
    register_tool_fn(
        "store_code_snippet",
        store_code_snippet,
        "Store a code snippet for future reference",
    )
    
    register_tool_fn(
        "run_tests",
        run_tests,
        "Run tests for a project and return the results",
    )
    
    register_tool_fn(
        "analyze_test_results",
        analyze_test_results,
        "Analyze test results and provide insights",
    )
    
    register_tool_fn(
        "run_and_analyze_tests",
        run_and_analyze_tests,
        "Run tests and analyze the results in one step",
    )
    
    logger.info("MCP Enhanced tools registered successfully")

if __name__ == "__main__":
    # Example usage
    async def main():
        # Test the code analysis
        sample_code = """
def add_numbers(a, b):
    return a+b  # Missing spaces around operator
        
def unused_function():
    x = 10  # Unused variable
    return None
"""
        
        print("Analyzing code...")
        result = await analyze_code(sample_code)
        print(json.dumps(result, indent=2))
        
        print("\nFormatting code...")
        result = await format_code(sample_code)
        print(json.dumps(result, indent=2))
        
        print("\nAnalyzing and fixing code...")
        result = await analyze_and_fix_code(sample_code)
        print(json.dumps(result, indent=2))
        
        # Uncomment to test the test runner (requires a valid project)
        """
        print("\nRunning tests...")
        result = await run_tests(
            project_path="./",
            test_path="tests/test_sample",
            runner="pytest",
            mode="local",
        )
        print(json.dumps(result, indent=2))
        
        print("\nAnalyzing test results...")
        result = await analyze_test_results(result)
        print(json.dumps(result, indent=2))
        """
    
    asyncio.run(main()) 