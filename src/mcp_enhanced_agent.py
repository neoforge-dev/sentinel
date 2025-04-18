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
        session: Optional[aiohttp.ClientSession] = None,
        retry_attempts: int = 3,
        retry_delay: float = 1.0
    ):
        """Initialize the agent with server URLs and optional session."""
        self.code_server_url = code_server_url.rstrip('/')
        self.test_server_url = test_server_url.rstrip('/')
        self.api_key = api_key
        # Use provided session or create a new one if None
        self._session_owner = session is None
        self.session = session if session else aiohttp.ClientSession()
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        logger.info(f"Initialized MCPEnhancedAgent with code server at {self.code_server_url} and test server at {self.test_server_url}")
    
    async def close(self):
        """Closes the internally managed session, if it exists and is owned by the agent."""
        if self.session and self._session_owner:
            await self.session.close()
            self.session = None
            self._session_owner = False
            logger.info("Closed internally owned aiohttp ClientSession.")
        elif not self._session_owner:
            logger.debug("Agent does not own the session, not closing it.")
        else:
            logger.debug("No active session to close.")
    
    async def _make_request(self, method: str, server_type: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        base_url = self.code_server_url if server_type == "code" else self.test_server_url
        url = f"{base_url}/{endpoint.lstrip('/')}"
        headers = kwargs.pop("headers", {})
        headers["X-API-Key"] = self.api_key
        
        request_kwargs = {
            "headers": headers,
            "timeout": aiohttp.ClientTimeout(total=60) # Add a default timeout
        }
        if method.upper() == "POST" and "json" in kwargs:
             request_kwargs["json"] = kwargs["json"]
             
        current_attempt = 0
        while current_attempt < self.retry_attempts:
            current_attempt += 1
            try:
                async with self.session.request(method, url, **request_kwargs) as response:
                    try:
                         response_data = await response.json()
                         # Return a dictionary including status code and data
                         return {"status_code": response.status, **response_data}
                    except (aiohttp.ContentTypeError, json.JSONDecodeError):
                         # Handle non-JSON responses or empty bodies
                         response_text = await response.text()
                         logger.warning(f"Non-JSON response received from {url} (Status: {response.status}). Body: {response_text[:100]}...")
                         return {"status_code": response.status, "detail": response_text}
                         
            except aiohttp.ClientConnectorError as e:
                 logger.error(f"Connection error during {method} request to {url} (Attempt {current_attempt}): {e}")
                 if current_attempt == self.retry_attempts:
                      return {"status_code": 503, "error": "Service Unavailable", "detail": str(e)}
            except asyncio.TimeoutError as e:
                 logger.error(f"Timeout during {method} request to {url} (Attempt {current_attempt})")
                 if current_attempt == self.retry_attempts:
                      return {"status_code": 504, "error": "Gateway Timeout", "detail": "Request timed out"}
            except aiohttp.ClientResponseError as e:
                 logger.error(f"HTTP error during {method} request to {url} (Attempt {current_attempt}): {e.status} {e.message}")
                 # Return status code from the error
                 return {"status_code": e.status, "error": e.message, "detail": str(e)}
            except Exception as e:
                 logger.exception(f"Unexpected error during {method} request to {url} (Attempt {current_attempt}): {e}")
                 if current_attempt == self.retry_attempts:
                     # Return a generic 500 error for unexpected issues
                      return {"status_code": 500, "error": "Internal Server Error", "detail": str(e)}
            
            # Wait before retrying if not the last attempt
            if current_attempt < self.retry_attempts:
                await asyncio.sleep(self.retry_delay)

        # This part should ideally not be reached if retry logic is sound.
        logger.error(f"Request failed after {self.retry_attempts} attempts for {url}")
        return {"status_code": 500, "error": "Request Failed", "detail": f"Request failed after {self.retry_attempts} attempts."}
    
    # Code Server Methods
    
    async def analyze_code(self, code: str, language: str = "python") -> Dict[str, Any]:
        """Analyzes code using the code server."""
        return await self._make_request("POST", "code", "analyze", json={"code": code, "language": language})
    
    async def format_code(self, code: str, language: str = "python") -> Dict[str, Any]:
        """Formats code using the code server."""
        return await self._make_request("POST", "code", "format", json={"code": code, "language": language})
    
    async def analyze_and_fix_code(self, code: str, language: str = "python") -> Dict[str, Any]:
        """Fixes code using the code server."""
        return await self._make_request("POST", "code", "fix", json={"code": code, "language": language})
    
    async def store_code_snippet(
        self, 
        code: str, 
        language: str = "python", 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Stores a code snippet via the code server."""
        return await self._make_request("POST", "code", "snippets", json={"code": code, "language": language, "metadata": metadata or {}})
    
    async def get_code_snippet(self, snippet_id: str) -> Dict[str, Any]:
        """Retrieves a code snippet from the code server."""
        return await self._make_request("GET", "code", f"snippets/{snippet_id}")
    
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
        return await self._make_request("POST", "test", "run-tests", json={
            "project_path": project_path,
            "test_path": test_path,
            "runner": runner,
            "mode": mode,
            "timeout": timeout,
            "max_tokens": max_tokens
        })
    
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
        return await self._make_request("GET", "test", f"result/{result_id}")
    
    async def list_test_results(self) -> List[str]:
        """
        List all test execution IDs.
        
        Returns:
            List of test execution IDs
        """
        response = await self._make_request("GET", "test", "results")
        return response.get("result_ids", [])
    
    async def get_last_failed_tests(self) -> List[str]:
        """
        Get a list of tests that failed in the most recent execution.
        
        Returns:
            List of test names that failed
        """
        response = await self._make_request("GET", "test", "failed")
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