import pytest
import os
import asyncio
import subprocess
import sys
import time
import aiohttp
from typing import AsyncGenerator
import pytest_asyncio
import requests

# Adjust the path to import from the 'src' directory added to pythonpath
from storage.database import get_db_manager, DB_PATH
from src.storage.database import DatabaseManager
from src.mcp_enhanced_agent import MCPEnhancedAgent

# Add project root to path to allow importing server modules if needed
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Define server URLs, Port, and API Key
CODE_SERVER_URL = "http://localhost:8083" # Using 8083 for test code server
TEST_SERVER_PORT = 8082 # Define the port
TEST_SERVER_URL = f"http://localhost:{TEST_SERVER_PORT}"
API_KEY = os.environ.get("MCP_API_KEY", "dev_secret_key")

# Define a module-scoped event loop specifically for conftest managed fixtures
# This is needed by the session-scoped server process fixtures.
# @pytest.fixture(scope="session") # Removed custom event_loop fixture
# def event_loop(request):
#     """Create an instance of the default event loop for the session."""
#     loop = asyncio.get_event_loop_policy().new_event_loop()
#     yield loop
#     loop.close()

@pytest.fixture(scope="session", autouse=True)
def initialize_test_database():
    """Fixture to ensure a clean database schema for the test session."""
    # Delete existing DB file before session
    if os.path.exists(DB_PATH):
        print(f"\nRemoving existing test database: {DB_PATH}")
        try:
            os.remove(DB_PATH)
        except OSError as e:
            print(f"Error removing database file: {e}. Tests might use old schema.")
            # Proceed anyway, maybe permissions issue or file lock

    # Initialize schema using the manager
    print("Initializing new test database schema...")
    db_manager = get_db_manager() # Get singleton instance
    
    # Run async initialization in a temporary event loop
    async def _init_db():
        await db_manager.connect() # This implicitly calls _create_tables if not initialized
        await db_manager.disconnect()
    
    try:
        asyncio.run(_init_db())
        print("Test database initialized.")
    except Exception as e:
        print(f"Error initializing test database: {e}")
        # Fail fast if DB init fails
        pytest.fail(f"Could not initialize test database: {e}")

    # Yield control to the test session
    yield

    # Optional: Cleanup after session if needed, though often test DBs are left
    # print("\nTest session finished.") 

@pytest.fixture(scope="session")
def sample_project_path(tmp_path_factory):
    """Fixture to create a temporary sample project directory with dummy test files."""
    # Create a base temporary directory for the session
    base_temp = tmp_path_factory.mktemp("sample_project_session")
    
    # Create dummy test files required by tests
    (base_temp / "test_passing.py").write_text("def test_always_passes(): assert True")
    (base_temp / "test_failing.py").write_text("def test_always_fails(): assert False")
    # Add any other required files/structure here
    
    print(f"\nCreated sample project directory with tests: {base_temp}")
    return base_temp 

@pytest.fixture(scope="session")
def code_server_process(): # Removed event_loop dependency
    """Starts the MCP Code Server on a fixed port (8083) for integration tests."""
    env = os.environ.copy()
    env["MCP_API_KEY"] = API_KEY
    env["MCP_CODE_PORT"] = "8083" # Use fixed port 8083
    server_url = f"http://localhost:{env['MCP_CODE_PORT']}" # For health check

    cmd = [sys.executable, "-m", "agents.mcp_code_server"]
    print(f"\nStarting Code Server: {' '.join(cmd)} on port {env['MCP_CODE_PORT']}...")
    process = subprocess.Popen(
        cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    # --- Health Check Loop (similar to test_server_process) --- 
    max_wait_time = 20 # seconds
    start_time = time.time()
    server_ready = False
    print(f"Waiting up to {max_wait_time}s for Code Server at {server_url}...")
    while time.time() - start_time < max_wait_time:
        if process.poll() is not None: # Check if process died
             stdout, stderr = process.communicate()
             print("Code Server failed to start:")
             print(f"STDOUT:\n{stdout.decode(errors='ignore')}")
             print(f"STDERR:\n{stderr.decode(errors='ignore')}")
             pytest.fail("MCP Code Server process terminated unexpectedly during startup.", pytrace=False)
        
        try:
            # Use requests for synchronous check
            response = requests.get(f"{server_url}/", timeout=1, headers={"X-API-Key": API_KEY})
            if response.status_code == 200:
                 print("Code Server is ready.")
                 server_ready = True
                 break
        except requests.exceptions.ConnectionError:
            pass # Server not up yet
        except requests.exceptions.Timeout:
            print("Connection attempt timed out...") 
        except Exception as e:
             print(f"Health check error: {e}") # Log other errors
             
        time.sleep(0.5) # Wait before retrying
    # --- End Health Check Loop ---

    if not server_ready:
        print("Code Server did not become ready within the time limit.")
        stdout, stderr = process.communicate() # Get final output
        print(f"Final STDOUT:\n{stdout.decode(errors='ignore')}")
        print(f"Final STDERR:\n{stderr.decode(errors='ignore')}")
        process.terminate()
        process.wait()
        pytest.fail(f"MCP Code Server failed to start within {max_wait_time} seconds.", pytrace=False)
    
    print(f"Code Server started (PID: {process.pid}) on {server_url}")
    yield process # Yield only the process object

    # --- Teardown ---
    print(f"\nTerminating Code Server ({server_url}, PID: {process.pid})...")
    process.terminate()
    try:
        process.wait(timeout=5)
        print(f"Code Server terminated.")
    except subprocess.TimeoutExpired:
        print("Code Server did not terminate gracefully, killing...")
        process.kill()
        process.wait()
        print("Code Server killed.")

@pytest.fixture(scope="session")
def test_server_process(): # Removed event_loop dependency
    """Starts the MCP Test Server as a background process, ensuring it's ready."""
    env = os.environ.copy()
    env["MCP_API_KEY"] = API_KEY
    env["MCP_TEST_PORT"] = "8082" # Keep this fixed for now unless conflicts arise
    server_url = f"http://localhost:{env['MCP_TEST_PORT']}"

    cmd = [sys.executable, "-m", "agents.mcp_test_server"]
    print(f"\nStarting Test Server: {' '.join(cmd)}")
    process = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # --- Health Check Loop --- 
    max_wait_time = 20 # seconds
    start_time = time.time()
    server_ready = False
    print(f"Waiting up to {max_wait_time}s for Test Server at {server_url}...")
    while time.time() - start_time < max_wait_time:
        if process.poll() is not None: # Check if process died
             stdout, stderr = process.communicate()
             print("Test Server failed to start:")
             print(f"STDOUT:\n{stdout.decode(errors='ignore')}")
             print(f"STDERR:\n{stderr.decode(errors='ignore')}")
             pytest.fail("MCP Test Server process terminated unexpectedly during startup.", pytrace=False)
        
        try:
            # Use requests for synchronous check within fixture
            response = requests.get(f"{server_url}/", timeout=1, headers={"X-API-Key": API_KEY})
            if response.status_code == 200:
                 print("Test Server is ready.")
                 server_ready = True
                 break
        except requests.exceptions.ConnectionError:
            pass # Server not up yet
        except requests.exceptions.Timeout:
            print("Connection attempt timed out...") 
        except Exception as e:
             print(f"Health check error: {e}") # Log other errors
             
        time.sleep(0.5) # Wait before retrying
    # --- End Health Check Loop ---

    if not server_ready:
        # If loop finishes without server being ready
        print("Test Server did not become ready within the time limit.")
        stdout, stderr = process.communicate() # Get final output
        print(f"Final STDOUT:\n{stdout.decode(errors='ignore')}")
        print(f"Final STDERR:\n{stderr.decode(errors='ignore')}")
        process.terminate()
        process.wait()
        pytest.fail(f"MCP Test Server failed to start within {max_wait_time} seconds.", pytrace=False)

    print(f"Test Server started (PID: {process.pid})")
    yield process
    
    print(f"\nTerminating Test Server (PID: {process.pid})...")
    process.terminate()
    try:
        process.wait(timeout=5)
        print("Test Server terminated.")
    except subprocess.TimeoutExpired:
        print("Test Server did not terminate gracefully, killing...")
        process.kill()
        process.wait()
        print("Test Server killed.")

# Updated mcp_agent fixture to use local Ollama
@pytest_asyncio.fixture(scope="function")
async def mcp_agent(code_server_process, test_server_process) -> AsyncGenerator[MCPEnhancedAgent, None]: # Add server fixtures as dependencies
    """Provides an initialized MCPEnhancedAgent instance configured for the running test servers."""
    # ollama_url = "http://localhost:11434" # Default local Ollama URL - No longer needed
    # api_key = "ollama" # API key for Ollama (adjust if needed) - No longer needed
    
    # print(f"Configuring agent to use local Ollama at: {ollama_url}") - Removed redundant print

    # Ensure servers are running (handled by fixture dependency)
    # Optional: Brief pause if needed
    await asyncio.sleep(0.5) # Add a short delay to allow servers to fully initialize after startup check

    async with aiohttp.ClientSession() as session:
        agent = MCPEnhancedAgent(
            code_server_url=CODE_SERVER_URL, # Use the defined code server URL
            test_server_url=TEST_SERVER_URL, # Use the defined test server URL
            session=session,
            api_key=API_KEY # Use the shared API key
        )
        yield agent

    # agent.close() is not needed here because the session is managed by the fixture 