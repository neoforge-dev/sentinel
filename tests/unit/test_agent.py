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

# Add the parent directory to the path so we can import the agent module
# Resolve the directory of the current test file
current_dir = os.path.dirname(os.path.abspath(__file__))
# Construct the path to the project root (adjust '..' as necessary)
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
sys.path.insert(0, project_root)

from agents.agent import OllamaAgent, TaskType, ToolConfig, AgentContext, MCPResource

# Mock URL for Ollama
MOCK_OLLAMA_URL = "http://localhost:11434"

# --- Fixtures --- 

@pytest.fixture
def mock_agent_no_mcp():
    """Provides a basic OllamaAgent instance with MCP disabled."""
    # Patch _configure_for_hardware directly to prevent the import psutil call inside it.
    with patch('agents.agent.OllamaAgent._configure_for_hardware') as mock_configure_hw:
        agent = OllamaAgent(mcp_enabled=False, optimize_for_hardware=True) # Still pass True to ensure constructor logic runs if needed
        yield agent

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

if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 