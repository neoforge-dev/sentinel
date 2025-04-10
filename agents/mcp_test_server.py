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
import asyncio
import logging
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field
import uvicorn
import tiktoken
from fastapi.middleware.cors import CORSMiddleware

# Add src directory to path so we can import storage modules
# sys.path.append(str(Path(__file__).resolve().parent.parent))
# No longer needed with pytest.ini configuration
from storage.database import get_db_manager, DatabaseManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("mcp-test-server")

# Initialize FastAPI
app = FastAPI(title="MCP Test Server", description="MCP server for running and analyzing Python tests")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for test results
test_results = {}
last_failed_tests = set()

# Token counter for output limitations
def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count the number of tokens in a string"""
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except Exception as e:
        logger.warning(f"Error counting tokens: {e}")
        # Rough approximation: average 4 chars per token
        return len(text) // 4


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
    project_path: str
    test_path: Optional[str]
    runner: str
    execution_mode: str
    status: str
    summary: str
    details: str
    passed_tests: List[str] = []
    failed_tests: List[str] = []
    skipped_tests: List[str] = []
    execution_time: float
    created_at: datetime = Field(default_factory=datetime.now)


# Function to store test results
def store_test_result(result: TestResult) -> str:
    """Store a test result and return its ID"""
    result_id = result.id
    test_results[result_id] = result
    return result_id


# Function to retrieve a stored test result
def get_test_result(result_id: str) -> Optional[TestResult]:
    """Get a test result by ID"""
    return test_results.get(result_id)


# Function to list all stored test result IDs
def list_test_results() -> List[str]:
    """List all test result IDs"""
    return list(test_results.keys())


def clean_test_output(output: str, max_tokens: int = 4000) -> str:
    """Clean test output to make it more readable"""
    # Remove ANSI color codes
    output = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', output)
    
    # Remove common noise patterns
    output = re.sub(r'===+', '===', output)
    output = re.sub(r'---+', '---', output)
    output = re.sub(r'\n\s*\n\s*\n', '\n\n', output)
    
    # Truncate if too long
    if count_tokens(output) > max_tokens:
        # Split by lines and keep the first and last parts
        lines = output.splitlines()
        half_lines = max(1, (max_tokens // 8) // 2)  # Approximation
        
        # Keep first half_lines and last half_lines
        selected_lines = lines[:half_lines]
        selected_lines.append("... [output truncated] ...")
        selected_lines.extend(lines[-half_lines:])
        
        output = '\n'.join(selected_lines)
    
    return output


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


async def run_tests_local(config: TestExecutionConfig, db: DatabaseManager) -> TestResult:
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
    
    logger.info(f"Running command: {' '.join(cmd)}")
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=config.project_path
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=config.timeout
            )
        except asyncio.TimeoutError:
            process.terminate()
            end_time = time.time()
            
            # Create result for timeout
            result = TestResult(
                id=result_id,
                project_path=config.project_path,
                test_path=config.test_path,
                runner=config.runner.value,
                execution_mode=config.mode.value,
                status="timeout",
                summary=f"Tests timed out after {config.timeout} seconds",
                details=f"Command: {' '.join(cmd)}\nTests timed out after {config.timeout} seconds",
                execution_time=end_time - start_time,
                passed_tests=[],
                failed_tests=[],
                skipped_tests=[]
            )
            
            # Store the result in the database
            await db.store_test_result(
                result_id=result.id,
                status=result.status,
                summary=result.summary,
                details=result.details,
                passed_tests=result.passed_tests,
                failed_tests=[(t, "Timed out") for t in last_failed_tests], # Approximation for timeout
                skipped_tests=result.skipped_tests,
                execution_time=result.execution_time,
                config=config.model_dump() # Pass the original config dict
            )
            
            return result
            
        output = stdout.decode() + stderr.decode()
        cleaned_output = clean_test_output(output, config.max_tokens)
        
        end_time = time.time()
        
        # Extract test results
        results = extract_test_results(cleaned_output)
        last_failed_tests = set(results["failed"])
        
        # Get summary
        summary = extract_test_summary(cleaned_output)
        
        # Truncate to token limit
        details = truncate_to_token_limit(cleaned_output, config.max_tokens)
        
        # Determine test status
        status = "passed"
        if process.returncode != 0:
            status = "failed"
        
        # Create result object
        result = TestResult(
            id=result_id,
            project_path=config.project_path,
            test_path=config.test_path,
            runner=config.runner.value,
            execution_mode=config.mode.value,
            status=status,
            summary=summary,
            details=details,
            passed_tests=results["passed"],
            failed_tests=results["failed"], # Store raw list in object for now
            skipped_tests=results["skipped"],
            execution_time=end_time - start_time
        )
        
        # Format failed tests for database storage (List[Tuple[str, str]])
        failed_tests_for_db = [(test_name, "See details") for test_name in results["failed"]]

        # Store the result in the database
        await db.store_test_result(
            result_id=result.id,
            status=result.status,
            summary=result.summary,
            details=result.details,
            passed_tests=results["passed"],
            failed_tests=failed_tests_for_db, # Pass the correctly formatted list
            skipped_tests=results["skipped"],
            execution_time=result.execution_time,
            config=config.model_dump() # Pass the original config dict
        )
        
        return result
    
    except Exception as e:
        end_time = time.time()
        
        # Create result for error
        result_id = str(uuid.uuid4())
        result = TestResult(
            id=result_id,
            project_path=config.project_path,
            test_path=config.test_path,
            runner=config.runner.value,
            execution_mode=config.mode.value,
            status="error",
            summary=f"Error running tests: {str(e)}",
            details=f"Command: {' '.join(cmd)}\nError: {str(e)}",
            execution_time=end_time - start_time,
            passed_tests=[],
            failed_tests=[],
            skipped_tests=[]
        )
        
        # Store the result in the database
        await db.store_test_result(
            result_id=result.id,
            status=result.status,
            summary=result.summary,
            details=result.details,
            passed_tests=result.passed_tests,
            failed_tests=[(t, "Error during execution") for t in last_failed_tests], # Approximation for error
            skipped_tests=result.skipped_tests,
            execution_time=result.execution_time,
            config=config.model_dump() # Pass the original config dict
        )
        
        return result


async def run_tests_docker(config: TestExecutionConfig, db: DatabaseManager) -> TestResult:
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
            output = container.logs().decode('utf-8')
            cleaned_output = clean_test_output(output, config.max_tokens)
            
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
                project_path=config.project_path,
                test_path=config.test_path,
                runner=config.runner.value,
                execution_mode=config.mode.value,
                status="success" if exit_code == 0 else "failed",
                summary=summary,
                details=details,
                passed_tests=results["passed"],
                failed_tests=results["failed"],
                skipped_tests=results["skipped"],
                execution_time=time.time() - start_time
            )
            
            # Store the result in the database
            await db.store_test_result(
                result_id=test_result.id,
                status=test_result.status,
                summary=test_result.summary,
                details=test_result.details,
                passed_tests=test_result.passed_tests,
                failed_tests=test_result.failed_tests,
                skipped_tests=test_result.skipped_tests,
                execution_time=test_result.execution_time,
                config=config.model_dump() # Pass the original config dict
            )
            
        except Exception as e:
            container.stop()
            raise e
        finally:
            # Cleanup
            container.remove()
        
        return test_result
    
    except ImportError:
        test_result = TestResult(
            id=result_id,
            project_path=config.project_path,
            test_path=config.test_path,
            runner=config.runner.value,
            execution_mode=config.mode.value,
            status="error",
            summary="Docker Python package not installed",
            details="Please install the docker package: pip install docker",
            execution_time=time.time() - start_time,
            passed_tests=[],
            failed_tests=[(t, "Docker import error") for t in last_failed_tests], # Approximation
            skipped_tests=[]
        )
        await db.store_test_result(
            result_id=test_result.id,
            status=test_result.status,
            summary=test_result.summary,
            details=test_result.details,
            passed_tests=test_result.passed_tests,
            failed_tests=[(t, "Docker import error") for t in last_failed_tests], # Approximation
            skipped_tests=test_result.skipped_tests,
            execution_time=test_result.execution_time,
            config=config.model_dump() # Pass the original config dict
        )
        return test_result
    except Exception as e:
        test_result = TestResult(
            id=result_id,
            project_path=config.project_path,
            test_path=config.test_path,
            runner=config.runner.value,
            execution_mode=config.mode.value,
            status="error",
            summary=f"Error running tests in Docker: {str(e)}",
            details=str(e),
            execution_time=time.time() - start_time,
            passed_tests=[],
            failed_tests=[(t, "Docker execution error") for t in last_failed_tests], # Approximation
            skipped_tests=[]
        )
        await db.store_test_result(
            result_id=test_result.id,
            status=test_result.status,
            summary=test_result.summary,
            details=test_result.details,
            passed_tests=test_result.passed_tests,
            failed_tests=[(t, "Docker execution error") for t in last_failed_tests], # Approximation
            skipped_tests=test_result.skipped_tests,
            execution_time=test_result.execution_time,
            config=config.model_dump() # Pass the original config dict
        )
        return test_result


@app.get("/")
async def root():
    """Root endpoint"""
    return {"status": "active", "service": "MCP Test Server"}


@app.post("/run-tests", response_model=TestResult)
async def run_tests(config: TestExecutionConfig, background_tasks: BackgroundTasks, db: DatabaseManager = Depends(get_db_manager)):
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
        return await run_tests_local(config, db)
    else:
        return await run_tests_docker(config, db)


@app.get("/results/{result_id}", response_model=TestResult)
async def get_test_result(result_id: str, db: DatabaseManager = Depends(get_db_manager)):
    """Get the result of a previous test run"""
    result = await db.get_test_result(result_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Test result not found: {result_id}")
    
    return result


@app.get("/results", response_model=List[str])
async def list_test_results(db: DatabaseManager = Depends(get_db_manager)):
    """List all test result IDs"""
    results = await db.list_test_results()
    return [r["id"] for r in results]


@app.get("/last-failed", response_model=List[str])
async def get_last_failed_tests(project_path: str, db: DatabaseManager = Depends(get_db_manager)):
    """Get the list of last failed tests"""
    failed_tests = await db.get_last_failed_tests(project_path)
    return failed_tests


# Database dependency
async def get_db():
    """Dependency to get database manager."""
    db_manager = get_db_manager()
    await db_manager.connect()
    try:
        yield db_manager
    finally:
        await db_manager.disconnect()


# Set up application startup
@app.on_event("startup")
async def startup_event():
    """Initialize the database on startup."""
    db_manager = get_db_manager()
    await db_manager.connect()
    await db_manager.create_tables()
    await db_manager.disconnect()
    logger.info("MCP Test Server initialized")


def main():
    """Run the server"""
    port = int(os.environ.get("MCP_TEST_PORT", "8082"))
    host = os.environ.get("MCP_TEST_HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main() 