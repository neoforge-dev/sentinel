# MCP Test Server Documentation

The MCP Test Server is a specialized service that helps AI agents run and analyze tests in Python projects. This document explains the components, setup, and usage of the MCP test server.

## Overview

The MCP Test Server provides a REST API for running tests in Python projects, either locally or in Docker containers. It handles test execution, result processing, and provides clean, token-optimized output for both humans and LLMs.

## Components

The testing system consists of three main components:

1. **MCP Test Server** (`agents/mcp_test_server.py`): A FastAPI server that manages test execution, processes results, and provides a clean API for running tests.

2. **Test Client** (`examples/mcp_test_client.py`): A command-line client that demonstrates how to interact with the MCP Test Server.

3. **Agent Plugin** (`examples/test_analysis_plugin.py`): A plugin for the main agent that provides tools for running and analyzing tests.

## MCP Test Server Features

- Run tests using different test runners (pytest, unittest, uv)
- Execute tests locally or in Docker containers
- Limit test output to a specified token budget
- Clean and format test output for better readability
- Track and run only previously failed tests
- Store test results for later retrieval

## Setup and Installation

### Prerequisites

- Python 3.8+
- FastAPI
- Uvicorn
- Pydantic
- Tiktoken (for token counting)
- Docker (optional, for container-based testing)

### Setting Up the Server

1. Install the required dependencies:
   ```bash
   pip install fastapi uvicorn pydantic tiktoken docker
   ```

2. Start the server:
   ```bash
   python agents/mcp_test_server.py
   ```

The server will start on http://localhost:8082 by default.

## API Endpoints

The MCP Test Server provides the following endpoints:

- `POST /run_tests`: Run tests with specified configuration
- `GET /test_result/{test_id}`: Get the result of a specific test run
- `GET /test_results`: List all test result IDs
- `GET /last_failed_tests`: Get the list of tests that failed in the last run

## Using the Test Client

The test client provides a command-line interface for interacting with the MCP Test Server.

### Basic Usage

```bash
# Run tests in a project
python examples/mcp_test_client.py run --project_path /path/to/project --test_path tests/

# Run tests with specific configuration
python examples/mcp_test_client.py run --project_path /path/to/project --test_path tests/ --runner pytest --mode local --max_failures 3

# Get a test result
python examples/mcp_test_client.py get-result --test_id <test_id>

# List all test result IDs
python examples/mcp_test_client.py list

# Run only previously failed tests
python examples/mcp_test_client.py run --project_path /path/to/project --run_last_failed
```

## Integrating with the Main Agent

The test analysis plugin provides tools for the main agent to interact with the MCP Test Server.

### Plugin Registration

```python
from examples.test_analysis_plugin import register_test_tools

def register_tools(agent):
    register_test_tools(agent.register_tool)
```

### Available Tools

The plugin provides the following tools:

- `run_tests`: Run tests in a project using the MCP test server
- `get_test_result`: Get the result of a previously run test by its ID
- `list_test_results`: List all test result IDs
- `get_last_failed_tests`: Get the list of tests that failed in the last run
- `format_test_result`: Format a test result into a human-readable string

### Example Agent Usage

```python
# Run tests
result = agent.run_tests(
    project_path="/path/to/project",
    test_path="tests/",
    runner="pytest",
    mode="local",
    max_failures=3
)

# Get test ID
test_id = result["test_id"]

# Get test result
result = agent.get_test_result(test_id)

# Format and display the result
formatted_result = agent.format_test_result(result)
print(formatted_result)
```

## Docker Integration

To run tests in Docker containers, ensure Docker is installed and running on your system. Then specify `mode="docker"` when running tests:

```python
result = agent.run_tests(
    project_path="/path/to/project",
    test_path="tests/",
    runner="pytest",
    mode="docker",
    docker_image="python:3.11-slim"
)
```

## Token Budget Management

The MCP Test Server manages token output to prevent overwhelming LLMs. By default, it limits output to 4000 tokens, but this can be adjusted:

```python
result = agent.run_tests(
    project_path="/path/to/project",
    test_path="tests/",
    max_tokens=6000
)
```

## Advanced Features

### Running Only Failed Tests

To run only tests that failed in the previous test run:

```python
result = agent.run_tests(
    project_path="/path/to/project",
    run_last_failed=True
)
```

### Stopping After a Number of Failures

To stop test execution after a certain number of failures:

```python
result = agent.run_tests(
    project_path="/path/to/project",
    max_failures=3
)
```

## Troubleshooting

- If the server is not responding, make sure it's running at the expected URL.
- If you encounter Docker-related issues, verify that Docker is running and accessible.
- For token budget issues, try increasing the `max_tokens` parameter.
- If test output is unclear, check the original test output in the `details` field of the test result.

## Future Improvements

- Support for additional test frameworks
- Test coverage reporting
- Performance profiling
- Integration with CI/CD systems

### Running the Server

To run the server:

```bash
# Set the API key (optional, defaults to 'test-key')
export MCP_API_KEY="your-secret-key"

# Set the port (optional, defaults to 8082)
export MCP_TEST_PORT=8082

# Navigate to the project root directory
cd /path/to/base-agent

# Run using uvicorn
python agents/mcp_test_server.py
# Or directly with uvicorn for more options (like reload)
# uvicorn agents.mcp_test_server:app --host 0.0.0.0 --port 8082 --reload
```

The server will start on http://localhost:8082 by default. 