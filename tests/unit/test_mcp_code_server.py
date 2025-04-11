#!/usr/bin/env python3
"""
Unit tests for the MCP Code Server
"""

import sys
import os
import json
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import Depends
from httpx import AsyncClient, ASGITransport

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from agents.mcp_code_server import app

# Directly import database components - assume they exist when testing
from src.storage.database import DatabaseManager, get_db_manager

# Import security dependency
try:
    from src.security import verify_api_key, EXPECTED_API_KEY
except ImportError:
    # Define dummies if import fails
    async def verify_api_key(): pass
    EXPECTED_API_KEY = "dev_secret_key" # Ensure this matches the default used

# Create a test client
client = TestClient(app)

# Synchronous client fixture (useful for simple tests)
@pytest.fixture(scope="module")
def client_sync():
    # Add default valid API key header to sync client
    headers = {"X-API-Key": EXPECTED_API_KEY}
    return TestClient(app, headers=headers)

# Asynchronous client fixture (needed for async endpoints)
@pytest_asyncio.fixture(scope="function") # Use function scope for client
async def client_async():
    # Add default valid API key header to async client
    headers = {"X-API-Key": EXPECTED_API_KEY}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver", headers=headers) as client:
        yield client

# Fixture for overriding DB dependency
@pytest.fixture
def mock_db_manager():
    mock = MagicMock(spec=DatabaseManager)
    # Configure async methods
    mock.store_code_snippet = AsyncMock()
    mock.get_code_snippet = AsyncMock(return_value=None) # Default: not found
    # Add mocks for other DB methods used by the code server if any
    return mock

# Override the get_db_manager dependency for all tests in this module
@pytest.fixture(autouse=True)
def override_get_db_manager(mock_db_manager):
    async def _override_get_db():
        return mock_db_manager
    
    # Store original overrides if any
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db_manager] = _override_get_db
    yield
    # Restore original overrides
    app.dependency_overrides = original_overrides

# Override verify_api_key dependency (optional, can test actual dependency too)
@pytest.fixture(autouse=True)
def override_verify_api_key_dependency():
    """Override the verify_api_key dependency for most tests."""
    async def _override_verify():
        # Simple override that always passes, returns a dummy key
        return "test_key"
    
    # Store original overrides if any
    original_overrides = app.dependency_overrides.copy()
    # Target the actual verify_api_key function imported
    app.dependency_overrides[verify_api_key] = _override_verify
    yield
    # Restore original overrides
    app.dependency_overrides = original_overrides

def test_root_endpoint():
    """Test the root endpoint returns a 200 status code"""
    response = client.get("/")
    assert response.status_code == 200
    assert "MCP Code Server" in response.text


def test_analyze_code_valid():
    """Test analyzing valid Python code"""
    test_code = """
def add(a, b):
    return a + b
"""
    response = client.post("/analyze", json={"code": test_code})
    assert response.status_code == 200
    result = response.json()
    
    # Verify the expected structure
    assert "issues" in result
    assert "formatted_code" in result
    assert isinstance(result["issues"], list)
    
    # The test code should have no issues
    assert len(result["issues"]) == 0
    
    # Formatted code should be similar to input (after formatting)
    assert "def add(a, b):" in result["formatted_code"]


def test_analyze_code_with_issues():
    """Test analyzing Python code with issues"""
    # This code has unused import and undefined variable issues
    test_code = """
import os
import sys
import json

def print_value():
    print(undefined_var)
"""
    response = client.post("/analyze", json={"code": test_code})
    assert response.status_code == 200
    result = response.json()
    
    # There should be issues
    assert len(result["issues"]) > 0
    
    # Check for specific issue types (using 'code' field from Ruff output)
    issue_codes = [issue["code"] for issue in result["issues"]]
    assert "F401" in issue_codes  # Unused import
    assert "F821" in issue_codes  # Undefined name


def test_analyze_code_invalid_request():
    """Test analyzing code with an invalid request body"""
    # Missing required 'code' field
    response = client.post("/analyze", json={})
    assert response.status_code == 422  # Unprocessable Entity for validation errors


def test_format_code_valid():
    """Test formatting valid Python code"""
    # Code with formatting issues
    test_code = """
def add(a,b):
    return a+b
"""
    response = client.post("/format", json={"code": test_code})
    assert response.status_code == 200
    result = response.json()
    
    # Verify formatted code
    assert "formatted_code" in result
    assert "def add(a, b):" in result["formatted_code"]  # Space after comma


def test_format_code_invalid():
    """Test formatting invalid Python code which should return an error."""
    # Invalid syntax
    test_code = """
def add(a,b)
    return a+b
"""
    response = client.post("/format", json={"code": test_code})
    # Expect a 400 Bad Request because syntax prevents formatting
    assert response.status_code == 400
    result = response.json()

    # Check for the specific error structure
    assert "error" in result
    assert result["error"] == "Formatting failed"
    assert "details" in result
    assert "formatted_code" in result
    # Ensure original code is returned in the error response
    assert result["formatted_code"] == test_code


@pytest.mark.asyncio
async def test_store_and_get_snippet(client_async, mock_db_manager):
    """Test storing and retrieving a code snippet."""
    # Define snippet data without ID first
    snippet_data = {"code": "print('Hello')", "language": "python"}

    # Store the snippet by POSTing to /snippets
    response_store = await client_async.post("/snippets", json=snippet_data)
    assert response_store.status_code == 200
    result_store = response_store.json()

    # Expect the server to return the full CodeSnippet model including the generated ID
    assert "id" in result_store
    snippet_id = result_store["id"] # Get the ID assigned by the server
    assert result_store["code"] == snippet_data["code"]
    assert result_store["language"] == snippet_data["language"]

    # Verify DB store method was called (server generates ID, so we check payload)
    mock_db_manager.store_code_snippet.assert_awaited_once()
    # Get the call arguments
    call_args, call_kwargs = mock_db_manager.store_code_snippet.call_args
    assert call_kwargs["snippet_id"] == snippet_id # Verify the correct ID was passed
    assert call_kwargs["code"] == snippet_data["code"]
    assert call_kwargs["language"] == snippet_data["language"]

    # Configure mock DB for the subsequent GET request
    mock_db_manager.get_code_snippet.return_value = {
        "id": snippet_id, # Use the ID returned by the server
        "code": snippet_data["code"],
        "language": snippet_data["language"],
        # Add other fields returned by DB method if necessary
    }

    # Retrieve the snippet using the ID from the store response
    response_get = await client_async.get(f"/snippets/{snippet_id}")
    assert response_get.status_code == 200
    result_get = response_get.json()

    # Verify the response matches the CodeSnippet model structure
    assert result_get["code"] == snippet_data["code"]
    assert result_get["language"] == snippet_data["language"]
    assert result_get["id"] == snippet_id

    # Verify DB get method was called
    mock_db_manager.get_code_snippet.assert_awaited_once_with(snippet_id)


@pytest.mark.asyncio
async def test_get_snippet_not_found(client_async, mock_db_manager):
    """Test retrieving a non-existent snippet."""
    snippet_id = "non-existent-snippet"

    # Configure mock DB to return None (default, but explicit)
    mock_db_manager.get_code_snippet.return_value = None

    # Attempt to retrieve
    response = await client_async.get(f"/snippets/{snippet_id}")
    assert response.status_code == 404
    result = response.json()
    assert "not found" in result["detail"].lower()

    # Verify DB get method was called
    mock_db_manager.get_code_snippet.assert_awaited_once_with(snippet_id)

    # Check if the mock was called - use await_count to avoid issues if called multiple times
    # across different tests due to fixture scope. Reset might be needed for function scope.
    assert mock_db_manager.get_code_snippet.await_count > 0
    # Or assert specific call if scope guarantees reset:
    # mock_db_manager.get_code_snippet.assert_awaited_once_with(snippet_id)


# Optional: Add tests for DB errors
@pytest.mark.asyncio
async def test_store_snippet_db_error(client_async, mock_db_manager):
    """Test storing snippet when DB fails."""
    snippet_data = {"code": "fail me", "language": "python"}

    # Configure mock to raise an exception
    mock_db_manager.store_code_snippet.side_effect = Exception("Database connection failed")

    response = await client_async.post("/snippets", json=snippet_data)
    # Assert the HTTP status code and detail message
    assert response.status_code == 500
    assert "error storing snippet" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_snippet_db_error(client_async, mock_db_manager):
    """Test retrieving snippet when DB fails."""
    snippet_id = "error-snippet-get"

    # Configure mock to raise an exception
    mock_db_manager.get_code_snippet.side_effect = Exception("Database query failed")

    response = await client_async.get(f"/snippets/{snippet_id}")
    # Assert the HTTP status code and detail message
    assert response.status_code == 500
    assert "error retrieving snippet" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_all_snippets(client_async, mock_db_manager):
    """Test retrieving all stored snippets"""
    # Configure mock DB to return a list of snippet IDs (or full snippets)
    mock_snippet_list = [
        {"id": "snip1", "code": "c1", "language": "py", "metadata": {}},
        {"id": "snip2", "code": "c2", "language": "py", "metadata": {}}
    ]
    # Ensure the mock method exists and is async
    mock_db_manager.list_code_snippets = AsyncMock(return_value=mock_snippet_list)

    # Retrieve all snippets
    response = await client_async.get("/snippets")
    assert response.status_code == 200
    result = response.json()

    # Check the response structure matches the endpoint definition
    assert "snippet_ids" in result
    assert isinstance(result["snippet_ids"], list)

    # Verify the mock was called
    mock_db_manager.list_code_snippets.assert_awaited_once()

    # Verify the returned IDs match the mock data
    assert len(result["snippet_ids"]) == len(mock_snippet_list)
    assert result["snippet_ids"] == [s["id"] for s in mock_snippet_list]


# Add a test for the /fix endpoint
# def test_fix_code_valid():
#     ...
# 
# def test_fix_code_no_fix():
#     ...


# --- Authentication Tests ---

def test_missing_api_key(): # Use raw TestClient
    """Test request without API key header fails with 401."""
    raw_client = TestClient(app) # Create client without default headers or overrides
    response = raw_client.post("/analyze", json={"code": "print(1)"})
    assert response.status_code == 401
    assert "missing api key" in response.json()["detail"].lower()

def test_invalid_api_key(): # Use raw TestClient
    """Test request with invalid API key header fails with 401."""
    raw_client = TestClient(app) # Create client without default headers or overrides
    headers = {"X-API-Key": "invalid-key"}
    response = raw_client.post("/analyze", json={"code": "print(1)"}, headers=headers)
    assert response.status_code == 401
    assert "invalid api key" in response.json()["detail"].lower()

@pytest.mark.asyncio
async def test_async_missing_api_key(): # Use raw AsyncClient
    """Test async request without API key header fails with 401."""
    # Create raw client without default headers or overrides
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as raw_client:
        response = await raw_client.post("/snippets", json={"code": "c", "language": "py"})
    assert response.status_code == 401
    assert "missing api key" in response.json()["detail"].lower()

@pytest.mark.asyncio
async def test_async_invalid_api_key(): # Use raw AsyncClient
    """Test async request with invalid API key header fails with 401."""
    # Create raw client without default headers or overrides
    headers = {"X-API-Key": "invalid-key"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as raw_client:
        response = await raw_client.post("/snippets", json={"code": "c", "language": "py"}, headers=headers)
    assert response.status_code == 401
    assert "invalid api key" in response.json()["detail"].lower()


if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 