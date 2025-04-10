#!/usr/bin/env python3
"""
Unit tests for the MCP Code Server
"""

import sys
import os
import json
import pytest
from fastapi.testclient import TestClient

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from agents.mcp_code_server import app, CodeSnippet


# Create a test client
client = TestClient(app)


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
    
    # Check for specific issue types
    issue_types = [issue["type"] for issue in result["issues"]]
    assert any("undefined" in issue_type.lower() for issue_type in issue_types) or \
           any("unused" in issue_type.lower() for issue_type in issue_types)


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
    """Test formatting invalid Python code"""
    # Invalid syntax
    test_code = """
def add(a,b)
    return a+b
"""
    response = client.post("/format", json={"code": test_code})
    assert response.status_code == 200
    result = response.json()
    
    # Should have error
    assert "error" in result
    assert result["error"] is not None


def test_store_snippet():
    """Test storing a code snippet"""
    snippet = {
        "code": "def test_function():\n    return 'Hello'",
        "language": "python",
        "description": "Test function"
    }
    
    response = client.post("/store", json=snippet)
    assert response.status_code == 200
    result = response.json()
    
    # Verify the snippet ID is returned
    assert "id" in result
    assert result["id"] is not None


def test_get_snippet():
    """Test retrieving a stored code snippet"""
    # First store a snippet
    snippet = {
        "code": "def hello_world():\n    print('Hello, World!')",
        "language": "python",
        "description": "Hello World function"
    }
    
    store_response = client.post("/store", json=snippet)
    snippet_id = store_response.json()["id"]
    
    # Now retrieve it
    response = client.get(f"/snippets/{snippet_id}")
    assert response.status_code == 200
    result = response.json()
    
    # Verify the retrieved snippet matches what we stored
    assert result["code"] == snippet["code"]
    assert result["language"] == snippet["language"]
    assert result["description"] == snippet["description"]


def test_get_nonexistent_snippet():
    """Test retrieving a snippet that doesn't exist"""
    response = client.get("/snippets/nonexistent-id")
    assert response.status_code == 404


def test_get_all_snippets():
    """Test retrieving all stored snippets"""
    # Create a few snippets for testing
    snippets = [
        {"code": "def func1():\n    pass", "language": "python", "description": "Function 1"},
        {"code": "def func2():\n    pass", "language": "python", "description": "Function 2"}
    ]
    
    for snippet in snippets:
        client.post("/store", json=snippet)
    
    # Retrieve all snippets
    response = client.get("/snippets")
    assert response.status_code == 200
    result = response.json()
    
    # There should be snippets in the result
    assert len(result) > 0
    
    # Verify the structure of the returned snippets
    for snippet in result:
        assert "id" in snippet
        assert "code" in snippet
        assert "language" in snippet
        assert "description" in snippet


if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 