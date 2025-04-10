#!/usr/bin/env python3
"""
Integration tests for register_mcps.py
Tests that both MCP integrations work together properly
"""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import the functions from register_mcps
from examples.register_mcps import setup_agent, print_available_tools


class MockOllamaAgent:
    """Mock OllamaAgent class for testing tool registration"""
    
    def __init__(self, model="mistral:7b", mcp_enabled=True):
        self.model = model
        self.mcp_enabled = mcp_enabled
        self.tools = {}
        self.context = type('Context', (), {'tools': self.tools})
    
    def register_tool(self, tool_config):
        """Mock tool registration"""
        self.tools[tool_config.name] = tool_config


@pytest.fixture
def mock_agent():
    """Create a mock agent for testing"""
    return MockOllamaAgent()


@patch("examples.register_mcps.OllamaAgent")
@patch("examples.register_mcps.register_code_tools")
@patch("examples.register_mcps.register_test_tools")
def test_setup_agent(mock_register_test, mock_register_code, mock_ollama_agent, mock_agent):
    """Test that the setup_agent function properly initializes the agent"""
    mock_ollama_agent.return_value = mock_agent
    
    # Call setup_agent
    agent = setup_agent(model="test-model", mcp_enabled=True)
    
    # Verify OllamaAgent was created with the right parameters
    mock_ollama_agent.assert_called_once_with(model="test-model", mcp_enabled=True)
    
    # Verify both tool registrations were called
    mock_register_code.assert_called_once_with(mock_agent)
    mock_register_test.assert_called_once_with(mock_agent)
    
    # Verify the agent is returned
    assert agent == mock_agent


def test_print_available_tools(mock_agent, capsys):
    """Test that print_available_tools properly formats and prints tools"""
    # Add some mock tools
    mock_agent.tools["analyze_code"] = type('ToolConfig', (), {
        'name': 'analyze_code', 
        'description': 'Analyze code for issues'
    })
    
    mock_agent.tools["format_code"] = type('ToolConfig', (), {
        'name': 'format_code', 
        'description': 'Format code'
    })
    
    mock_agent.tools["run_tests"] = type('ToolConfig', (), {
        'name': 'run_tests', 
        'description': 'Run tests in a project'
    })
    
    mock_agent.tools["analyze_test_failures"] = type('ToolConfig', (), {
        'name': 'analyze_test_failures', 
        'description': 'Analyze test failures'
    })
    
    mock_agent.tools["other_tool"] = type('ToolConfig', (), {
        'name': 'other_tool', 
        'description': 'Some other tool'
    })
    
    # Call the function
    print_available_tools(mock_agent)
    
    # Capture the printed output
    captured = capsys.readouterr()
    output = captured.out
    
    # Verify the output contains the expected categories and tools
    assert "=== Available Tools ===" in output
    assert "Code Tools:" in output
    assert "Test Tools:" in output
    assert "Other Tools:" in output
    
    # Verify specific tools are under the right categories
    assert "- analyze_code: Analyze code for issues" in output
    assert "- format_code: Format code" in output
    assert "- run_tests: Run tests in a project" in output
    assert "- analyze_test_failures: Analyze test failures" in output
    assert "- other_tool: Some other tool" in output


@patch("examples.register_mcps.setup_agent")
@patch("examples.register_mcps.print_available_tools")
@patch("examples.register_mcps.requests.get")
def test_main_function(mock_requests, mock_print, mock_setup, mock_agent):
    """Test the main function with mocked server checks"""
    # Mock the agent setup
    mock_setup.return_value = mock_agent
    
    # Mock the requests.get responses
    def mock_get_response(url):
        """Return success for both MCP servers"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        return mock_response
    
    mock_requests.side_effect = mock_get_response
    
    # Import and patch the main function
    with patch("examples.register_mcps.main") as mock_main:
        mock_main.return_value = mock_agent
        
        # Import the module
        import examples.register_mcps
        
        # Call the patched main function
        agent = mock_main()
        
        # Verify setup_agent was called
        mock_setup.assert_called_once()
        
        # Verify tools were printed
        mock_print.assert_called_once_with(mock_agent)
        
        # Verify server checks
        assert mock_requests.call_count == 2
    
    # Verify the agent was returned
    assert agent == mock_agent


if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 