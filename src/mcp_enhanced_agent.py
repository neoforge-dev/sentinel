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
        test_server_url: str = "http://localhost:8001",
    ):
        """
        Initialize the MCP Enhanced Agent.
        
        Args:
            code_server_url: URL of the MCP Code Server
            test_server_url: URL of the MCP Test Server
        """
        self.code_server_url = code_server_url
        self.test_server_url = test_server_url
        self.session = None
        logger.info(f"Initialized MCPEnhancedAgent with code server at {code_server_url} "
                   f"and test server at {test_server_url}")
    
    async def __aenter__(self):
        """Set up the aiohttp session for the context manager."""
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up the aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def _ensure_session(self):
        """Ensure an aiohttp session exists."""
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def _make_request(
        self, 
        method: str, 
        url: str, 
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to an MCP server.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL for the request
            data: Optional JSON data for POST requests
            headers: Optional HTTP headers
            
        Returns:
            Dictionary containing the response data
        """
        await self._ensure_session()
        
        default_headers = {'Content-Type': 'application/json'}
        if headers:
            default_headers.update(headers)
        
        try:
            if method.upper() == 'GET':
                async with self.session.get(url, headers=default_headers) as response:
                    response.raise_for_status()
                    return await response.json()
            elif method.upper() == 'POST':
                async with self.session.post(url, json=data, headers=default_headers) as response:
                    response.raise_for_status()
                    return await response.json()
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error when making {method} request to {url}: {str(e)}")
            return {"error": str(e), "status": "error"}
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON response from {url}")
            return {"error": "Invalid JSON response", "status": "error"}
        except Exception as e:
            logger.error(f"Unexpected error with {method} request to {url}: {str(e)}")
            return {"error": str(e), "status": "error"}
    
    # Code Server Methods
    
    async def analyze_code(self, code: str, language: str = "python") -> Dict[str, Any]:
        """
        Analyze code for issues using the MCP Code Server.
        
        Args:
            code: The code to analyze
            language: Programming language of the code (default: python)
            
        Returns:
            Dictionary with analysis results including issues and recommendations
        """
        url = f"{self.code_server_url}/analyze"
        data = {"code": code, "language": language}
        return await self._make_request("POST", url, data)
    
    async def format_code(self, code: str, language: str = "python") -> Dict[str, Any]:
        """
        Format code according to language-specific guidelines.
        
        Args:
            code: The code to format
            language: Programming language of the code (default: python)
            
        Returns:
            Dictionary with the formatted code
        """
        url = f"{self.code_server_url}/format"
        data = {"code": code, "language": language}
        return await self._make_request("POST", url, data)
    
    async def analyze_and_fix_code(self, code: str, language: str = "python") -> Dict[str, Any]:
        """
        Analyze code, attempt to automatically fix issues, and return the results.
        
        Args:
            code: The code to analyze and fix
            language: Programming language of the code (default: python)
            
        Returns:
            Dictionary containing the fixed code, remaining issues, and applied fixes.
        """
        url = f"{self.code_server_url}/fix"
        data = {"code": code, "language": language}
        return await self._make_request("POST", url, data)
    
    async def store_code_snippet(
        self, 
        code: str, 
        language: str = "python", 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Store a code snippet for later retrieval.
        
        Args:
            code: The code snippet to store
            language: Programming language of the code (default: python)
            metadata: Optional metadata to associate with the snippet
            
        Returns:
            Dictionary with the snippet ID
        """
        url = f"{self.code_server_url}/store"
        data = {
            "code": code,
            "language": language
        }
        if metadata:
            data["metadata"] = metadata
        return await self._make_request("POST", url, data)
    
    async def get_code_snippet(self, snippet_id: str) -> Dict[str, Any]:
        """
        Retrieve a stored code snippet.
        
        Args:
            snippet_id: ID of the snippet to retrieve
            
        Returns:
            Dictionary with the code snippet and metadata
        """
        url = f"{self.code_server_url}/snippet/{snippet_id}"
        return await self._make_request("GET", url)
    
    # Test Server Methods
    
    async def run_tests(
        self,
        project_path: str,
        test_path: Optional[str] = None,
        runner: str = "pytest",
        mode: str = "local",
        max_failures: Optional[int] = None,
        run_last_failed: bool = False,
        timeout: int = 60,
        max_tokens: int = 4000,
        docker_image: Optional[str] = None,
        additional_args: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Run tests in a local Python project.
        
        Args:
            project_path: Path to the project root
            test_path: Path to tests (relative to project_path)
            runner: Test runner to use (pytest, unittest, uv)
            mode: Execution mode (local, docker)
            max_failures: Stop after this many failures
            run_last_failed: Only run tests that failed in the last run
            timeout: Maximum execution time in seconds
            max_tokens: Maximum tokens for output
            docker_image: Docker image to use if mode is 'docker'
            additional_args: Additional arguments to pass to the test runner
            
        Returns:
            Dictionary with test results
        """
        url = f"{self.test_server_url}/run"
        data = {
            "project_path": project_path,
            "runner": runner,
            "mode": mode,
            "timeout": timeout,
            "max_tokens": max_tokens
        }
        
        if test_path:
            data["test_path"] = test_path
        if max_failures is not None:
            data["max_failures"] = max_failures
        if run_last_failed:
            data["run_last_failed"] = run_last_failed
        if docker_image:
            data["docker_image"] = docker_image
        if additional_args:
            data["additional_args"] = additional_args
            
        return await self._make_request("POST", url, data)
    
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


if __name__ == "__main__":
    # Simple usage example
    async def main():
        async with MCPEnhancedAgent() as agent:
            # Analyze a simple code snippet
            result = await agent.analyze_code("def foo():\n  x = 1 + 2\n  return x")
            print(f"Analysis result: {json.dumps(result, indent=2)}")
            
    asyncio.run(main()) 