#!/usr/bin/env python3
"""
MCP Agent Plugin.

This plugin connects the main agent with MCP (Model Code Plugin) services,
integrating code analysis and test execution capabilities.
"""

import os
import sys
import asyncio
import logging
from typing import Dict, List, Any, Optional, Union

# Add the parent directory to the path to import the MCPEnhancedAgent
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the MCPEnhancedAgent
from src.mcp_enhanced_agent import MCPEnhancedAgent

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize the MCP enhanced agent
mcp_agent = MCPEnhancedAgent(
    code_server_url=os.environ.get("MCP_CODE_SERVER_URL", "http://localhost:8000"),
    test_server_url=os.environ.get("MCP_TEST_SERVER_URL", "http://localhost:8001")
)

# Define the agent tool functions
async def analyze_code(code: str) -> Dict[str, Any]:
    """
    Analyze code for issues.
    
    Args:
        code: The code to analyze
        
    Returns:
        Analysis results as a dictionary
    """
    return await mcp_agent.analyze_code(code)

async def format_code(code: str, language: str = "python") -> Dict[str, Any]:
    """
    Format code according to language-specific style guidelines.
    
    Args:
        code: The code to format
        language: The programming language of the code
        
    Returns:
        Formatted code as a dictionary
    """
    return await mcp_agent.format_code(code, language)

async def analyze_and_fix_code(code: str) -> Dict[str, Any]:
    """
    Analyze code and provide fixes for issues.
    
    Args:
        code: The code to analyze and fix
        
    Returns:
        Dictionary with original code, fixed code, and issue counts
    """
    return await mcp_agent.analyze_and_fix_code(code)

async def store_code_snippet(code: str, language: str = "python") -> Dict[str, Any]:
    """
    Store a code snippet for later retrieval.
    
    Args:
        code: The code snippet to store
        language: The programming language of the code
        
    Returns:
        Dictionary with the snippet ID
    """
    return await mcp_agent.store_code_snippet(code, language)

async def get_code_snippet(snippet_id: str) -> Dict[str, Any]:
    """
    Retrieve a stored code snippet.
    
    Args:
        snippet_id: The ID of the snippet to retrieve
        
    Returns:
        Dictionary with the code snippet
    """
    return await mcp_agent.get_code_snippet(snippet_id)

async def run_tests(
    project_path: str,
    test_path: str = None,
    runner: str = "pytest",
    mode: str = "local",
    max_failures: int = None,
    run_last_failed: bool = False,
    timeout: int = 30,
    max_tokens: int = 4000,
    docker_image: str = None,
    additional_args: List[str] = None
) -> Dict[str, Any]:
    """
    Run tests in a local Python project.
    
    Args:
        project_path: Path to the project root
        test_path: Path to tests directory or specific test file
        runner: Test runner to use (pytest, unittest, or uv)
        mode: Execution mode (local or docker)
        max_failures: Maximum number of failures before stopping
        run_last_failed: Whether to run only the last failed tests
        timeout: Timeout in seconds for test execution
        max_tokens: Maximum token count for output
        docker_image: Docker image to use if mode is docker
        additional_args: Additional arguments to pass to the test runner
        
    Returns:
        Dictionary with test results
    """
    return await mcp_agent.run_tests(
        project_path=project_path,
        test_path=test_path,
        runner=runner,
        mode=mode,
        max_failures=max_failures,
        run_last_failed=run_last_failed,
        timeout=timeout,
        max_tokens=max_tokens,
        docker_image=docker_image,
        additional_args=additional_args
    )

async def run_and_analyze_tests(
    project_path: str,
    test_path: str = None,
    runner: str = "pytest",
    mode: str = "local",
    max_failures: int = None,
    run_last_failed: bool = False,
    timeout: int = 30,
    max_tokens: int = 4000,
    docker_image: str = None,
    additional_args: List[str] = None
) -> Dict[str, Any]:
    """
    Run tests and provide analysis of results.
    
    Args:
        project_path: Path to the project root
        test_path: Path to tests directory or specific test file
        runner: Test runner to use (pytest, unittest, or uv)
        mode: Execution mode (local or docker)
        max_failures: Maximum number of failures before stopping
        run_last_failed: Whether to run only the last failed tests
        timeout: Timeout in seconds for test execution
        max_tokens: Maximum token count for output
        docker_image: Docker image to use if mode is docker
        additional_args: Additional arguments to pass to the test runner
        
    Returns:
        Dictionary with test results and analysis
    """
    return await mcp_agent.run_and_analyze_tests(
        project_path=project_path,
        test_path=test_path,
        runner=runner,
        mode=mode,
        max_failures=max_failures,
        run_last_failed=run_last_failed,
        timeout=timeout,
        max_tokens=max_tokens,
        docker_image=docker_image,
        additional_args=additional_args
    )

async def get_test_result(result_id: str) -> Dict[str, Any]:
    """
    Get the result of a test execution.
    
    Args:
        result_id: The ID of the test execution
        
    Returns:
        Dictionary with test results
    """
    return await mcp_agent.get_test_result(result_id)

async def list_test_results() -> List[str]:
    """
    List all test execution IDs.
    
    Returns:
        List of test execution IDs
    """
    return await mcp_agent.list_test_results()

async def get_last_failed_tests() -> List[str]:
    """
    Get a list of tests that failed in the most recent execution.
    
    Returns:
        List of test names that failed
    """
    return await mcp_agent.get_last_failed_tests()

def register_mcp_tools(agent):
    """
    Register MCP tools with the main agent.
    
    Args:
        agent: The agent to register the tools with
    """
    # Register code analysis tools
    agent.register_tool("analyze_code", analyze_code)
    agent.register_tool("format_code", format_code)
    agent.register_tool("analyze_and_fix_code", analyze_and_fix_code)
    agent.register_tool("store_code_snippet", store_code_snippet)
    agent.register_tool("get_code_snippet", get_code_snippet)
    
    # Register test execution tools
    agent.register_tool("run_tests", run_tests)
    agent.register_tool("run_and_analyze_tests", run_and_analyze_tests)
    agent.register_tool("get_test_result", get_test_result)
    agent.register_tool("list_test_results", list_test_results)
    agent.register_tool("get_last_failed_tests", get_last_failed_tests)
    
    print(f"Registered {10} MCP tools with the agent")

# Example usage
if __name__ == "__main__":
    # Create a mock agent for demonstration
    class MockAgent:
        def __init__(self):
            self.tools = {}
            
        def register_tool(self, name, tool_func):
            self.tools[name] = tool_func
            
        def get_registered_tools(self):
            return list(self.tools.keys())
    
    # Create a mock agent
    mock_agent = MockAgent()
    
    # Register MCP tools
    register_mcp_tools(mock_agent)
    
    # Print registered tools
    print(f"Registered {len(mock_agent.get_registered_tools())} tools:")
    for tool_name in mock_agent.get_registered_tools():
        print(f"- {tool_name}")
        
    print("\nMCP Agent Plugin is ready for use!") 