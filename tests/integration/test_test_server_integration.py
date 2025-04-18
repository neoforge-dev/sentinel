import pytest
import pytest_asyncio
import httpx
import os
import sys
import re
import asyncio

# Assuming constants are defined in tests/conftest.py or globally accessible
# If not, these might need adjustment
from tests.conftest import TEST_SERVER_URL, API_KEY

HEADERS = {"X-API-Key": API_KEY}

@pytest.mark.asyncio
async def test_root_endpoint(test_server_process):
    """Test the root endpoint of the test server."""
    # test_server_process fixture ensures the server is running
    async with httpx.AsyncClient(base_url=TEST_SERVER_URL, headers=HEADERS) as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data.get("message") == "MCP Test Server is running"

@pytest.mark.asyncio
async def test_run_local_success(test_server_process, sample_project_path):
    """Test running tests locally that succeed."""
    config = {
        "project_path": str(sample_project_path),
        "test_path": "test_passing.py", # Use a known passing test
        "runner": "pytest",
        "mode": "local",
    }
    async with httpx.AsyncClient(base_url=TEST_SERVER_URL, headers=HEADERS, timeout=60.0) as client:
        response = await client.post("/run-tests", json=config)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "Passed"
        assert data["summary"] is not None # Basic check

@pytest.mark.asyncio
async def test_run_local_failure(test_server_process, sample_project_path):
    """Test running tests locally that fail."""
    config = {
        "project_path": str(sample_project_path),
        "test_path": "test_failing.py", # Use a known failing test
        "runner": "pytest",
        "mode": "local",
    }
    async with httpx.AsyncClient(base_url=TEST_SERVER_URL, headers=HEADERS, timeout=60.0) as client:
        response = await client.post("/run-tests", json=config)
        assert response.status_code == 200 # API call succeeds even if tests fail
        data = response.json()
        assert data["status"] == "Failed"
        assert data["summary"] is not None # Basic check

@pytest.mark.asyncio
async def test_get_list_results(test_server_process):
    """Test listing test results."""
    # Assumes some tests have run via other tests using the session server
    async with httpx.AsyncClient(base_url=TEST_SERVER_URL, headers=HEADERS) as client:
        response = await client.get("/results")
        assert response.status_code == 200
        assert isinstance(response.json(), list) # Should return a list

@pytest.mark.asyncio
async def test_get_last_failed(test_server_process, sample_project_path):
    """Test getting the last failed test result."""
    # Assumes test_run_local_failure has run
    async with httpx.AsyncClient(base_url=TEST_SERVER_URL, headers=HEADERS) as client:
        # Use the actual sample_project_path used in failure test
        response = await client.get(f"/last-failed?project_path={sample_project_path}")
        # Expect 200 if failure exists for this path, or 404 otherwise
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            assert isinstance(response.json(), list)

# Test for Docker Mode - This is the new TDD test case
@pytest.mark.asyncio
async def test_run_docker_mode_success_and_verify_db(test_server_process, sample_project_path):
    """Test running tests in Docker mode that succeed and verify DB record."""
    config = {
        "project_path": str(sample_project_path),
        "test_path": "test_passing.py", # Use a known passing test
        "runner": "pytest",
        "mode": "docker",
        "stream_output": True, # Enable streaming to get result ID
        "docker_image": "python:3.11-slim" # Ensure this image is available
    }
    result_id = None
    
    async with httpx.AsyncClient(base_url=TEST_SERVER_URL, headers=HEADERS, timeout=180.0) as client:
        # --- Execute Test Run --- 
        async with client.stream("POST", "/run-tests", json=config) as response:
            # Check initial response status
            assert response.status_code == 200
            # Process stream to find the result ID
            async for line in response.aiter_lines():
                print(f"Stream Line: {line}") # Debug output during test run
                if "--- RESULT_STORED:" in line:
                    match = re.search(r"--- RESULT_STORED: ([a-f0-9\-]+) ---", line)
                    if match:
                        result_id = match.group(1)
                        print(f"Extracted Result ID: {result_id}") # Debug
                        break # Found the ID, no need to process rest of stream here
        
        # --- Verification --- 
        assert result_id is not None, "Result ID was not found in the stream"
        
        # Give DB a moment (optional, but sometimes helpful in CI)
        await asyncio.sleep(1)

        # Fetch the result from the database via API
        get_response = await client.get(f"/results/{result_id}")
        
        print(f"GET /results/{result_id} Status: {get_response.status_code}")
        print(f"GET /results/{result_id} Response: {get_response.text}") # Debug
        
        assert get_response.status_code == 200, f"Failed to fetch result {result_id}"
        result_data = get_response.json()
        
        # Verify the data stored in the DB
        assert result_data["id"] == result_id
        assert result_data["execution_mode"] == "docker"
        assert result_data["status"] == "Passed" # Assuming test_passing.py passes
        assert result_data["runner"] == "pytest"
        assert result_data["project_path"] == str(sample_project_path)
        assert "test_passing.py" in result_data["test_path"]

# Basic placeholder tests for Docker - these might need significant refinement
# depending on local Docker setup and the base image used by the server.
@pytest.mark.asyncio
@pytest.mark.skip(reason="Docker tests require specific setup and configuration")
async def test_run_docker_success(test_server_process, sample_project_path):
    """Placeholder for testing successful Docker test runs."""
    config = {
        "project_path": str(sample_project_path), # Mount path in Docker needs care
        "test_path": "test_passing.py",
        "runner": "pytest",
        "mode": "docker",
        "docker_image": "python:3.11-slim" # Example image
    }
    async with httpx.AsyncClient(base_url=TEST_SERVER_URL, headers=HEADERS, timeout=120.0) as client:
        response = await client.post("/run-tests", json=config)
        assert response.status_code == 200
        data = response.json()
        # assert data["status"] == "Passed" # Assertion depends on actual Docker run

@pytest.mark.asyncio
@pytest.mark.skip(reason="Docker tests require specific setup and configuration")
async def test_run_docker_failure(test_server_process, sample_project_path):
    """Placeholder for testing failing Docker test runs."""
    config = {
        "project_path": str(sample_project_path), # Mount path in Docker needs care
        "test_path": "test_failing.py",
        "runner": "pytest",
        "mode": "docker",
        "docker_image": "python:3.11-slim" # Example image
    }
    async with httpx.AsyncClient(base_url=TEST_SERVER_URL, headers=HEADERS, timeout=120.0) as client:
        response = await client.post("/run-tests", json=config)
        assert response.status_code == 200
        data = response.json()
        # assert data["status"] == "Failed" # Assertion depends on actual Docker run 