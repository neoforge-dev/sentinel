#!/usr/bin/env python3
"""
MCP Integration Module.

This module provides a unified interface for interacting with MCP servers
for code analysis and test execution.
"""

import os
import json
import asyncio
import aiohttp
from typing import Dict, List, Any, Optional, Union

# --- Default URLs (Consider moving to a config file) ---
DEFAULT_MCP_CODE_SERVER_URL = os.environ.get(
    "MCP_CODE_SERVER_URL", "http://localhost:8081"
)
DEFAULT_MCP_TEST_SERVER_URL = os.environ.get(
    "MCP_TEST_SERVER_URL", "http://localhost:8082"
)

class MCPIntegration:
    """Integration class for MCP servers."""
    
    def __init__(
        self, 
        code_server_url: str = None, 
        test_server_url: str = None
    ):
        """
        Initialize the MCP integration.
        
        Args:
            code_server_url: URL of the MCP code server
            test_server_url: URL of the MCP test server
        """
        self.code_server_url = code_server_url or DEFAULT_MCP_CODE_SERVER_URL
        self.test_server_url = test_server_url or DEFAULT_MCP_TEST_SERVER_URL
        self.session = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def close(self):
        """Close the aiohttp session."""
        if self.session is not None:
            await self.session.close()
            self.session = None
    
    async def _ensure_session(self):
        """Ensure that the aiohttp session exists."""
        if self.session is None:
            self.session = aiohttp.ClientSession()
    
    async def _post(self, url: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a POST request to the specified URL.
        
        Args:
            url: The URL to send the request to
            data: The data to send in the request
            
        Returns:
            The response data as a dictionary
        """
        await self._ensure_session()
        async with self.session.post(url, json=data) as response:
            response.raise_for_status()
            return await response.json()
    
    async def _get(self, url: str) -> Dict[str, Any]:
        """
        Send a GET request to the specified URL.
        
        Args:
            url: The URL to send the request to
            
        Returns:
            The response data as a dictionary
        """
        await self._ensure_session()
        async with self.session.get(url) as response:
            response.raise_for_status()
            return await response.json()
    
    # Code Server Methods
    
    async def analyze_code(
        self, 
        code: str, 
        language: str = "python"
    ) -> Dict[str, Any]:
        """
        Analyze code for issues.
        
        Args:
            code: The code to analyze
            language: The programming language of the code
            
        Returns:
            A dictionary containing analysis results
        """
        url = f"{self.code_server_url}/analyze"
        data = {"code": code, "language": language}
        return await self._post(url, data)
    
    async def format_code(
        self, 
        code: str, 
        language: str = "python"
    ) -> Dict[str, Any]:
        """
        Format code according to language-specific style guidelines.
        
        Args:
            code: The code to format
            language: The programming language of the code
            
        Returns:
            A dictionary containing the formatted code
        """
        url = f"{self.code_server_url}/format"
        data = {"code": code, "language": language}
        return await self._post(url, data)
    
    async def store_code_snippet(
        self, 
        code: str, 
        language: str = "python", 
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Store a code snippet for later retrieval.
        
        Args:
            code: The code to store
            language: The programming language of the code
            metadata: Additional metadata for the snippet
            
        Returns:
            A dictionary containing the snippet ID
        """
        url = f"{self.code_server_url}/store"
        data = {
            "code": code,
            "language": language,
            "metadata": metadata or {}
        }
        return await self._post(url, data)
    
    async def get_code_snippet(self, snippet_id: str) -> Dict[str, Any]:
        """
        Retrieve a stored code snippet.
        
        Args:
            snippet_id: The ID of the snippet to retrieve
            
        Returns:
            A dictionary containing the code snippet
        """
        url = f"{self.code_server_url}/snippets/{snippet_id}"
        return await self._get(url)
    
    # Test Server Methods
    
    async def run_tests(
        self,
        project_path: str,
        test_path: str = None,
        runner: str = "pytest",
        mode: str = "local",
        max_failures: int = 0,
        run_last_failed: bool = False,
        timeout: int = 60,
        max_tokens: int = 4000,
        docker_image: str = None,
        additional_args: List[str] = None
    ) -> Dict[str, Any]:
        """
        Run tests in a local Python project.
        
        Args:
            project_path: Path to the project
            test_path: Path to the tests to run (relative to project_path)
            runner: Test runner to use (pytest, unittest, or uv)
            mode: Execution mode (local or docker)
            max_failures: Maximum number of failures before stopping
            run_last_failed: Whether to run only the last failed tests
            timeout: Maximum time to wait for tests to complete (seconds)
            max_tokens: Maximum tokens in the output
            docker_image: Docker image to use (if mode is docker)
            additional_args: Additional arguments to pass to the test runner
            
        Returns:
            A dictionary containing test results
        """
        url = f"{self.test_server_url}/run"
        data = {
            "project_path": project_path,
            "test_path": test_path,
            "runner": runner,
            "mode": mode,
            "max_failures": max_failures,
            "run_last_failed": run_last_failed,
            "timeout": timeout,
            "max_tokens": max_tokens,
        }
        
        if docker_image and mode == "docker":
            data["docker_image"] = docker_image
            
        if additional_args:
            data["additional_args"] = additional_args
            
        return await self._post(url, data)
    
    async def get_test_result(self, result_id: str) -> Dict[str, Any]:
        """
        Get the result of a test execution.
        
        Args:
            result_id: The ID of the test execution
            
        Returns:
            A dictionary containing the test results
        """
        url = f"{self.test_server_url}/results/{result_id}"
        return await self._get(url)
    
    async def list_test_results(self) -> Dict[str, Any]:
        """
        List all test execution IDs.
        
        Returns:
            A dictionary containing a list of test result IDs
        """
        url = f"{self.test_server_url}/results"
        return await self._get(url)
    
    async def get_last_failed_tests(self) -> List[str]:
        """
        Get a list of tests that failed in the most recent execution.
        
        Returns:
            A list of test names that failed
        """
        url = f"{self.test_server_url}/last-failed"
        result = await self._get(url)
        return result.get("tests", []) 