#!/usr/bin/env python3
"""
MCP Test Server for running and analyzing Python tests

Dependencies:
- fastapi==0.104.1
- uvicorn==0.23.2
- pydantic==2.4.2
- tiktoken==0.5.1
- docker==6.1.3
"""
# [dependencies]
# fastapi = "^0.104.1"
# uvicorn = "^0.23.2"
# pydantic = "^2.4.2"
# tiktoken = "^0.5.1"
# docker = "^6.1.3"

import os
import sys
import json
import re
import time
import tempfile
import subprocess
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Set
from enum import Enum
import uuid

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
import uvicorn
import tiktoken

# Initialize FastAPI
app = FastAPI(title="MCP Test Server", description="MCP server for running and analyzing Python tests")

# In-memory storage for test results
test_results = {}
last_failed_tests = set()

# Token counter for output limitations
def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count the number of tokens in a string"""
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except:
        # Fallback approximation (words / 0.75)
        return int(len(text.split()) / 0.75)


class TestRunner(str, Enum):
    """Test runner options"""
    PYTEST = "pytest"
    UNITTEST = "unittest"
    UV = "uv"


class ExecutionMode(str, Enum):
    """Test execution mode"""
    LOCAL = "local"
    DOCKER = "docker"


class TestExecutionConfig(BaseModel):
    """Configuration for test execution"""
    project_path: str = Field(..., description="Absolute path to the project directory")
    test_path: str = Field("tests", description="Path to test directory or file, relative to project_path")
    runner: TestRunner = Field(TestRunner.PYTEST, description="Test runner to use")
    mode: ExecutionMode = Field(ExecutionMode.LOCAL, description="Execution mode (local or docker)")
    max_failures: Optional[int] = Field(None, description="Stop after N failures (None to run all)")
    run_last_failed: bool = Field(False, description="Run only the last failed tests")
    timeout: int = Field(300, description="Timeout in seconds")
    max_tokens: int = Field(4000, description="Maximum tokens for output")
    docker_image: Optional[str] = Field(None, description="Docker image to use (defaults to python:3.11)")
    additional_args: List[str] = Field(default_factory=list, description="Additional arguments for the test runner")


class TestResult(BaseModel):
    """Result of a test execution"""
    id: str
    status: str
    summary: str
    details: str
    passed_tests: List[str] = []
    failed_tests: List[str] = []
    skipped_tests: List[str] = []
    execution_time: float
    timestamp: float
    command: str
    token_count: int


def clean_test_output(output: str) -> str:
    """Clean test output to make it more readable"""
    # Remove ANSI escape sequences
    output = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', output)
    
    # Remove unnecessary path prefixes
    output = re.sub(r'(\/.*\/)*([^\/]+\.py)', r'\2', output)
    
    # Remove timestamps
    output = re.sub(r'\[\d{2}:\d{2}:\d{2}\]', '', output)
    
    # Remove duplicate newlines
    output = re.sub(r'\n{3,}', '\n\n', output)
    
    return output.strip()


def extract_test_results(output: str) -> Dict[str, List[str]]:
    """Extract lists of passed, failed, and skipped tests"""
    results = {
        "passed": [],
        "failed": [],
        "skipped": []
    }
    
    # Extract failed tests - adapt these patterns to your test runner's output
    for line in output.split('\n'):
        if 'FAILED' in line and '.py::' in line:
            test_name = re.search(r'([^\s]+\.py::[^\s]+)', line)
            if test_name:
                results["failed"].append(test_name.group(1))
        elif 'PASSED' in line and '.py::' in line:
            test_name = re.search(r'([^\s]+\.py::[^\s]+)', line)
            if test_name:
                results["passed"].append(test_name.group(1))
        elif 'SKIPPED' in line and '.py::' in line:
            test_name = re.search(r'([^\s]+\.py::[^\s]+)', line)
            if test_name:
                results["skipped"].append(test_name.group(1))
                
    return results


def extract_test_summary(output: str) -> str:
    """Extract the test summary from the output"""
    # Look for summary sections - adapt to your test runner's output
    summary_patterns = [
        r'===+\s*FAILURES\s*===+\n(.*?)(?=\n===+|$)',
        r'===+\s*summary\s*===+\n(.*?)(?=\n===+|$)',
        r'========.*\n(.*?)(?=\n===+|$)',
        r'Ran\s+\d+\s+tests.*\n(.*?)(?=\n|$)'
    ]
    
    for pattern in summary_patterns:
        match = re.search(pattern, output, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    # Fallback: last few lines
    lines = output.strip().split("\n")
    if len(lines) > 5:
        return "\n".join(lines[-5:])
    return output.strip()


def truncate_to_token_limit(text: str, max_tokens: int) -> str:
    """Truncate text to fit within token limit, preserving the most important parts"""
    current_tokens = count_tokens(text)
    if current_tokens <= max_tokens:
        return text
    
    # Split into sections to preserve important parts
    lines = text.split('\n')
    
    # Find test failures section
    failure_start = -1
    for i, line in enumerate(lines):
        if re.match(r'^=+\s*FAILURES\s*=+$', line, re.IGNORECASE):
            failure_start = i
            break
    
    # If we found failures section, prioritize it
    if failure_start >= 0:
        # Keep header, summary, and failures
        header = '\n'.join(lines[:10])
        failures = '\n'.join(lines[failure_start:])
        summary = '\n'.join(lines[-10:])
        
        # Combine with priority to failures
        parts = [
            failures,
            "...[truncated for token limit]...\n",
            summary
        ]
        
        combined = '\n'.join(parts)
        if count_tokens(combined) <= max_tokens:
            return combined
        
        # Still too long, truncate failures
        failure_lines = failures.split('\n')
        # Keep first 3 errors in detail
        important_failures = []
        current_error = []
        error_count = 0
        
        for line in failure_lines:
            if re.match(r'^_+\s*.*\s*_+$', line) and current_error:
                important_failures.extend(current_error)
                current_error = [line]
                error_count += 1
                if error_count >= 3:
                    important_failures.append("...[more errors truncated]...")
                    break
            else:
                current_error.append(line)
        
        if current_error:
            important_failures.extend(current_error)
        
        parts = [
            '\n'.join(important_failures),
            "...[truncated for token limit]...\n",
            summary
        ]
        return '\n'.join(parts)
    
    # No failure section found, keep beginning and end
    beginning = '\n'.join(lines[:20])
    ending = '\n'.join(lines[-20:])
    
    return f"{beginning}\n...[truncated for token limit]...\n{ending}"


async def run_tests_local(config: TestExecutionConfig) -> TestResult:
    """Run tests locally using the specified configuration"""
    global last_failed_tests  # Declare the global variable at the start of the function
    start_time = time.time()
    result_id = str(uuid.uuid4())
    
    cmd = []
    if config.runner == TestRunner.UV:
        cmd = ["uv", "run", "-m", "pytest"]
    elif config.runner == TestRunner.PYTEST:
        cmd = ["python", "-m", "pytest"]
    elif config.runner == TestRunner.UNITTEST:
        cmd = ["python", "-m", "unittest"]
    
    # Add test path
    test_path = os.path.join(config.project_path, config.test_path)
    cmd.append(test_path)
    
    # Add max failures if specified
    if config.max_failures is not None:
        cmd.extend(["-x" if config.max_failures == 1 else f"--maxfail={config.max_failures}"])
    
    # Add last failed tests if requested
    if config.run_last_failed and last_failed_tests:
        for test in last_failed_tests:
            cmd.append(test)
    
    # Add verbose output
    cmd.append("-v")
    
    # Add any additional arguments
    cmd.extend(config.additional_args)
    
    try:
        process = subprocess.run(
            cmd,
            cwd=config.project_path,
            capture_output=True,
            text=True,
            timeout=config.timeout
        )
        
        # Process output
        output = process.stdout + "\n" + process.stderr
        cleaned_output = clean_test_output(output)
        
        # Extract test results
        results = extract_test_results(cleaned_output)
        last_failed_tests = set(results["failed"])
        
        # Get summary
        summary = extract_test_summary(cleaned_output)
        
        # Truncate to token limit
        details = truncate_to_token_limit(cleaned_output, config.max_tokens)
        
        # Create result
        test_result = TestResult(
            id=result_id,
            status="success" if process.returncode == 0 else "failure",
            summary=summary,
            details=details,
            passed_tests=results["passed"],
            failed_tests=results["failed"],
            skipped_tests=results["skipped"],
            execution_time=time.time() - start_time,
            timestamp=start_time,
            command=" ".join(cmd),
            token_count=count_tokens(details)
        )
        
        # Store result
        test_results[result_id] = test_result
        
        return test_result
    
    except subprocess.TimeoutExpired:
        return TestResult(
            id=result_id,
            status="timeout",
            summary="Test execution timed out",
            details=f"Test execution timed out after {config.timeout} seconds",
            execution_time=time.time() - start_time,
            timestamp=start_time,
            command=" ".join(cmd),
            token_count=0
        )
    except Exception as e:
        return TestResult(
            id=result_id,
            status="error",
            summary=f"Error running tests: {str(e)}",
            details=str(e),
            execution_time=time.time() - start_time,
            timestamp=start_time,
            command=" ".join(cmd),
            token_count=0
        )


async def run_tests_docker(config: TestExecutionConfig) -> TestResult:
    """Run tests in Docker container"""
    global last_failed_tests  # Declare the global variable at the start of the function
    start_time = time.time()
    result_id = str(uuid.uuid4())
    
    try:
        import docker
        
        # Create Docker client
        client = docker.from_env()
        
        # Prepare command
        cmd = []
        if config.runner == TestRunner.UV:
            cmd = ["uv", "run", "-m", "pytest"]
        elif config.runner == TestRunner.PYTEST:
            cmd = ["python", "-m", "pytest"]
        elif config.runner == TestRunner.UNITTEST:
            cmd = ["python", "-m", "unittest"]
        
        # Add test path (relative to /app in container)
        test_path = os.path.join("/app", config.test_path)
        cmd.append(test_path)
        
        # Add max failures if specified
        if config.max_failures is not None:
            cmd.extend(["-x" if config.max_failures == 1 else f"--maxfail={config.max_failures}"])
        
        # Add last failed tests if requested
        if config.run_last_failed and last_failed_tests:
            for test in last_failed_tests:
                cmd.append(test)
        
        # Add verbose output
        cmd.append("-v")
        
        # Add any additional arguments
        cmd.extend(config.additional_args)
        
        # Run container
        docker_image = config.docker_image or "python:3.11"
        
        container = client.containers.run(
            docker_image,
            command=" ".join(cmd),
            volumes={config.project_path: {'bind': '/app', 'mode': 'rw'}},
            working_dir="/app",
            detach=True
        )
        
        # Wait for container to finish with timeout
        try:
            container.wait(timeout=config.timeout)
            output = container.logs().decode('utf-8')
            cleaned_output = clean_test_output(output)
            
            # Extract test results
            results = extract_test_results(cleaned_output)
            last_failed_tests = set(results["failed"])
            
            # Get summary
            summary = extract_test_summary(cleaned_output)
            
            # Truncate to token limit
            details = truncate_to_token_limit(cleaned_output, config.max_tokens)
            
            container_info = container.inspect()
            exit_code = container_info["State"]["ExitCode"]
            
            # Create result
            test_result = TestResult(
                id=result_id,
                status="success" if exit_code == 0 else "failure",
                summary=summary,
                details=details,
                passed_tests=results["passed"],
                failed_tests=results["failed"],
                skipped_tests=results["skipped"],
                execution_time=time.time() - start_time,
                timestamp=start_time,
                command=" ".join(cmd),
                token_count=count_tokens(details)
            )
        except Exception as e:
            container.stop()
            raise e
        finally:
            # Cleanup
            container.remove()
        
        # Store result
        test_results[result_id] = test_result
        
        return test_result
    
    except ImportError:
        return TestResult(
            id=result_id,
            status="error",
            summary="Docker Python package not installed",
            details="Please install the docker package: pip install docker",
            execution_time=time.time() - start_time,
            timestamp=start_time,
            command="",
            token_count=0
        )
    except Exception as e:
        return TestResult(
            id=result_id,
            status="error",
            summary=f"Error running tests in Docker: {str(e)}",
            details=str(e),
            execution_time=time.time() - start_time,
            timestamp=start_time,
            command="",
            token_count=0
        )


@app.get("/")
async def root():
    """Root endpoint"""
    return {"status": "active", "service": "MCP Test Server"}


@app.post("/run-tests", response_model=TestResult)
async def run_tests(config: TestExecutionConfig, background_tasks: BackgroundTasks):
    """Run tests with the given configuration"""
    # Validate project path
    if not os.path.isdir(config.project_path):
        raise HTTPException(status_code=400, detail=f"Project path not found: {config.project_path}")
    
    # Check test path
    test_path = os.path.join(config.project_path, config.test_path)
    if not os.path.exists(test_path):
        raise HTTPException(status_code=400, detail=f"Test path not found: {test_path}")
    
    # Run tests based on mode
    if config.mode == ExecutionMode.LOCAL:
        return await run_tests_local(config)
    else:
        return await run_tests_docker(config)


@app.get("/results/{result_id}", response_model=TestResult)
async def get_test_result(result_id: str):
    """Get the result of a previous test run"""
    if result_id not in test_results:
        raise HTTPException(status_code=404, detail=f"Test result not found: {result_id}")
    
    return test_results[result_id]


@app.get("/results", response_model=List[str])
async def list_test_results():
    """List all test result IDs"""
    return list(test_results.keys())


@app.get("/last-failed", response_model=List[str])
async def get_last_failed_tests():
    """Get the list of last failed tests"""
    return list(last_failed_tests)


def main():
    """Run the server"""
    port = int(os.environ.get("MCP_TEST_PORT", "8082"))
    host = os.environ.get("MCP_TEST_HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main() 