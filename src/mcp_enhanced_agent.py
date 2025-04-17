#!/usr/bin/env python3
"""
MCP Enhanced Agent.

This module provides the MCPEnhancedAgent class that integrates both
the MCP Code Server and MCP Test Server into a unified interface.
"""

import os
import sys
import json
import asyncio
import logging
from typing import Any, Dict, List, Optional, Union
import aiohttp
from collections.abc import Callable

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MCPEnhancedAgent")

class MCPEnhancedAgent:
    """
    Enhanced agent that integrates with MCP Code and Test servers.
    
    This agent provides a unified interface to access code analysis,
    formatting, and test execution capabilities.
    """
    
    def __init__(
        self,
        code_server_url: str = "http://localhost:8000",
        test_server_url: str = "http://localhost:8082",
        api_key: Optional[str] = None,
        session: Optional[aiohttp.ClientSession] = None
    ):
        """Initialize the agent with server URLs and optional session."""
        self.code_server_url = code_server_url
        self.test_server_url = test_server_url
        self.api_key = api_key
        self.default_headers = {'Content-Type': 'application/json'} # Initialize default headers
        
        if session:
            self.session = session
            self._owns_session = False
            logger.info("Using provided aiohttp ClientSession.")
        else:
            # Create a default session if none is provided
            self.session = aiohttp.ClientSession()
            self._owns_session = True
            logger.info("Created internal aiohttp ClientSession.")
            
        logger.info(f"Initialized MCPEnhancedAgent with code server at {self.code_server_url} and test server at {self.test_server_url}")
    
    async def close(self):
        """Closes the internally managed session, if it exists and is owned by the agent."""
        if self.session and self._owns_session:
            await self.session.close()
            self.session = None
            self._owns_session = False
            logger.info("Closed internally owned aiohttp ClientSession.")
        elif not self._owns_session:
            logger.debug("Agent does not own the session, not closing it.")
        else:
            logger.debug("No active session to close.")
    
    async def _make_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """Makes an async HTTP request and handles common responses."""
        headers = self.default_headers.copy()
        if self.api_key:
            headers['X-API-Key'] = self.api_key
        
        request_kwargs = {"headers": headers, **kwargs}
        
        try:
            async with self.session.request(method, url, **request_kwargs) as response:
                # Try to parse JSON regardless of status code initially
                try:
                    json_data = await response.json()
                except (aiohttp.ContentTypeError, json.JSONDecodeError):
                    # If JSON parsing fails, read text and store it
                    text_data = await response.text()
                    json_data = {"error": "Failed to decode JSON", "status_code": response.status, "text": text_data}

                # Combine status code with JSON data (or error data)
                result_data = {"status_code": response.status, **json_data}
                
                # Log non-2xx responses
                if not 200 <= response.status < 300:
                    logger.error(f"HTTP error: {response.status} {response.reason} for {method} {url}. Response: {result_data}")
                    # Optionally raise an exception here for critical errors, 
                    # but for now, returning the data allows calling methods to decide.

                return result_data
        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error when making {method} request to {url}: {e}")
            return {"status_code": 503, "error": f"HTTP client error: {e}"} # 503 Service Unavailable
        except Exception as e:
            logger.error(f"Unexpected error during {method} request to {url}: {e}", exc_info=True)
            return {"status_code": 500, "error": f"Unexpected agent error: {e}"}
    
    # Code Server Methods
    
    async def analyze_code(self, code: str, language: str = "python") -> Dict[str, Any]:
        """Analyzes code using the code server."""
        url = f"{self.code_server_url}/analyze"
        payload = {"code": code, "language": language}
        # _make_request now includes status_code and potential error fields
        return await self._make_request("POST", url, json=payload)
    
    async def format_code(self, code: str, language: str = "python") -> Dict[str, Any]:
        """Formats code using the code server."""
        url = f"{self.code_server_url}/format"
        payload = {"code": code, "language": language}
        return await self._make_request("POST", url, json=payload)
    
    async def analyze_and_fix_code(self, code: str, language: str = "python") -> Dict[str, Any]:
        """Fixes code using the code server."""
        url = f"{self.code_server_url}/fix"
        payload = {"code": code, "language": language}
        return await self._make_request("POST", url, json=payload)
    
    async def store_code_snippet(
        self, 
        code: str, 
        language: str = "python", 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Stores a code snippet via the code server."""
        url = f"{self.code_server_url}/snippets" # Corrected endpoint
        payload = {"code": code, "language": language, "metadata": metadata or {}}
        return await self._make_request("POST", url, json=payload)
    
    async def get_code_snippet(self, snippet_id: str) -> Dict[str, Any]:
        """Retrieves a code snippet from the code server."""
        url = f"{self.code_server_url}/snippets/{snippet_id}" # Corrected endpoint
        return await self._make_request("GET", url)
    
    # Test Server Methods
    
    async def run_tests(
        self,
        project_path: str,
        test_path: str = ".",
        runner: str = "pytest",
        mode: str = "local",
        max_failures: Optional[int] = None,
        run_last_failed: bool = False,
        timeout: int = 60,
        max_tokens: int = 4000,
        docker_image: Optional[str] = None,
        additional_args: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Runs tests using the test server."""
        url = f"{self.test_server_url}/run-tests"
        payload = {
            "project_path": project_path,
            "test_path": test_path,
            "runner": runner,
            "mode": mode,
            "timeout": timeout,
            "max_tokens": max_tokens
        }
        
        if max_failures is not None:
            payload["max_failures"] = max_failures
        if run_last_failed:
            payload["run_last_failed"] = run_last_failed
        if docker_image:
            payload["docker_image"] = docker_image
        if additional_args:
            payload["additional_args"] = additional_args
            
        return await self._make_request("POST", url, json=payload)
    
    async def run_and_analyze_tests(
        self,
        project_path: str,
        test_path: Optional[str] = None,
        runner: str = "pytest",
        mode: str = "local",
        max_failures: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Run tests and provide analysis of the results.
        
        Args:
            project_path: Path to the project root
            test_path: Path to tests (relative to project_path)
            runner: Test runner to use (pytest, unittest, uv)
            mode: Execution mode (local, docker)
            max_failures: Stop after this many failures
            **kwargs: Additional arguments passed to run_tests
            
        Returns:
            Dictionary with test results and analysis
        """
        # First run the tests
        test_result = await self.run_tests(
            project_path=project_path,
            test_path=test_path,
            runner=runner,
            mode=mode,
            max_failures=max_failures,
            **kwargs
        )
        
        # Then analyze the results
        if test_result.get("status") == "error":
            return {
                "status": "error",
                "error": test_result.get("error", "Unknown error"),
                "analysis": "Could not analyze tests due to execution error."
            }
        
        # Perform a simple analysis
        failed_count = len(test_result.get("failed_tests", []))
        passed_count = len(test_result.get("passed_tests", []))
        skipped_count = len(test_result.get("skipped_tests", []))
        total_count = failed_count + passed_count + skipped_count
        
        analysis = "Test Results Analysis:\n"
        analysis += f"- Total tests: {total_count}\n"
        
        if total_count > 0:
            passed_pct = (passed_count / total_count) * 100
            failed_pct = (failed_count / total_count) * 100
            skipped_pct = (skipped_count / total_count) * 100
        else:
            passed_pct = failed_pct = skipped_pct = 0
            
        analysis += f"- Passed: {passed_count} ({passed_pct:.1f}%)\n"
        analysis += f"- Failed: {failed_count} ({failed_pct:.1f}%)\n"
        analysis += f"- Skipped: {skipped_count} ({skipped_pct:.1f}%)\n"
        
        if failed_count > 0:
            analysis += "\nFailed Tests:\n"
            for i, test in enumerate(test_result.get("failed_tests", []), 1):
                analysis += f"{i}. {test}\n"
                
            analysis += "\nRecommended Action: Fix the failed tests before proceeding with development."
        else:
            analysis += "\nAll tests passing! The codebase is in good health."
            
        test_result["analysis"] = analysis
        return test_result
    
    async def get_test_result(self, result_id: str) -> Dict[str, Any]:
        """
        Get the result of a test execution.
        
        Args:
            result_id: ID of the test execution
            
        Returns:
            Dictionary with test results
        """
        url = f"{self.test_server_url}/result/{result_id}"
        return await self._make_request("GET", url)
    
    async def list_test_results(self) -> List[str]:
        """
        List all test execution IDs.
        
        Returns:
            List of test execution IDs
        """
        url = f"{self.test_server_url}/results"
        response = await self._make_request("GET", url)
        return response.get("result_ids", [])
    
    async def get_last_failed_tests(self) -> List[str]:
        """
        Get a list of tests that failed in the most recent execution.
        
        Returns:
            List of test names that failed
        """
        url = f"{self.test_server_url}/failed"
        response = await self._make_request("GET", url)
        return response.get("failed_tests", [])

    # --- Tool Management --- 
    def register_tool(self, name: str, function: Callable):
        """Register an external function as a tool."""
        if not callable(function):
             raise TypeError(f"Tool function '{name}' must be callable.")
        if name in self.tools:
             logger.warning(f"Overwriting existing tool: {name}")
        self.tools[name] = function
        logger.info(f"Registered tool: {name}")

    async def execute_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        Execute a registered tool by name.
        
        Args:
            tool_name: The name of the tool to execute.
            **kwargs: Arguments to pass to the tool function.
            
        Returns:
            Dictionary containing the tool's execution result or an error.
        """
        if tool_name not in self.tools:
            logger.error(f"Tool not found: {tool_name}")
            return {"success": False, "error": f"Tool '{tool_name}' not found."}
        
        tool_func = self.tools[tool_name]
        try:
            # Check if the function is async
            if asyncio.iscoroutinefunction(tool_func):
                result = await tool_func(**kwargs)
            else:
                # Run synchronous function in thread pool executor if available?
                # For simplicity now, run directly (might block event loop!)
                # Consider using asyncio.to_thread in Python 3.9+
                result = tool_func(**kwargs)
                
            # Assume tool functions return a dictionary or serializable result
            # If they return simple types, wrap them
            if not isinstance(result, dict):
                 result = {"result": result}
                 
            return {"success": True, "tool_name": tool_name, "result": result}
        
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
            return {"success": False, "tool_name": tool_name, "error": str(e)}


if __name__ == "__main__":
    # Simple usage example
    async def main():
        async with MCPEnhancedAgent() as agent:
            # Analyze a simple code snippet
            result = await agent.analyze_code("def foo():\n  x = 1 + 2\n  return x")
            print(f"Analysis result: {json.dumps(result, indent=2)}")
            
    asyncio.run(main()) 