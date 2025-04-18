import pytest
import pytest_asyncio
import httpx
import os
import sys

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
async def test_get_last_failed(test_server_process):
    """Test getting the last failed test result."""
    # Assumes test_run_local_failure has run
    async with httpx.AsyncClient(base_url=TEST_SERVER_URL, headers=HEADERS) as client:
        response = await client.get("/results/last_failed?project_path=unknown") # Need a path param
        # Expect 404 if no failures for this path, or 200 if failure exists
        # For now, just check the call is made without error
        assert response.status_code in [200, 404]

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