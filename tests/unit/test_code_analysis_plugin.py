#!/usr/bin/env python3
"""
Unit tests for the code analysis plugin
"""

import sys
import os
import json
import pytest
from unittest.mock import patch, MagicMock

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import the plugin functions
from examples.code_analysis_plugin import (
    analyze_code_with_mcp,
    format_code_with_mcp,
    store_snippet_with_mcp,
    register_code_tools
)


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


@patch("examples.code_analysis_plugin.requests.post")
def test_analyze_code_success(mock_post):
    """Test successful code analysis"""
    # Mock response data
    mock_data = {
        "issues": [
            {"line": 2, "col": 10, "type": "F401", "message": "Module imported but unused"}
        ],
        "formatted_code": "def hello():\n    print('Hello')\n"
    }
    
    # Set up the mock
    mock_post.return_value = MockResponse(200, mock_data)
    
    # Test code
    code = "import os\n\ndef hello():\n    print('Hello')"
    
    # Call the function
    result = analyze_code_with_mcp(code)
    
    # Verify the results
    assert "issues" in result
    assert "formatted_code" in result
    assert result["issues"] == mock_data["issues"]
    assert result["formatted_code"] == mock_data["formatted_code"]
    
    # Verify the request
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0].endswith("/analyze")
    assert kwargs["json"]["code"] == code


@patch("examples.code_analysis_plugin.requests.post")
def test_analyze_code_error(mock_post):
    """Test code analysis with a server error"""
    # Mock a server error
    mock_post.return_value = MockResponse(500, {"error": "Server error"})
    
    # Test code
    code = "def hello():\n    print('Hello')"
    
    # Call the function and check it handles the error
    result = analyze_code_with_mcp(code)
    
    # Verify the error is handled
    assert "error" in result
    assert "issues" in result
    assert "formatted_code" in result
    assert result["issues"] == []
    assert result["formatted_code"] == code  # Original code should be returned


@patch("examples.code_analysis_plugin.requests.post")
def test_format_code_success(mock_post):
    """Test successful code formatting"""
    # Mock response data
    mock_data = {
        "formatted_code": "def hello():\n    print('Hello')\n"
    }
    
    # Set up the mock
    mock_post.return_value = MockResponse(200, mock_data)
    
    # Test code
    code = "def hello():\n  print('Hello')"
    
    # Call the function
    result = format_code_with_mcp(code)
    
    # Verify the results
    assert "formatted_code" in result
    assert result["formatted_code"] == mock_data["formatted_code"]
    
    # Verify the request
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0].endswith("/format")
    assert kwargs["json"]["code"] == code


@patch("examples.code_analysis_plugin.requests.post")
def test_format_code_error(mock_post):
    """Test code formatting with a server error"""
    # Mock a server error
    mock_post.return_value = MockResponse(500, {"error": "Server error"})
    
    # Test code
    code = "def hello():\n  print('Hello')"
    
    # Call the function and check it handles the error
    result = format_code_with_mcp(code)
    
    # Verify the error is handled
    assert "error" in result
    assert "formatted_code" in result
    assert result["formatted_code"] == code  # Original code should be returned


@patch("examples.code_analysis_plugin.requests.post")
def test_store_snippet_success(mock_post):
    """Test successful snippet storage"""
    # Mock response data
    mock_data = {
        "id": "snippet-123",
        "message": "Snippet stored successfully"
    }
    
    # Set up the mock
    mock_post.return_value = MockResponse(200, mock_data)
    
    # Test snippet data
    code = "def hello():\n    print('Hello')"
    language = "python"
    description = "Simple hello function"
    
    # Call the function
    result = store_snippet_with_mcp(code, language, description)
    
    # Verify the results
    assert "id" in result
    assert "message" in result
    assert result["id"] == mock_data["id"]
    assert result["message"] == mock_data["message"]
    
    # Verify the request
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0].endswith("/store")
    assert kwargs["json"]["code"] == code
    assert kwargs["json"]["language"] == language
    assert kwargs["json"]["description"] == description


@patch("examples.code_analysis_plugin.requests.post")
def test_store_snippet_error(mock_post):
    """Test snippet storage with a server error"""
    # Mock a server error
    mock_post.return_value = MockResponse(500, {"error": "Server error"})
    
    # Test snippet data
    code = "def hello():\n    print('Hello')"
    language = "python"
    description = "Simple hello function"
    
    # Call the function and check it handles the error
    result = store_snippet_with_mcp(code, language, description)
    
    # Verify the error is handled
    assert "error" in result
    assert result["error"] is not None


def test_register_code_tools(mock_agent):
    """Test that code tools are registered with the agent"""
    # Register tools with the mock agent
    register_code_tools(mock_agent)
    
    # Verify the tools were registered
    assert "analyze_code" in mock_agent.tools
    assert "format_code" in mock_agent.tools
    assert "store_snippet" in mock_agent.tools


if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 