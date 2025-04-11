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
from examples.register_mcps import setup_agent, print_available_tools, main as register_mcps_main


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

    def execute_tool(self, tool_name, params):
        # Mock execution logic if needed
        pass


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


# Mock Response for requests.get
class MockResponse:
    def __init__(self, status_code):
        self.status_code = status_code


@patch("examples.register_mcps.setup_agent")
@patch("requests.get")
@patch("examples.register_mcps.print")
def test_main_function(mock_print, mock_requests_get, mock_setup_agent, mock_agent):
    """Test the main function to ensure it initializes the agent and checks servers."""
    
    # Configure mocks
    mock_setup_agent.return_value = mock_agent # Return the mock agent
    mock_requests_get.return_value = MockResponse(200) # Mock successful server checks
    
    # Set environment variables if needed (or assume defaults)
    # os.environ["MCP_CODE_SERVER_URL"] = "http://mock-code-server"
    # os.environ["MCP_TEST_SERVER_URL"] = "http://mock-test-server"

    # Call the main function
    # Use try-except to catch SystemExit from argparse if needed, or use specific args
    with patch('sys.argv', ['register_mcps.py']): # Mock sys.argv
        returned_agent = register_mcps_main()

    # Assertions
    mock_setup_agent.assert_called_once_with(model="mistral:7b", mcp_enabled=True)
    assert mock_requests_get.call_count == 2 # Check both servers
    # Check the URLs called
    expected_urls = [
        f"http://localhost:8081", # Default code server URL
        f"http://localhost:8082"  # Default test server URL
    ]
    actual_urls = [call.args[0] for call in mock_requests_get.call_args_list]
    assert sorted(actual_urls) == sorted(expected_urls)
    
    assert returned_agent == mock_agent # Ensure the configured agent is returned
    
    # Check print calls if necessary (e.g., verify server status messages)
    # print(mock_print.call_args_list)
    assert any("Code MCP Server: Connected" in call.args[0] for call in mock_print.call_args_list)
    assert any("Test MCP Server: Connected" in call.args[0] for call in mock_print.call_args_list)


if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 