#!/usr/bin/env python3
"""
Unit tests for the code analysis plugin
"""

import sys
import os
import json
import pytest
import requests # Import requests for exception testing
from unittest.mock import patch, MagicMock, ANY, AsyncMock, call, mock_open
import uuid # Import uuid for patching

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import the plugin functions
from examples import code_analysis_plugin
from examples.code_analysis_plugin import (
    analyze_code_with_mcp,
    format_code_with_mcp,
    store_snippet_with_mcp,
    register_code_tools,
    MCP_CODE_SERVER_URL, # Import URL for checking calls
    _get_headers # Import helper for testing
)
from agents.agent import ToolConfig # Import ToolConfig for verification


class MockOllamaAgent:
    """Mock OllamaAgent class for testing tool registration"""
    
    def __init__(self):
        self.tools = {}
    
    def register_tool(self, tool_config):
        """Mock tool registration"""
        self.tools[tool_config.name] = tool_config


class MockResponse:
    """Mock response object for requests"""
    
    def __init__(self, status_code, data):
        self.status_code = status_code
        self.data = data
    
    def json(self):
        """Return the mock data"""
        return self.data
    
    def raise_for_status(self):
        """Raise an exception if status code is not 200"""
        if self.status_code != 200:
            raise Exception(f"HTTP Error {self.status_code}")


@pytest.fixture
def mock_agent():
    """Create a mock agent for testing"""
    return MockOllamaAgent()


# Mock URL
MOCK_URL = "http://mock-mcp-code-server:8081" # Ensure port matches plugin default or test env
MOCK_API_KEY = "test-agent-key"

# Mock the requests library
@patch.dict(os.environ, {
    "MCP_CODE_SERVER_URL": MOCK_URL, 
    "AGENT_API_KEY": MOCK_API_KEY
}, clear=True)
@patch('requests.post')
def test_analyze_code_success(mock_post):
    """Test analyze_code_with_mcp successful call."""
    expected_headers = {"Content-Type": "application/json", "X-API-Key": MOCK_API_KEY}
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "issues": []}
    mock_post.return_value = mock_response
    
    result = analyze_code_with_mcp("print('hello')")
    
    mock_post.assert_called_once_with(
        f"{MOCK_URL}/analyze",
        json={"code": "print('hello')", "language": "python"},
        headers=expected_headers
    )
    assert result["success"] == True


@patch('requests.post')
@patch.dict(os.environ, {"AGENT_API_KEY": ""}) # Test without API key
def test_analyze_code_no_api_key(mock_post):
    """Test analyze_code_with_mcp without API key header."""
    # Reload the plugin module to reflect the patched environment variable
    import importlib
    # Ensure code_analysis_plugin is the actual module object
    importlib.reload(code_analysis_plugin)

    expected_headers = {"Content-Type": "application/json"} # No X-API-Key
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "issues": []}
    mock_post.return_value = mock_response
    
    result = analyze_code_with_mcp("test code")
    
    # Verify the call was made without the API key in headers
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert "X-API-Key" not in kwargs.get("headers", {})
    
    # Verify the result matches the mocked success response
    assert result == {"success": True, "issues": []}


@patch("examples.code_analysis_plugin.analyze_code_with_mcp")
def test_format_code_success(mock_analyze):
    """Test successful code formatting"""
    # Mock analyze_code_with_mcp to return success and formatted code
    mock_analyze.return_value = {
        "success": True, # Ensure success is True
        "issues": [],
        "formatted_code": "formatted code example",
        "message": "Analysis successful" # Include expected fields
    }
    
    result = format_code_with_mcp("def foo():pass", language="python")
    
    # Verify the results
    mock_analyze.assert_called_once_with("def foo():pass", "python")
    assert result["success"] == True
    assert result["formatted_code"] == "formatted code example"
    assert result["message"] == "Formatting successful" # Message from format_code


@patch('examples.code_analysis_plugin.analyze_code_with_mcp') # Patch the function called internally
def test_format_code_error(mock_analyze):
    """Test code formatting when analysis fails."""
    # Mock analyze_code_with_mcp to return failure
    mock_analyze.return_value = {
        "success": False,
        "message": "Analysis failed",
        "issues": [],
        "formatted_code": None
    }
    
    code = "def hello():\n  print('Hello')"
    result = format_code_with_mcp(code)
    
    # Verify analyze_code_with_mcp was called
    mock_analyze.assert_called_once_with(code, "python")
    
    # Verify the error is handled and propagated
    assert result["success"] is False
    assert result["formatted_code"] is None
    assert result["message"] == "Analysis failed" # Message from analysis


@patch('examples.code_analysis_plugin.requests.post')
@patch('uuid.uuid4')
def test_store_snippet_success(mock_uuid, mock_post):
    """Test successful snippet storage"""
    # Mock response data
    mock_uuid.return_value = "snippet-123"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock() # Prevent raising error
    mock_post.return_value = mock_response
    
    # Test snippet data
    code = "def hello():\n    print('Hello')"
    language = "python"
    
    # Call the function
    result = store_snippet_with_mcp(code, language) # Call without snippet_id
    
    # Verify the results
    assert result["success"] == True
    assert result["id"] == "snippet-123" # Check for 'id' instead of 'message'
    assert "message" not in result # Ensure message is not in success response
    
    # Verify the request
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0].endswith("/store/snippet-123") # Check URL includes ID
    assert kwargs["json"]["code"] == code
    assert kwargs["json"]["language"] == language


@patch("examples.code_analysis_plugin.requests.post")
def test_store_snippet_error(mock_post):
    """Test snippet storage with a connection error"""
    # Mock a connection error
    error_message = "Connection failed"
    mock_post.side_effect = requests.RequestException(error_message)
    
    # Test snippet data
    code = "def hello():\n    print('Hello')"
    language = "python"
    snippet_id = "my-snippet-id"
    
    # Call the function and check it handles the error
    result = store_snippet_with_mcp(code, language, snippet_id=snippet_id)
    
    # Verify the request was made
    mock_post.assert_called_once_with(
        f"{MCP_CODE_SERVER_URL}/store/{snippet_id}",
        json={"code": code, "language": language},
        headers={"Content-Type": "application/json"}
    )
    
    # Verify the error is handled
    assert result["success"] is False
    assert "id" not in result
    assert result["message"] == f"Error storing snippet: {error_message}"


def test_register_code_tools(mock_agent):
    """Test that code tools are registered with the agent"""
    # Register tools with the mock agent
    register_code_tools(mock_agent)
    
    # Verify the tools were registered
    assert "analyze_code" in mock_agent.tools
    assert "format_code" in mock_agent.tools
    assert "store_code" in mock_agent.tools # Check for 'store_code'
    assert len(mock_agent.tools) == 3 # Ensure exactly 3 tools are registered


if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 