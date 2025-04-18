"""
Unit tests for the OllamaAgent class in agents/agent.py
"""
import sys
import os
import json
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock, call
import requests
from json import JSONDecodeError
from pathlib import Path
import tempfile
import shutil
from unittest.mock import mock_open

# Add the parent directory to the path so we can import the agent module
# Resolve the directory of the current test file
current_dir = os.path.dirname(os.path.abspath(__file__))
# Construct the path to the project root (adjust '..' as necessary)
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
sys.path.insert(0, project_root)

from agents.agent import OllamaAgent, TaskType, ToolConfig, AgentContext, MCPResource
from src.mcp_integration import MCPIntegration # Assume this exists for MCP tests

# Mock URL for Ollama
MOCK_OLLAMA_URL = "http://localhost:11434"

# --- Fixtures --- 

@pytest.fixture
def mock_agent_no_mcp():
    """Fixture to create an agent instance without enabling MCP."""
    # Ensure workspace path exists for tests needing file operations
    temp_dir = tempfile.mkdtemp()
    agent = OllamaAgent(mcp_enabled=False, workspace_path=temp_dir)
    yield agent
    # Cleanup
    shutil.rmtree(temp_dir)

@pytest.fixture
def mock_agent_with_mcp():
    """Fixture to create an agent instance with MCP enabled (mocked)."""
    temp_dir = tempfile.mkdtemp()
    agent = OllamaAgent(mcp_enabled=True, workspace_path=temp_dir)
    # Mock the MCPIntegration part if necessary, or assume it's mocked elsewhere
    agent.mcp = MagicMock(spec=MCPIntegration)
    yield agent
    # Cleanup
    shutil.rmtree(temp_dir)

# --- Test Class --- 

class TestOllamaAgentGenerate:

    @patch('requests.post')
    def test_generate_streaming_success(self, mock_post, mock_agent_no_mcp):
        """Test successful streaming generation from Ollama."""
        # 1. Mock requests.post response
        mock_response = MagicMock(spec=requests.Response)
        mock_response.raise_for_status.return_value = None # Simulate successful status

        # Simulate streaming chunks
        chunks = [
            json.dumps({"response": "Hello "}).encode('utf-8'),
            json.dumps({"response": "World"}).encode('utf-8'),
            json.dumps({"done": True}).encode('utf-8')
        ]
        mock_response.iter_lines.return_value = iter(chunks)
        mock_post.return_value = mock_response

        # 2. Call the agent's generate method
        prompt = "Say hello"
        generator = mock_agent_no_mcp.generate(prompt)
        
        # 3. Consume the generator and assert results
        results = list(generator)
        assert results == ["Hello ", "World"]

        # 4. Verify requests.post was called correctly
        expected_url = f"{MOCK_OLLAMA_URL}/api/generate"
        mock_post.assert_called_once()
        call_args, call_kwargs = mock_post.call_args
        assert call_args[0] == expected_url
        assert call_kwargs['json']['prompt'] == prompt
        assert call_kwargs['json']['stream'] is True

    @patch('requests.post')
    def test_generate_streaming_request_error(self, mock_post, mock_agent_no_mcp):
        """Test handling of requests.RequestException during streaming."""
        # 1. Mock requests.post to raise an error
        error_message = "Connection timed out"
        mock_post.side_effect = requests.exceptions.RequestException(error_message)

        # 2. Call generate and consume
        prompt = "This will fail"
        generator = mock_agent_no_mcp.generate(prompt)
        results = list(generator)

        # 3. Assert error message is yielded
        assert len(results) == 1
        assert "[ERROR: Ollama request failed" in results[0]
        assert error_message in results[0]

    @patch('requests.post')
    def test_generate_streaming_http_error(self, mock_post, mock_agent_no_mcp):
        """Test handling of HTTPError (e.g., 404 Not Found)."""
        # 1. Mock response with an error status code
        mock_response = MagicMock(spec=requests.Response)
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Client Error")
        mock_post.return_value = mock_response

        # 2. Call generate and consume
        prompt = "Requesting non-existent endpoint?"
        generator = mock_agent_no_mcp.generate(prompt)
        results = list(generator)

        # 3. Assert error message is yielded (HTTPError is caught by RequestException handler)
        assert len(results) == 1
        assert "[ERROR: Ollama request failed" in results[0]
        assert "404 Client Error" in results[0]

    @patch('requests.post')
    def test_generate_streaming_json_decode_error(self, mock_post, mock_agent_no_mcp):
        """Test handling of JSONDecodeError during stream processing."""
        # 1. Mock response with invalid JSON chunk
        mock_response = MagicMock(spec=requests.Response)
        mock_response.raise_for_status.return_value = None
        chunks = [
            b'{"response": "Valid chunk"}',
            b'Invalid JSON chunk', # Malformed JSON
            b'{"done": true}'
        ]
        mock_response.iter_lines.return_value = iter(chunks)
        mock_post.return_value = mock_response

        # 2. Call generate and consume
        # We expect it to yield the valid chunk and then log a warning (not easily testable here)
        # and continue until done. It should not yield an error message directly for decode errors.
        prompt = "Test invalid json"
        generator = mock_agent_no_mcp.generate(prompt)
        results = list(generator)
        
        # 3. Assert only the valid part was yielded
        assert results == ["Valid chunk"]

    @patch('requests.post')
    def test_generate_streaming_ollama_internal_error_chunk(self, mock_post, mock_agent_no_mcp):
        """Test handling of error messages within the Ollama stream."""
        # 1. Mock response with an error message in a chunk
        mock_response = MagicMock(spec=requests.Response)
        mock_response.raise_for_status.return_value = None
        chunks = [
            json.dumps({"response": "Part 1..."}).encode('utf-8'),
            json.dumps({"error": "Ollama model load failed", "done": True}).encode('utf-8') # Error chunk
        ]
        mock_response.iter_lines.return_value = iter(chunks)
        mock_post.return_value = mock_response

        # 2. Call generate and consume
        prompt = "Trigger Ollama error"
        generator = mock_agent_no_mcp.generate(prompt)
        results = list(generator)

        # 3. Assert the valid part was yielded. The error chunk itself doesn't yield content.
        assert results == ["Part 1..."]

    # Add more tests for different task types, context handling etc. if needed

# --- Tool Execution Tests --- 

# Patch os functions used by the agent's file tools
@patch('agents.agent.os.path.exists')
@patch('builtins.open', new_callable=mock_open, read_data="This is the file content.\nLine 2.")
def test_tool_file_read_success(mock_open_builtin, mock_exists, mock_agent_no_mcp):
    """Test successful file reading using the _tool_file_read method."""
    test_path = "test_dir/my_file.txt"
    full_path_str = os.path.abspath(os.path.join(mock_agent_no_mcp.context.workspace_path or "", test_path))
    test_content = "This is the file content.\nLine 2."
    
    # Configure mocks
    mock_exists.return_value = True

    # Execute the tool method
    result = mock_agent_no_mcp._tool_file_read(test_path)

    # Assertions
    mock_exists.assert_called_once_with(full_path_str)
    mock_open_builtin.assert_called_once_with(full_path_str, 'r', encoding='utf-8')
    # Check result structure based on agent code
    assert result == {
        "success": True,
        "content": test_content,
        "path": test_path
    }

@patch('agents.agent.os.path.exists')
def test_tool_file_read_not_found(mock_exists, mock_agent_no_mcp):
    """Test file reading when the file does not exist."""
    test_path = "test_dir/non_existent.txt"
    full_path_str = os.path.abspath(os.path.join(mock_agent_no_mcp.context.workspace_path or "", test_path))
    
    # Configure mock
    mock_exists.return_value = False

    # Execute
    result = mock_agent_no_mcp._tool_file_read(test_path)

    # Assertions
    mock_exists.assert_called_once_with(full_path_str)
    # Check error structure based on agent code
    assert result == {"error": f"File not found: {test_path}"}

@patch('agents.agent.os.path.exists')
@patch('builtins.open') # Patch open directly for simulating OSError
def test_tool_file_read_os_error(mock_open_builtin, mock_exists, mock_agent_no_mcp):
    """Test file reading when an OS error occurs (e.g., permission denied)."""
    test_path = "test_dir/permission_denied.txt"
    full_path_str = os.path.abspath(os.path.join(mock_agent_no_mcp.context.workspace_path or "", test_path))
    error_message = "Permission denied"

    # Configure mocks
    mock_exists.return_value = True
    mock_open_builtin.side_effect = OSError(error_message) # Error during open

    # Execute
    result = mock_agent_no_mcp._tool_file_read(test_path)

    # Assertions
    mock_exists.assert_called_once_with(full_path_str)
    mock_open_builtin.assert_called_once_with(full_path_str, 'r', encoding='utf-8')
    # Check error structure based on agent code
    assert result == {"error": f"Error reading file: {error_message}"}

@patch('agents.agent.os.makedirs')
@patch('builtins.open', new_callable=mock_open)
def test_tool_file_write_success(mock_open_builtin, mock_makedirs, mock_agent_no_mcp):
    """Test successful file writing using the _tool_file_write method."""
    test_path = "output/new_file.log"
    full_path_str = os.path.abspath(os.path.join(mock_agent_no_mcp.context.workspace_path or "", test_path))
    parent_dir_str = os.path.dirname(full_path_str)
    test_content = "Log message 1\nLog message 2"

    # Mock setup: Assume makedirs works without error
    
    # Execute
    result = mock_agent_no_mcp._tool_file_write(test_path, test_content)

    # Assertions
    mock_makedirs.assert_called_once_with(parent_dir_str, exist_ok=True)
    mock_open_builtin.assert_called_once_with(full_path_str, 'w', encoding='utf-8')
    mock_open_builtin().write.assert_called_once_with(test_content)
    # Check result structure based on agent code
    assert result == {
        "success": True,
        "path": test_path,
        "bytes_written": len(test_content)
    }

@patch('agents.agent.os.makedirs')
@patch('builtins.open', new_callable=mock_open)
def test_tool_file_write_os_error_on_mkdir(mock_open_builtin, mock_makedirs, mock_agent_no_mcp):
    """Test file writing when os.makedirs raises an OS error."""
    test_path = "output/protected_dir/new_file.log"
    full_path_str = os.path.abspath(os.path.join(mock_agent_no_mcp.context.workspace_path or "", test_path))
    parent_dir_str = os.path.dirname(full_path_str)
    test_content = "This won't be written"
    error_message = "Permission denied creating directory"

    # Configure mocks
    mock_makedirs.side_effect = OSError(error_message) # Error during makedirs

    # Execute
    result = mock_agent_no_mcp._tool_file_write(test_path, test_content)

    # Assertions
    mock_makedirs.assert_called_once_with(parent_dir_str, exist_ok=True)
    mock_open_builtin.assert_not_called() # open should not be called
    # Check error structure based on agent code
    assert result == {"error": f"Error writing file: {error_message}"}

@patch('agents.agent.os.makedirs')
@patch('builtins.open') # Patch open directly
def test_tool_file_write_os_error_on_open(mock_open_builtin, mock_makedirs, mock_agent_no_mcp):
    """Test file writing when builtins.open raises an OS error."""
    test_path = "output/existing_dir/protected_file.log"
    full_path_str = os.path.abspath(os.path.join(mock_agent_no_mcp.context.workspace_path or "", test_path))
    parent_dir_str = os.path.dirname(full_path_str)
    test_content = "This won't be written"
    error_message = "Permission denied opening file"

    # Configure mocks
    # We assume makedirs is called, but doesn't raise error here
    mock_open_builtin.side_effect = OSError(error_message) # Error during open

    # Execute
    result = mock_agent_no_mcp._tool_file_write(test_path, test_content)

    # Assertions
    mock_makedirs.assert_called_once_with(parent_dir_str, exist_ok=True)
    mock_open_builtin.assert_called_once_with(full_path_str, 'w', encoding='utf-8')
    # Check error structure based on agent code
    assert result == {"error": f"Error writing file: {error_message}"}

# Add more tests for edge cases like empty content, different encodings if needed

if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 