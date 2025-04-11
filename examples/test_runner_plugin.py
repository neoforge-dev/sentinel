#!/usr/bin/env python3
"""
Plugin for connecting our agent with the MCP Test Server
Adds test running and analysis capabilities to the agent
"""

import os
import sys
import json
import requests
from typing import Dict, Any, List, Optional
import logging
import re

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from agents.agent import OllamaAgent, ToolConfig, TaskType
except ImportError:
    print("Error: Could not import from agents.agent. Make sure you're running from the project root.")
    sys.exit(1)

# Base URL for the MCP Test Server
try:
    MCP_TEST_SERVER_URL = os.environ.get("MCP_TEST_SERVER_URL", "http://localhost:8082")
    # API Key for authentication
    API_KEY = os.environ.get("AGENT_API_KEY")
    if not API_KEY:
        print("Warning: AGENT_API_KEY environment variable not set for MCP communication.", file=sys.stderr)
        API_KEY = None
except Exception as e:
    print(f"Error loading MCP configuration: {e}", file=sys.stderr)
    MCP_TEST_SERVER_URL = "http://localhost:8082" # Default fallback
    API_KEY = None

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Helper to get headers
def _get_headers() -> Dict[str, str]:
    """Returns headers for MCP requests, including API key if available."""
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    return headers

def run_tests_with_mcp(
    project_path: str,
    test_path: str = "tests",
    runner: str = "pytest",
    mode: str = "local",
    max_failures: Optional[int] = None,
    run_last_failed: bool = False,
    timeout: int = 300,
    max_tokens: int = 4000,
    docker_image: Optional[str] = None,
    additional_args: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Runs tests using the MCP Test Server. Handles streaming for local mode."""
    endpoint = f"{MCP_TEST_SERVER_URL}/run-tests"
    payload = {
        "project_path": project_path,
        "test_path": test_path,
        "runner": runner,
        "mode": mode,
        "max_failures": max_failures,
        "run_last_failed": run_last_failed,
        "timeout": timeout,
        "max_tokens": max_tokens,
        "docker_image": docker_image,
        "additional_args": additional_args
    }
    try:
        # Use stream=True for potential streaming response
        response = requests.post(endpoint, json=payload, headers=_get_headers(), stream=(mode == 'local')) 
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        
        if mode == 'local' and response.headers.get("content-type") == "text/plain":
            # Handle streaming response
            final_result_summary = {"status": "unknown", "summary": "Processing stream...", "id": "unknown"}
            print("--- Streaming Test Output --- ")
            full_output = ""
            for line in response.iter_lines(decode_unicode=True):
                if line:
                    print(line) # Print stream line by line
                    full_output += line + "\n"
                    # Attempt to parse final status line (example)
                    if line.startswith("--- Test run complete"): 
                        match = re.search(r"\((.*?)\). Status: (\w+)", line)
                        if match:
                            final_result_summary["id"] = match.group(1)
                            final_result_summary["status"] = match.group(2)
                            final_result_summary["summary"] = f"Run {match.group(1)} completed with status {match.group(2)}."
            print("--- End of Stream --- ")
            
            # Return a summary based on the stream, as the full JSON might not be available
            # Or potentially fetch the full result using the ID if needed
            return {
                "status": final_result_summary["status"],
                "summary": final_result_summary["summary"],
                "details": full_output, # Return captured stream as details
                "result_id": final_result_summary["id"]
            }
        else:
            # Handle non-streaming response (e.g., Docker mode or error)
            return response.json()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error running tests via MCP: {e}", exc_info=True)
        return {"status": "error", "summary": f"MCP request failed: {e}", "details": str(e)}


def get_last_failed_tests_with_mcp() -> Dict[str, Any]:
    """
    Get the list of last failed tests
    """
    # Need project_path for the server endpoint
    # This tool might need refinement if project_path isn't available
    # For now, let's assume it needs to be passed or configured
    # Placeholder - this needs a project_path ideally!
    project_path = "." # Or get from config/context? 
    url = f"{MCP_TEST_SERVER_URL}/last-failed?project_path={project_path}" 
    
    try:
        response = requests.get(url, headers=_get_headers())
        response.raise_for_status()
        return {
            "success": True,
            "failed_tests": response.json()
        }
    except requests.exceptions.HTTPError as http_err:
        return {
            "success": False,
            "message": f"HTTP error getting last failed tests: {http_err}",
            "details": response.text if 'response' in locals() else str(http_err)
        }
    except requests.exceptions.RequestException as req_err:
        return {
            "success": False,
            "message": f"Error connecting for last failed tests: {req_err}",
            "details": str(req_err)
        }
    except Exception as e:
         return {
            "success": False,
            "message": f"An unexpected error occurred: {e}",
            "details": str(e)
        }


def get_test_result_with_mcp(result_id: str) -> Dict[str, Any]:
    """
    Get a specific test result
    """
    url = f"{MCP_TEST_SERVER_URL}/results/{result_id}"
    
    try:
        response = requests.get(url, headers=_get_headers())
        response.raise_for_status()
        # Assuming success returns the JSON directly
        return response.json() 
    except requests.exceptions.HTTPError as http_err:
        status_code = http_err.response.status_code
        error_detail = response.text if 'response' in locals() else str(http_err)
        if status_code == 404:
            message = f"Test result '{result_id}' not found."
        else:
            message = f"HTTP error retrieving test result: {http_err}"
            
        return {
            "success": False,
            "status": "error",
            "message": message,
            "details": error_detail
        }
    except requests.exceptions.RequestException as req_err:
        return {
            "success": False,
            "status": "error",
            "message": f"Error connecting to retrieve test result: {req_err}",
            "details": str(req_err)
        }
    except Exception as e:
         return {
            "success": False,
            "status": "error",
            "message": f"An unexpected error occurred: {e}",
            "details": str(e)
        }


def apply_fix_and_retest(code: str, file_path: str, project_path: str) -> Dict[str, Any]:
    """
    Test if a code fix resolves failing tests by applying it temporarily and running tests.
    
    This function:
    1. Gets the list of currently failing tests.
    2. Creates a backup of the original file.
    3. Applies the provided code fix to the original file.
    4. Runs only the previously failing tests using the MCP test server.
    5. Restores the original file from backup.
    6. Returns the test result, indicating if the fix was successful.
    """
    # Get current failing tests
    last_failed = get_last_failed_tests_with_mcp()
    
    if not last_failed.get("success"):
        return {
            "success": False,
            "message": last_failed.get("message", "Could not get last failed tests")
        }
    
    failed_tests = last_failed.get("failed_tests", [])
    if not failed_tests:
        return {
            "success": False,
            "message": "No failing tests to fix"
        }
    
    # Create a temporary copy of the file
    import tempfile
    import shutil
    import os
    
    # Make sure the project path is absolute
    project_path = os.path.abspath(project_path)
    
    # Check if file_path is absolute, if not make it relative to project_path
    if not os.path.isabs(file_path):
        full_path = os.path.join(project_path, file_path)
    else:
        full_path = file_path
    
    # Check if file exists
    if not os.path.exists(full_path):
        return {
            "success": False,
            "message": f"File not found: {file_path}"
        }
    
    # Create a backup of the original file
    backup_file = None
    try:
        # Create a temporary file with the original content
        fd, backup_file = tempfile.mkstemp(suffix=".py.bak")
        os.close(fd)
        
        # Backup original file
        shutil.copy2(full_path, backup_file)
        
        # Write new code to the original file
        with open(full_path, "w") as f:
            f.write(code)
        
        # Run the failing tests
        result = run_tests_with_mcp(
            project_path=project_path,
            test_path=" ".join(failed_tests),  # Pass specific failed tests
            runner="pytest",
            max_failures=None,  # Run all tests
            run_last_failed=True,  # Run only the previously failing tests
            max_tokens=6000  # Higher token limit for detailed results
        )
        
        # Check if the tests now pass
        passing = result.get("status") == "success"
        
        # Add more helpful information
        result["code_fixed_the_issue"] = passing
        result["file_tested"] = file_path
        
        # If tests still fail, get a summary of remaining failures
        if not passing:
            still_failing = result.get("failed_tests", [])
            result["fixed_tests"] = [test for test in failed_tests if test not in still_failing]
            result["still_failing_tests"] = still_failing
        else:
            result["fixed_tests"] = failed_tests
            result["still_failing_tests"] = []
        
        return result
    
    finally:
        # Restore the original file
        if backup_file and os.path.exists(backup_file):
            shutil.copy2(backup_file, full_path)
            os.unlink(backup_file)


def analyze_test_failures(project_path: str) -> Dict[str, Any]:
    """
    Analyze test failures and generate a summary with an LLM
    
    This function:
    1. Gets the latest test results
    2. Asks the LLM to analyze the failures
    3. Returns a structured analysis
    """
    # Get last failed tests
    last_failed = get_last_failed_tests_with_mcp()
    
    if not last_failed.get("success"):
        return {
            "success": False,
            "message": last_failed.get("message", "Could not get last failed tests")
        }
    
    failed_tests = last_failed.get("failed_tests", [])
    if not failed_tests:
        return {
            "success": True,
            "message": "No failing tests to analyze",
            "analysis": "All tests are passing."
        }
    
    # Run the tests again to get fresh results
    result = run_tests_with_mcp(
        project_path=project_path,
        test_path="",  # We'll specify individual tests
        runner="pytest",
        max_failures=None,
        run_last_failed=True
    )
    
    if result.get("status") == "error":
        return {
            "success": False,
            "message": result.get("summary", "Error running tests")
        }
    
    # Get test details for analysis
    test_details = result.get("details", "")
    
    # Use the parent agent to analyze the failures
    agent = OllamaAgent(mcp_enabled=False)
    
    prompt = f"""
    Analyze these test failures and provide a concise, structured report.
    For each issue:
    1. Explain the root cause
    2. Suggest a specific fix with code examples
    
    Test Failures:
    {test_details}
    
    Format your response as a JSON object with these keys:
    - summary: A one-paragraph overview of the issues
    - failures: A list of failure objects, each containing:
      - test_name: The name of the failing test
      - cause: The root cause of the failure
      - fix: A suggested fix with code example
    - general_recommendations: Any broader recommendations
    
    Keep it concise and actionable.
    """
    
    try:
        analysis_text = agent.generate(prompt, task_type=TaskType.CODE_GENERATION)
        
        # Try to extract JSON
        try:
            # Look for JSON in the response
            import re
            json_match = re.search(r'```(?:json)?\s*(\{[\s\S]*\})\s*```', analysis_text)
            if json_match:
                analysis = json.loads(json_match.group(1))
            else:
                # Try to extract the entire content as JSON
                analysis = json.loads(analysis_text)
        except json.JSONDecodeError:
            # If JSON parsing fails, return the raw analysis
            analysis = {
                "summary": "Failed to parse structured analysis",
                "failures": [],
                "general_recommendations": "See the raw analysis below",
                "raw_analysis": analysis_text
            }
        
        return {
            "success": True,
            "analysis": analysis,
            "test_result": result
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error analyzing test failures: {str(e)}",
            "test_result": result
        }


def register_test_tools(agent: OllamaAgent):
    """
    Register test running and analysis tools with the agent
    """
    # Run Tests Tool
    agent.register_tool(
        ToolConfig(
            name="run_tests",
            description="Run tests in a Python project using pytest, unittest, or uv",
            parameters={
                "project_path": "Path to the project directory",
                "test_path": "Path to test directory or file (default: 'tests')",
                "runner": "Test runner to use: pytest, unittest, or uv (default: pytest)",
                "mode": "Execution mode: local or docker (default: local)",
                "max_failures": "Stop after N failures (default: None)",
                "run_last_failed": "Run only the last failed tests (default: False)"
            },
            function=run_tests_with_mcp
        )
    )
    
    # Get Last Failed Tests Tool
    agent.register_tool(
        ToolConfig(
            name="get_last_failed_tests",
            description="Get the list of last failed tests",
            parameters={},
            function=get_last_failed_tests_with_mcp
        )
    )
    
    # Test Fix Tool
    agent.register_tool(
        ToolConfig(
            name="test_fix",
            description="Test if a code fix resolves failing tests",
            parameters={
                "code": "The fixed code to test",
                "file_path": "Path to the file being fixed",
                "project_path": "Path to the project directory"
            },
            function=apply_fix_and_retest
        )
    )
    
    # Analyze Failures Tool
    agent.register_tool(
        ToolConfig(
            name="analyze_test_failures",
            description="Analyze test failures and generate a structured report with fix suggestions",
            parameters={
                "project_path": "Path to the project directory"
            },
            function=analyze_test_failures
        )
    )


if __name__ == "__main__":
    # Example usage
    agent = OllamaAgent(model="mistral:7b")
    register_test_tools(agent)
    
    # Get current directory to use as project path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(current_dir)  # Parent of examples directory
    
    print(f"=== MCP Test Runner Plugin Example ===")
    print(f"Using project directory: {project_dir}")
    
    # Example test run
    print("\nRunning tests...")
    result = agent.execute_tool("run_tests", {
        "project_path": project_dir,
        "test_path": "tests" if os.path.exists(os.path.join(project_dir, "tests")) else ".",
        "runner": "pytest",
        "mode": "local"
    })
    
    # Display result summary
    status = result.get("status", "unknown")
    print(f"Test Status: {status}")
    
    if status == "failure":
        # Get failed tests
        print("\nGetting failed tests...")
        failed_result = agent.execute_tool("get_last_failed_tests", {})
        
        if failed_result.get("success"):
            failed_tests = failed_result.get("failed_tests", [])
            print(f"Found {len(failed_tests)} failed tests:")
            for i, test in enumerate(failed_tests, 1):
                print(f"  {i}. {test}")
            
            # Analyze failures
            print("\nAnalyzing test failures...")
            analysis_result = agent.execute_tool("analyze_test_failures", {
                "project_path": project_dir
            })
            
            if analysis_result.get("success"):
                analysis = analysis_result.get("analysis", {})
                print("\nTest Failure Analysis:")
                print(f"Summary: {analysis.get('summary', 'No summary available')}")
                
                if "failures" in analysis:
                    print("\nFailure Details:")
                    for i, failure in enumerate(analysis.get("failures", []), 1):
                        print(f"  {i}. Test: {failure.get('test_name', 'Unknown test')}")
                        print(f"     Cause: {failure.get('cause', 'Unknown cause')}")
                        print(f"     Fix: {failure.get('fix', 'No fix suggested')}")
            else:
                print(f"Error analyzing failures: {analysis_result.get('message')}")
    
    print("\n=== Available Tools ===")
    for name, tool in agent.context.tools.items():
        if name.startswith("run_") or name.startswith("test_") or name.startswith("analyze_") or name.startswith("get_"):
            print(f"- {name}: {tool.description}") 