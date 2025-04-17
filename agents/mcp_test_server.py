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
# NOTE: Direct script execution requires PYTHONPATH=.:src:agents for 'from src...' imports to work. See .neorules for details.
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
from typing import List, Dict, Any, Optional, Union, Set, AsyncGenerator
from enum import Enum
import uuid
import asyncio
import logging
import traceback
from datetime import datetime
import inspect

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import uvicorn
import tiktoken
from fastapi.middleware.cors import CORSMiddleware

# Add src directory to path so we can import storage modules
root = Path(__file__).resolve().parent.parent
src_path = root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
from src.storage.database import get_db_manager, DatabaseManager, get_request_db_manager
from src.security import verify_api_key

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
    NOSE2 = "nose2"
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


def extract_test_results(output: str, runner: TestRunner) -> Dict[str, List[str]]:
    """Extract lists of passed, failed, and skipped tests based on the runner"""
    results = {
        "passed": [],
        "failed": [],
        "skipped": []
    }
    
    # Runner-specific parsing
    if runner in [TestRunner.UNITTEST, TestRunner.NOSE2]:
        # Pattern for unittest/nose2 style: test_method (module.class) ... ok/FAIL/ERROR/SKIP
        pattern = re.compile(r"^(test_\w+)\s+\((.*?)\)\s+\.\.\.\s+(\w+)", re.MULTILINE)
        for match in pattern.finditer(output):
            test_name = f"{match.group(2)}.{match.group(1)}" # Combine class/module with method
            outcome = match.group(3).lower()
            
            if outcome == "ok":
                if test_name not in results["passed"]: # Avoid duplicates
                     results["passed"].append(test_name)
            elif outcome == "fail" or outcome == "error": # Treat errors as failures for this list
                if test_name not in results["failed"]: # Avoid duplicates
                    results["failed"].append(test_name)
            elif outcome == "skip":
                if test_name not in results["skipped"]: # Avoid duplicates
                    results["skipped"].append(test_name)
        
        # Fallback for unittest/nose2 if the primary pattern didn't find specific failures/errors.
        if not results["failed"]:
            logging.debug("--- nose2/unittest Fallback Parsing ---")
            lines = output.split('\n')
            # Check summary status line like FAILED (errors=1) or FAILED (failures=1)
            summary_failure_detected = any(re.search(r"^FAILED \((?:errors|failures)=\d+\)", line) for line in lines)
            logging.debug(f"Summary failure detected: {summary_failure_detected}")
            # Explicitly check for loader/discovery errors
            loader_error_detected = False
            potential_failed_path = None
            
            for line in lines:
                 # Check for lines starting with FAIL: or ERROR: (less specific)
                 if (line.startswith("FAIL:") or line.startswith("ERROR:")) and not potential_failed_path:
                     # Try to extract a potential test name or file path
                     match = re.search(r"(?:FAIL|ERROR):\s*(\S.*?)(?:\s+\(|\n|$)", line)
                     if match:
                         potential_failure_id = match.group(1).strip()
                         if potential_failure_id and not potential_failure_id.startswith("Traceback"):
                              potential_failed_path = potential_failure_id # Store potential path/name
                              logging.debug(f"Found potential failure from FAIL/ERROR line: {potential_failed_path}")
                 
                 # Check for specific Import/Module errors
                 if "ImportError: Start directory is not importable:" in line:
                     loader_error_detected = True
                     match = re.search(r"ImportError: Start directory is not importable: '(.+?)'", line)
                     if match:
                         potential_failed_path = match.group(1) # Extract path from error
                         logging.debug(f"Found potential failure from ImportError: {potential_failed_path}")
                     break # Found the critical error
                 elif "ModuleNotFoundError: No module named" in line and "nose2.loader.LoadTestsFailure" in output:
                     loader_error_detected = True
                     # Try to extract the path mentioned in the nose2 error context
                     # Using a more explicit regex pattern to avoid escaping/termination issues
                     match = re.search(r'ERROR: (.*?)(?: \([^)]*\)|$)', output)
                     if match:
                         potential_failed_path = match.group(1) # Extract path before the loader failure part
                         logging.debug(f"Found potential failure from ModuleNotFoundError: {potential_failed_path}")
                     break # Found the critical error
            
            logging.debug(f"Loader error detected: {loader_error_detected}")
            logging.debug(f"Potential failed path found: {potential_failed_path}")
            # If a loader error was detected or summary indicated failure, and we potentially have a path
            if (loader_error_detected or summary_failure_detected) and potential_failed_path:
                # Clean up potential quotes from path
                cleaned_path = potential_failed_path.strip("\'\"")
                logging.debug(f"Adding cleaned path to failed list: {cleaned_path}")
                if cleaned_path not in results["failed"]:
                    results["failed"].append(cleaned_path)
            # If still no failures found, but summary indicated failure, add a placeholder
            elif not results["failed"] and summary_failure_detected:
                 logging.debug("Adding placeholder failure due to summary line.")
                 results["failed"].append("Unknown test (failure detected in summary)")

    else: # Default to pytest style parsing
        # Regex to capture pytest test result lines
        pattern = re.compile(r"^([^\s]+\.py(?:[:]{2}[^\s]+)?)\s(PASSED|FAILED|SKIPPED|ERROR|XFAIL|XPASS)\s*(?:\[\s*\d+%\s*\])?$", re.MULTILINE)

        for match in pattern.finditer(output):
            test_name = match.group(1)
            status = match.group(2)

            if status == 'PASSED' or status == 'XPASS': # Treat XPASS as pass
                if test_name not in results["passed"]:
                    results["passed"].append(test_name)
            elif status == 'FAILED' or status == 'ERROR': # Group ERROR with FAILED
                 if test_name not in results["failed"]:
                    results["failed"].append(test_name)
            elif status == 'SKIPPED' or status == 'XFAIL': # Group XFAIL with SKIPPED
                if test_name not in results["skipped"]:
                    results["skipped"].append(test_name)

        # Fallback: Also check the final summary line for resilience
        for line in output.split('\n'):
            if 'FAILED' in line and '.py::' in line:
                test_name_match = re.search(r'([^\s]+\.py::[^\s]+)', line)
                if test_name_match:
                    test_name = test_name_match.group(1)
                    if test_name not in results["failed"]:
                         results["failed"].append(test_name)
            elif 'PASSED' in line and '.py::' in line:
                test_name_match = re.search(r'([^\s]+\.py::[^\s]+)', line)
                if test_name_match:
                    test_name = test_name_match.group(1)
                    if test_name not in results["passed"]:
                        results["passed"].append(test_name)

    return results


def extract_test_summary(output: str, runner: Optional[TestRunner] = None) -> str:
    """Extract the test summary from the output, prioritizing the final summary line."""
    
    # Specific patterns for unittest/nose2
    if runner in [TestRunner.UNITTEST, TestRunner.NOSE2]:
        # Look for the "Ran X tests..." line and the outcome (OK, FAILED)
        summary_match = re.search(r"^(Ran \d+ tests? in .*?s)\s*^([A-Z]+(?:\s*\(.*\))?)?", output, re.MULTILINE | re.DOTALL)
        if summary_match:
            main_summary = summary_match.group(1)
            outcome = summary_match.group(2) or ""
            return f"{main_summary}\n{outcome}".strip()
        lines = output.strip().split("\n")
        for i, line in enumerate(reversed(lines)):
            if line.startswith("Ran "):
                 return "\n".join(lines[len(lines)-1-i:])
        return "\n".join(lines[-5:])

    # Default/Pytest patterns
    # Priority 1: Look for the final summary line
    # Simplified pattern, focuses on structure: === ... (passed/failed/etc) ... in ...s ===
    final_summary_pattern = r'(^={10,}.*(?:passed|failed|skipped|error|warnings|selected).*in\s+[\d\.]+s.*={10,}$)'
    match = re.search(final_summary_pattern, output, re.MULTILINE | re.IGNORECASE)
    if match:
        return match.group(1).strip() # Return the matched line

    # Priority 2: Look for short summary lines (often near the end)
    # Corrected the lookahead group to handle potential final === line
    short_summary_pattern = r"^=+\s+short test summary info\s+=+$\n(.*?)(?=\n^=+\s*(?:\d+ passed|\d+ failed|\d+ skipped|error|warnings|selected)|\Z)" 
    match = re.search(short_summary_pattern, output, re.DOTALL | re.MULTILINE | re.IGNORECASE)
    if match:
        summary_content = match.group(1).strip()
        summary_lines = summary_content.split('\n')
        # Filter out empty lines that might result from splitting
        non_empty_lines = [line for line in summary_lines if line.strip()]
        # Return the first few non-empty lines of this block
        return "\n".join(non_empty_lines[:5]) 

    # Fallback: If no specific summary line/block is found, return the last few lines.
    # Avoid returning the full FAILURES/ERRORS block explicitly.
    lines = output.strip().split("\n")
    # Look for the start of the last block of === lines, but avoid the main FAILURES/ERRORS section
    # Find the last line that starts with ====
    last_separator_index = -1
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].startswith("===="):
            # Ensure it's not the start of the main FAILURES/ERRORS block
            if not re.match(r"^===+\s+(FAILURES|ERRORS)\s+===+$", lines[i], re.IGNORECASE):
                last_separator_index = i
                break 
                
    if last_separator_index != -1:
        # Return lines from the last relevant separator onwards
        return "\n".join(lines[last_separator_index:])
    elif len(lines) > 5:
        # Generic fallback to last 5 lines if no suitable separator found
        return "\n".join(lines[-5:])
    else:
        # If very short output, return it all
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


# Generator for streaming subprocess output
async def stream_subprocess_output(process: asyncio.subprocess.Process):
    """Yield stdout and stderr lines from a subprocess as they arrive."""
    queue = asyncio.Queue()
    finished_readers = 0

    # Yield an initial status line immediately
    yield "--- Starting test run ---"

    async def read_stream(stream, prefix):
        """Reads lines from a stream and puts them into the queue."""
        nonlocal finished_readers
        try:
            if stream is None:
                return
            while True:
                line = await stream.readline()
                if not line:
                    break
                await queue.put(f"{prefix}: {line.decode('utf-8', errors='replace')}")
        except Exception as e:
            logger.error(f"Error reading stream {prefix}: {e}")
            await queue.put(f"ERROR_READING_STREAM: {prefix}: {e}") # Signal error
        finally:
            finished_readers += 1
            if finished_readers == 2:
                await queue.put(None) # Signal end of both streams

    # Create tasks for the reader coroutines
    stdout_task = asyncio.create_task(read_stream(process.stdout, "STDOUT"))
    stderr_task = asyncio.create_task(read_stream(process.stderr, "STDERR"))

    # Yield lines from the queue until the sentinel (None) is received
    while True:
        line = await queue.get()
        if line is None:
            break
        yield line
        queue.task_done() # Mark task as done for queue management

    # Ensure tasks are finished (optional, but good practice)
    await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)


async def run_tests_local(config: TestExecutionConfig, db: DatabaseManager) -> Union[TestResult, AsyncGenerator[str, None]]:
    """Run tests locally using the specified configuration.
    
    Returns either a TestResult object or an AsyncGenerator for streaming responses.
    """
    start_time = time.time()
    result_id = str(uuid.uuid4())
    
    cmd = []
    if config.runner == TestRunner.UV:
        # Assuming 'uv run pytest ...' for consistency, adjust if uv handles test discovery differently
        cmd = ["uv", "run", "pytest"] 
    elif config.runner == TestRunner.PYTEST:
        cmd = ["python", "-m", "pytest"]
    elif config.runner == TestRunner.UNITTEST:
        # For unittest, use discover, targeting the specific file if provided
        if config.test_path:
            # Run discover from project root, targeting the relative path
            cmd = ["python", "-m", "unittest", "discover", "-s", ".", "-p", config.test_path]
        else:
            # Default discover from project root if no path provided
            cmd = ["python", "-m", "unittest", "discover", "-s", "."]
    elif config.runner == TestRunner.NOSE2:
        cmd = ["python", "-m", "nose2"]
    else:
        raise ValueError(f"Unsupported test runner: {config.runner}")
    
    # Add test path if specified and exists, otherwise run all tests in project path implicitly
    test_path_abs = None
    if config.test_path:
        test_path_abs = os.path.join(config.project_path, config.test_path)
        if os.path.exists(test_path_abs):
            cmd.append(test_path_abs)
        else:
            logger.warning(f"Specified test_path '{config.test_path}' not found relative to project_path. Running tests without explicit path.")
    
    # Add max failures if specified
    if config.max_failures is not None:
        cmd.extend(["-x" if config.max_failures == 1 else f"--maxfail={config.max_failures}"])
    
    # Handle last failed tests (pass as specific arguments if available)
    last_failed_tests_list = []
    if config.run_last_failed:
        last_failed_tests_list = await db.get_last_failed_tests(config.project_path)
        if last_failed_tests_list:
            # Pytest specific: `--lf` flag is often better than passing individual paths
            if config.runner == TestRunner.PYTEST or config.runner == TestRunner.UV:
                 cmd.append("--lf") # Add last-failed flag
            else:
                 # For other runners, append the test identifiers if possible
                 # Note: This might need runner-specific formatting
                 cmd.extend(last_failed_tests_list) 
    
    # Add verbose output
    cmd.append("-v")
    
    # Add any additional arguments
    cmd.extend(config.additional_args)
    
    logger.info(f"Running command: {' '.join(cmd)}")
    
    # Check if we're in streaming mode
    streaming_mode = "stream" in config.additional_args
    
    process = None
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=config.project_path
        )

        # If streaming mode is enabled, return a streaming generator
        if streaming_mode:
            logger.info("Local test execution in streaming mode")
            
            # Create generator function to stream output
            async def generate_output():
                output_buffer = []
                
                # Stream process output
                async for line in stream_subprocess_output(process):
                    output_buffer.append(line)
                    yield line
                
                # Process is complete, get return code
                return_code = process.returncode
                yield f"Process completed with return code: {return_code}"
                
                # Process the complete output
                try:
                    # Join the output buffer to get the full output
                    full_output = "".join(output_buffer)
                    
                    # Process the output to extract results
                    cleaned_output = clean_test_output(full_output, config.max_tokens)
                    results = extract_test_results(cleaned_output, config.runner)
                    summary = extract_test_summary(cleaned_output, config.runner)
                    
                    # Determine status
                    yield "-- DEBUG: Determining status..."
                    if return_code != 0:
                        status = "failed"
                    elif results["failed"]:
                        status = "failed"
                    elif not results["passed"] and not results["failed"]:
                        status = "error"
                    else:
                        status = "success"
                    yield f"-- DEBUG: Status determined: {status}"
                    
                    # Create and store result
                    yield "-- DEBUG: Creating TestResult object..."
                    result = TestResult(
                        id=result_id,
                        project_path=config.project_path,
                        test_path=config.test_path,
                        runner=config.runner.value,
                        execution_mode=config.mode.value,
                        status=status,
                        summary=summary,
                        details=full_output, # Store the raw buffer output
                        passed_tests=results["passed"],
                        failed_tests=results["failed"],
                        skipped_tests=results["skipped"],
                        execution_time=time.time() - start_time
                    )
                    yield "-- DEBUG: TestResult object created."
                    
                    # Store result in database
                    yield "-- DEBUG: Calling db.store_test_result..."
                    await db.store_test_result(
                        result_id=result.id,
                        status=result.status,
                        summary=result.summary,
                        details=result.details,
                        passed_tests=result.passed_tests,
                        failed_tests=result.failed_tests,
                        skipped_tests=result.skipped_tests,
                        execution_time=result.execution_time,
                        config=config.model_dump()
                    )
                    yield "-- DEBUG: db.store_test_result awaited."
                    
                    # yield result # Removed: Do not yield the TestResult object in the stream
                    # Yield a sentinel string indicating completion instead?
                    # Or just let the stream end. The caller will fetch result from DB.
                    yield f"RESULT_STORED:{result_id}" # Yielding ID as sentinel
                    yield "-- DEBUG: RESULT_STORED yielded."
                except Exception as e:
                    # Log the exception for debugging
                    logger.error(f"Exception during stream result processing: {e}", exc_info=True)
                    yield f"ERROR: Failed to process test results: {str(e)}"
            
            return generate_output()
            
        # Non-streaming mode (original code) - collect all output
        output_lines = []

        # --- Replaced communicate() with explicit stream reading --- 
        async def read_stream(stream, stream_name):
            while True:
                line = await stream.readline()
                if not line:
                    break
                output_lines.append(line.decode('utf-8', errors='replace'))
                logger.debug(f"{stream_name}: {line.decode('utf-8', errors='replace').strip()}")

        # Start reading stdout and stderr concurrently
        try:
            await asyncio.wait_for(
                asyncio.gather(
                    read_stream(process.stdout, "STDOUT"),
                    read_stream(process.stderr, "STDERR")
                ),
                timeout=config.timeout
            )
        except asyncio.TimeoutError:
            process.terminate() # Terminate the process on timeout
            logger.warning(f"Local test execution timed out after {config.timeout} seconds.")
            end_time = time.time()
            # Handle timeout result
            result = TestResult(
                id=result_id,
                project_path=config.project_path,
                test_path=config.test_path,
                runner=config.runner.value,
                execution_mode=config.mode.value,
                status="timeout",
                summary=f"Tests timed out after {config.timeout} seconds",
                details=f"Command: {' '.join(cmd)}\nTests timed out after {config.timeout} seconds.\nPartial Output:\n{'' .join(output_lines)}",
                execution_time=end_time - start_time,
                passed_tests=[],
                failed_tests=last_failed_tests_list if config.run_last_failed else [],
                skipped_tests=[]
            )
            # Store timeout result
            await db.store_test_result(
                result_id=result.id, status=result.status, summary=result.summary, details=result.details,
                passed_tests=result.passed_tests, failed_tests=result.failed_tests, skipped_tests=result.skipped_tests,
                execution_time=result.execution_time, config=config.model_dump()
            )
            return result
            
        # Wait for the process to finish and get the return code AFTER reading streams
        return_code = await process.wait()
        logger.info(f"Process finished with return code: {return_code}")
        # --- End of replaced block --- 
            
        output = "".join(output_lines)
        logger.info(f"Raw output length: {len(output)}")
        logger.debug(f"Raw output head:\n{output[:500]}") # Log start of output
        logger.debug(f"Full raw output for {config.runner}:\n{output}") 

        cleaned_output = clean_test_output(output, config.max_tokens)
        logger.info(f"Cleaned output length: {len(cleaned_output)}")
        
        end_time = time.time()
        
        # Extract test results
        logger.info("Extracting test results...")
        results = extract_test_results(cleaned_output, config.runner)
        logger.info(f"Extracted results: {results}")

        # Get summary
        logger.info("Extracting test summary...")
        summary = extract_test_summary(cleaned_output, config.runner)
        logger.info(f"Extracted summary: {summary[:200]}...") # Log start of summary

        # Truncate to token limit
        logger.info("Truncating details...")
        details = truncate_to_token_limit(cleaned_output, config.max_tokens)
        logger.info("Truncating complete.")
        
        # Determine test status (Revised Logic using return_code)
        logger.info("Determining final status...")
        if return_code is None: # Should not happen if timeout didn't occur, but belt-and-suspenders
             status = "error"
             summary = "Unknown test outcome: Process did not exit cleanly."
             logger.error("Process return code was None after stream reading completed.")
        elif return_code != 0:
            # Non-zero exit code always means failure
            status = "failed"
            logger.info(f"Status set to 'failed' (returncode={return_code})")
        elif results["failed"]:
            # Zero exit code, but parser found failures
            status = "failed"
            logger.info(f"Status set to 'failed' (returncode=0, failures_found=True)")
        elif not results["passed"] and not results["failed"] and return_code == 0:
            # Zero exit code, no failures, but also no passes -> Error (e.g., no tests collected)
            status = "error"
            summary = "No tests found or executed." + (" " + summary if summary else "")
            logger.info(f"Status set to 'error' (no tests found/run, returncode=0)")
        elif return_code == 0 and not results["failed"]:
            # Zero exit code, no failures found (passes or skips)
            status = "success"
            logger.info(f"Status determined as 'success'")
        else:
            # Fallback case, treat as error
            status = "error"
            summary = f"Unknown test outcome (returncode={return_code}, failures={len(results['failed'])})"
            logger.warning(f"Status set to 'error' (fallback case)")

        # Create result object
        logger.info("Creating TestResult object...")
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
            failed_tests=results["failed"],
            skipped_tests=results["skipped"],
            execution_time=end_time - start_time
        )

        # Store the result in the database
        await db.store_test_result(
            result_id=result.id,
            status=result.status,
            summary=result.summary,
            details=result.details,
            passed_tests=result.passed_tests,
            failed_tests=result.failed_tests,
            skipped_tests=result.skipped_tests,
            execution_time=result.execution_time,
            config=config.model_dump()
        )
        
        return result
    
    except FileNotFoundError as e:
        end_time = time.time()
        logger.error(f"Command not found error during local test execution: {e}", exc_info=True)
        status = "error"
        summary = f"Command execution failed: {e.strerror}"
        details = f"Command: {' '.join(cmd)}\nError: Command not found ({e.filename}). Ensure the runner ({config.runner.value}) and Python/uv are correctly installed and in PATH."
        # Return a specific TestResult, but the endpoint should raise HTTP 500 for this kind of server error
        result = TestResult(
            id=result_id, project_path=config.project_path, test_path=config.test_path,
            runner=config.runner.value, execution_mode=config.mode.value, status=status,
            summary=summary, details=details, execution_time=end_time - start_time
        )
        # Store error result
        await db.store_test_result(
             result_id=result.id, status=status, summary=summary, details=details,
             passed_tests=[], failed_tests=[], skipped_tests=[],
             execution_time=result.execution_time, config=config.model_dump()
        )
        # Raise HTTP 500 - Indicates a server setup issue
        raise HTTPException(status_code=500, detail=f"Server Execution Error: {details}")
        
    except ValueError as e: # Catch specific ValueError for unsupported runner
        end_time = time.time()
        logger.error(f"Configuration error during local test execution: {e}", exc_info=True)
        status = "error"
        summary = f"Configuration error: {str(e)}"
        details = f"Error: {str(e)}\nTraceback: {traceback.format_exc()}"
        # Raise HTTP 400 or 422 for configuration errors
        raise HTTPException(status_code=400, detail=f"Configuration Error: {str(e)}")

    except OSError as e:
        end_time = time.time()
        logger.error(f"OS error during local test execution: {type(e).__name__}: {e}", exc_info=True)
        status = "error"
        summary = f"OS error during command execution: {e.strerror} - {e.filename if e.filename else 'command'}"
        # Try to get command if available
        cmd_str = "Unknown command" 
        try: cmd_str = ' '.join(cmd) 
        except NameError: pass # cmd might not be defined if error was early
        details = f"Command: {cmd_str}\nOS Error: {e.strerror} ({e.filename if e.filename else 'command'}). Ensure the command and environment are correctly set up."
        
        # Ensure result_id is defined, generate if necessary
        try: current_result_id = result_id
        except NameError: current_result_id = str(uuid.uuid4())
        
        result = TestResult(
            id=current_result_id, project_path=config.project_path, test_path=config.test_path,
            runner=config.runner.value, execution_mode=config.mode.value, status=status,
            summary=summary, details=details, execution_time=end_time - start_time,
            passed_tests=[], failed_tests=[], skipped_tests=[] # No reliable results on error
        )
        try:
            await db.store_test_result(
                 result_id=result.id, status=status, summary=summary, details=details,
                 passed_tests=result.passed_tests, failed_tests=result.failed_tests, skipped_tests=result.skipped_tests,
                 execution_time=result.execution_time, config=config.model_dump()
            )
            logger.info(f"Stored OSError TestResult {result.id} to DB.")
        except Exception as db_err:
             logger.error(f"Failed to store OSError TestResult {result.id} to DB: {db_err}", exc_info=True)
             
        # Raise HTTP 500 - Indicates a server setup issue
        raise HTTPException(status_code=500, detail=f"Server Execution Error: {details}")

    except Exception as e:
        # --- Modified Generic Exception Handling ---
        end_time = time.time()
        logger.error(f"Generic error during local test execution: {type(e).__name__}: {e}", exc_info=True) # Log type and message
        status="error"
        summary=f"Error processing test results: {type(e).__name__}: {str(e)}" # Clarify summary
        # Try to get command if available
        cmd_str = "Unknown command" 
        try: cmd_str = ' '.join(cmd) 
        except NameError: pass # cmd might not be defined if error was early
        # Include exception type in details
        details=f"Command: {cmd_str}\nError Type: {type(e).__name__}\nError: {str(e)}\nTraceback: {traceback.format_exc()}"
        
        logger.info("Creating error TestResult object...")
        # Ensure result_id is defined, generate if necessary
        try: current_result_id = result_id
        except NameError: current_result_id = str(uuid.uuid4())
        
        result = TestResult(
            id=current_result_id,
            project_path=config.project_path, 
            test_path=config.test_path,
            runner=config.runner.value, 
            execution_mode=config.mode.value, 
            status=status,
            summary=summary, 
            details=details, 
            execution_time=end_time - start_time,
            passed_tests=[], failed_tests=[], skipped_tests=[] # No reliable results on error
        )
        try:
            await db.store_test_result(
                 result_id=result.id, status=result.status, summary=result.summary, details=result.details,
                 passed_tests=result.passed_tests, failed_tests=result.failed_tests, skipped_tests=result.skipped_tests,
                 execution_time=result.execution_time, config=config.model_dump()
            )
            logger.info(f"Stored error TestResult {result.id} to DB.")
        except Exception as db_err:
             logger.error(f"Failed to store error TestResult {result.id} to DB: {db_err}", exc_info=True)

        # Return the error result as JSON, DO NOT raise 500 anymore
        logger.warning(f"Returning error TestResult {result.id} due to internal processing error.")
        return result 
    finally:
        # Ensure process is cleaned up if it exists and hasn't finished
        if process and process.returncode is None:
            logger.warning(f"Terminating hanging process {process.pid} in run_tests_local")
            try:
                logger.info(f"[run_tests_local finally] Attempting to terminate process {process.pid}...")
                process.terminate()
                logger.info(f"[run_tests_local finally] Waiting for process {process.pid} termination...")
                await asyncio.wait_for(process.wait(), timeout=2) # Short wait after terminate
                logger.info(f"[run_tests_local finally] Process {process.pid} terminated successfully.")
            except asyncio.TimeoutError:
                logger.error(f"[run_tests_local finally] Timeout waiting for process {process.pid} termination. Killing...")
                try: 
                    process.kill()
                    logger.info(f"[run_tests_local finally] Process {process.pid} killed.")
                except ProcessLookupError:
                    logger.warning(f"[run_tests_local finally] Process {process.pid} already exited before kill.")
                except Exception as kill_err:
                     logger.error(f"[run_tests_local finally] Error killing process {process.pid}: {kill_err}")                    
            except Exception as term_err:
                logger.error(f"[run_tests_local finally] Error terminating process {process.pid}: {term_err}")
                try: 
                    logger.info(f"[run_tests_local finally] Attempting to kill process {process.pid} after termination error...")
                    process.kill()
                    logger.info(f"[run_tests_local finally] Process {process.pid} killed after termination error.")
                except ProcessLookupError:
                    logger.warning(f"[run_tests_local finally] Process {process.pid} already exited before kill (after term error).")
                except Exception as kill_err_alt:
                     logger.error(f"[run_tests_local finally] Error killing process {process.pid} after termination error: {kill_err_alt}")
        else:
            logger.info(f"[run_tests_local finally] Process cleanup not needed (process={process}, returncode={process.returncode if process else 'N/A'}).")


async def run_tests_docker(config: TestExecutionConfig, db: DatabaseManager) -> Union[TestResult, AsyncGenerator[str, None]]:
    """Run tests in Docker container, streaming output or returning the final result object."""
    start_time = time.time()
    result_id = str(uuid.uuid4())
    container = None
    client = None
    last_failed_tests_list = []
    cmd_str = ""
    output = ""
    status = None  # No default status, we'll determine it based on test results
    summary = ""
    details = ""
    passed_tests = []
    failed_tests = []
    skipped_tests = []
    exit_code = -1
    end_time = start_time

    try:
        import docker
        from docker.errors import DockerException, ImageNotFound, APIError
        import requests # Needed for wait timeout exception

        client = docker.from_env()

        # --- Prepare Command (Combine logic from previous attempts) ---
        test_cmd_list = []
        runner_name = config.runner.value
        if runner_name == "pytest":
            test_cmd_list = ["python", "-m", "pytest"]
        elif runner_name == "unittest":
            if config.test_path and os.path.isfile(os.path.join(config.project_path, config.test_path)) and config.test_path.endswith('.py'):
                # Convert file path to module path relative to /app
                module_path = config.test_path[:-3].replace(os.path.sep, '.')
                test_cmd_list = ["python", "-m", "unittest", module_path]
            elif config.test_path and os.path.isdir(os.path.join(config.project_path, config.test_path)):
                test_cmd_list = ["python", "-m", "unittest", "discover", "-s", os.path.join("/app", config.test_path)] # Discover in relative path
            else:
                 test_cmd_list = ["python", "-m", "unittest", "discover", "-s", "/app"] # Discover in /app
        elif runner_name == "nose2":
            test_cmd_list = ["python", "-m", "nose2"]
        else:
            raise ValueError(f"Unsupported test runner for Docker execution: {runner_name}")

        # Add specific test target unless unittest handled discovery
        if runner_name != "unittest" and config.test_path:
             test_path_in_container = os.path.join("/app", config.test_path)
             # Check if path exists locally before adding - docker will fail anyway but provides earlier feedback
             if os.path.exists(os.path.join(config.project_path, config.test_path)):
                 test_cmd_list.append(test_path_in_container)
             else:
                 logger.warning(f"Test path {config.test_path} not found locally, may fail in Docker.")
                 # Decide whether to proceed or raise error? Proceed for now.
                 test_cmd_list.append(test_path_in_container)

        if config.max_failures is not None:
            test_cmd_list.extend(["-x" if config.max_failures == 1 else f"--maxfail={config.max_failures}"])
        if config.run_last_failed:
             last_failed_tests_list = await db.get_last_failed_tests(config.project_path) # Fetch from DB
             if last_failed_tests_list:
                  if runner_name == "pytest":
                       test_cmd_list.append("--lf")
                  else:
                      # Append relative paths for other runners if needed
                      for test in last_failed_tests_list:
                          # Assume stored paths are relative to project root
                          test_path_in_container = os.path.join("/app", test) 
                          test_cmd_list.append(test_path_in_container)
                          
        test_cmd_list.append("-v") # Add verbosity
        test_cmd_list.extend(config.additional_args)
        test_cmd_str = " ".join(test_cmd_list)

        # Combine installation and execution
        install_cmd = "python -m pip install --upgrade pip > /dev/null && python -m pip install pytest nose2 > /dev/null"
        full_container_cmd = f"/bin/sh -c \"{install_cmd} && {test_cmd_str}\""
        cmd_str = full_container_cmd
        # --- End Prepare Command ---

        docker_image = config.docker_image or "python:3.11"
        logger.info(f"Starting Docker container {docker_image} with command: {full_container_cmd}")
        container = client.containers.run(
            docker_image,
            command=full_container_cmd,
            volumes={config.project_path: {'bind': '/app', 'mode': 'rw'}},
            working_dir="/app",
            detach=True,
            stdout=True, stderr=True
        )
        logger.info(f"Container {container.short_id} started.")

        # Use Docker logs stream=True for streaming output
        stream = container.logs(stdout=True, stderr=True, stream=True, follow=True)
        
        # For streaming mode, return a generator
        async def generate_stream():
            buffer = []
            timeout_task = None
            final_status = 'pending' # Initial status
            stream_error = None
            exit_code = -1 # Initialize exit_code
            
            try:
                # Start timeout monitor
                timeout_task = asyncio.create_task(asyncio.sleep(config.timeout))

                # Define a function to iterate over the sync stream in a thread
                def sync_iterate_stream():
                    results = []
                    for line_bytes in stream: # Iterate synchronously
                        results.append(line_bytes)
                    return results

                # Process Docker logs stream using asyncio.to_thread
                try:
                    # Run the synchronous iteration in a thread
                    log_lines = await asyncio.to_thread(sync_iterate_stream)

                    # Process the collected lines asynchronously
                    for line_bytes in log_lines:
                        if timeout_task.done():
                            final_status = 'timeout'
                            yield "ERROR: Docker execution timed out"
                            logger.warning(f"Docker execution for {result_id} timed out after {config.timeout} seconds.")
                            break # Stop processing stream on timeout

                        line_str = line_bytes.decode('utf-8', errors='replace')
                        buffer.append(line_str)
                        yield f"DOCKER: {line_str}"
                        await asyncio.sleep(0) # Yield control briefly

                except Exception as e:
                    stream_error = e
                    final_status = 'error'
                    logger.error(f"Error reading Docker stream for {result_id}: {e}", exc_info=True)
                    yield f"ERROR: Docker stream error: {str(e)}"
                
                # Cancel timeout task if it hasn't finished and we exited the loop normally
                if not timeout_task.done():
                    timeout_task.cancel()
                    try:
                        await timeout_task
                    except asyncio.CancelledError:
                        pass # Expected
                elif final_status != 'timeout': # Timeout already handled
                    # If timeout occurred, status is already set
                    pass

                # Wait for container to finish if no timeout/stream error occurred yet
                if final_status == 'pending':
                    try:
                        logger.debug(f"Waiting for container {container.short_id} to finish...")
                        container_result = await asyncio.to_thread(container.wait, timeout=10) # Use asyncio.to_thread for blocking call
                        exit_code = container_result.get("StatusCode", -1)
                        yield f"DOCKER: Container exited with code {exit_code}"
                        logger.info(f"Container {container.short_id} exited with code {exit_code}.")
                        # Determine status based on exit code *only if* no prior error/timeout
                        final_status = "success" if exit_code == 0 else "failed"
                    except asyncio.TimeoutError:
                         final_status = 'timeout'
                         logger.warning(f"Timeout waiting for container {container.short_id} to exit.")
                         yield "ERROR: Timeout waiting for container exit."
                    except (APIError, DockerException) as wait_err:
                        final_status = 'error'
                        logger.error(f"Error waiting for container {container.short_id}: {wait_err}", exc_info=True)
                        yield f"DOCKER: Error waiting for container: {wait_err}"

            except asyncio.CancelledError:
                final_status = 'error'
                logger.warning(f"Docker stream task for {result_id} cancelled.")
                yield "ERROR: Stream processing cancelled"
            finally:
                # Ensure container cleanup happens regardless of errors
                try:
                    logger.debug(f"Attempting to remove container {container.short_id}...")
                    logger.info(f"[run_tests_docker finally] Calling container.remove for {container.short_id}...")
                    await asyncio.to_thread(container.remove, force=True)
                    logger.info(f"[run_tests_docker finally] container.remove for {container.short_id} completed.")
                    yield "DOCKER: Container cleaned up"
                    logger.info(f"Container {container.short_id} removed.")
                except (APIError, DockerException) as cleanup_err:
                    # Log error but don't yield it, as it might obscure the actual test result/error
                    logger.error(f"[run_tests_docker finally] Error cleaning up container {container.short_id}: {cleanup_err}", exc_info=False)
                    # yield f"DOCKER: Error cleaning up container: {cleanup_err}" # Avoid yielding this
                except Exception as general_cleanup_err:
                     logger.error(f"[run_tests_docker finally] Unexpected error during container cleanup {container.short_id}: {general_cleanup_err}", exc_info=True)

                # --- Final Result Processing ---
                end_time = time.time() # Capture end time accurately here
                output = "".join(buffer)
                cleaned_output = clean_test_output(output, config.max_tokens) # Clean before parsing
                details_truncated = truncate_to_token_limit(cleaned_output, config.max_tokens) # Truncate *cleaned* output

                # Default values for results
                passed_tests_final = []
                failed_tests_final = []
                skipped_tests_final = []
                summary_final = f"Execution finished with status: {final_status}" # Default summary

                # Parse results only if execution likely completed (success or failed)
                if final_status in ['success', 'failed']:
                    try:
                        results = extract_test_results(cleaned_output, config.runner)
                        summary_extracted = extract_test_summary(cleaned_output, config.runner)

                        passed_tests_final = results.get("passed", [])
                        failed_tests_final = results.get("failed", [])
                        skipped_tests_final = results.get("skipped", [])
                        if summary_extracted:
                            summary_final = summary_extracted
                        else:
                            # Use a fallback summary if extraction fails but status is success/failed
                            summary_final = f"Tests {'passed' if final_status == 'success' else 'failed'}. Summary extraction failed."
                            logger.warning(f"Summary extraction failed for {result_id} despite status '{final_status}'. Output: {cleaned_output[:200]}...")

                    except Exception as parse_err:
                         logger.error(f"Error parsing test results for {result_id}: {parse_err}", exc_info=True)
                         summary_final = f"Error parsing test results: {parse_err}"
                         # Consider setting status to 'error' if parsing fails? For now, keep original status.
                         # final_status = 'error'


                elif final_status == 'timeout':
                     summary_final = f"Execution timed out after {config.timeout} seconds."
                elif final_status == 'error':
                     # Use the stream error or a generic message if stream_error is None
                     error_msg = str(stream_error) if stream_error else "An unspecified error occurred during execution."
                     summary_final = f"Execution failed with error: {error_msg}"
                     # Ensure details contain the error if available
                     if stream_error and str(stream_error) not in details_truncated:
                         details_truncated = f"Stream Error: {str(stream_error)}\n---\n{details_truncated}"


                # Create and store the final result object
                result = TestResult(
                    id=result_id,
                    project_path=config.project_path,
                    test_path=config.test_path,
                    runner=config.runner.value,
                    execution_mode=config.mode.value,
                    status=final_status, # Use the determined final status
                    summary=summary_final,
                    details=details_truncated,
                    passed_tests=passed_tests_final,
                    failed_tests=failed_tests_final,
                    skipped_tests=skipped_tests_final,
                    execution_time=end_time - start_time
                )

                try:
                    await db.store_test_result(
                        result_id=result.id,
                        status=result.status,
                        summary=result.summary,
                        details=result.details,
                        passed_tests=result.passed_tests,
                        failed_tests=result.failed_tests,
                        skipped_tests=result.skipped_tests,
                        execution_time=result.execution_time,
                        config=config.model_dump()
                    )
                    logger.info(f"Stored final result for {result_id} with status: {result.status}")
                except Exception as db_err:
                    logger.error(f"Failed to store final Docker result {result_id} to DB: {db_err}", exc_info=True)

                # Yield the final TestResult object LAST
                yield result

        # Return the async generator
        return generate_stream()

    except (ValueError, ImageNotFound, APIError, DockerException) as e:
        logger.error(f"Docker test setup error: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=400 if isinstance(e, (ValueError, ImageNotFound)) else 500,
            detail=f"Docker Error: {str(e)}"
        )
    except Exception as e:
        # Create error result for non-streaming mode
        logger.error(f"Unexpected error in Docker test setup: {type(e).__name__}: {e}", exc_info=True)
        result = TestResult(
            id=result_id,
            project_path=config.project_path,
            test_path=config.test_path,
            runner=config.runner.value,
            execution_mode=config.mode.value,
            status="error",
            summary=f"Docker setup error: {type(e).__name__}: {str(e)}",
            details=f"Error: {str(e)}\n{traceback.format_exc()}",
            execution_time=time.time() - start_time
        )
        
        try:
            await db.store_test_result(
                result_id=result.id,
                status=result.status, 
                summary=result.summary,
                details=result.details,
                passed_tests=[],
                failed_tests=[],
                skipped_tests=[],
                execution_time=result.execution_time,
                config=config.model_dump()
            )
        except Exception as db_err:
            logger.error(f"Failed to store Docker error result: {db_err}")
            
        return result


@app.get("/")
async def root(api_key: str = Depends(verify_api_key)):
    """Root endpoint"""
    return {"status": "active", "service": "MCP Test Server"}


@app.post("/run-tests")
async def run_tests_endpoint(config: TestExecutionConfig, db: DatabaseManager = Depends(get_request_db_manager), api_key: str = Depends(verify_api_key)):
    """Run tests with the given configuration. Returns JSON result or streaming text response."""
    # Validate project path
    if not os.path.isdir(config.project_path):
        raise HTTPException(status_code=400, detail=f"Project path not found: {config.project_path}")
    
    # Check test path relative to project path
    relative_test_path = config.test_path
    absolute_test_path = os.path.join(config.project_path, relative_test_path)
    if not os.path.exists(absolute_test_path):
        # Allow running without a specific path if intent is to run all tests
        if relative_test_path: # Only raise if a specific non-existent path was given
             raise HTTPException(status_code=400, detail=f"Test path not found: {absolute_test_path}")
    
    try:
        # Determine streaming mode EXPLICITLY from request
        streaming_mode = config.additional_args and "stream" in config.additional_args
        
        if config.mode == ExecutionMode.LOCAL:
            logger.info(f"Running local test execution for project: {config.project_path} (Stream: {streaming_mode})")
            result = await run_tests_local(config, db)
            
            # Only return StreamingResponse if stream=True was requested
            if streaming_mode and inspect.isasyncgen(result):
                logger.info("Returning streaming response for local test execution")
                return StreamingResponse(result, media_type="text/plain")
            elif not streaming_mode and inspect.isasyncgen(result):
                 # If it returned a stream unexpectedly, consume it to get the final result 
                 logger.warning("run_tests_local returned a stream unexpectedly for non-streaming request. Consuming...")
                 final_result_data = None
                 async for line in result:
                     if line.startswith("RESULT:"): # Try to get final result ID from stream
                         try: 
                              result_id = line.split("-")[0].split(":")[1].strip()
                              final_result_data = await db.get_test_result(result_id)
                         except Exception as e:
                              logger.error(f"Failed to extract/fetch result ID from unexpected stream: {e}")
                         break # Stop consuming after finding result line
                 if final_result_data:
                      return final_result_data # Return the TestResult object fetched from DB
                 else:
                      # If we couldn't get the result ID or fetch it, return an error
                      # Ideally, run_tests_local shouldn't get here in non-streaming mode
                      error_id = str(uuid.uuid4())
                      error_res = TestResult(id=error_id, status="error", summary="Failed to process unexpected stream from local runner", details="", execution_time=0, project_path=config.project_path, test_path=config.test_path, runner=config.runner.value, execution_mode=config.mode.value)
                      # Attempt to store error
                      try: await db.store_test_result(result_id=error_id, status="error", summary=error_res.summary, details="", execution_time=0, config=config.model_dump())
                      except Exception as db_err: logger.error(f"Failed to store stream error result: {db_err}")
                      return error_res # Return the error result as JSON
            elif not streaming_mode and not inspect.isasyncgen(result):
                 # This is the expected path for non-streaming local runs
                 logger.info("Returning JSON response for non-streaming local test execution")
                 return result # Return the TestResult object directly
            elif streaming_mode and not inspect.isasyncgen(result):
                 # Corner case: Requested stream but got JSON (shouldn't happen with run_tests_local)
                 logger.error("run_tests_local returned JSON unexpectedly for streaming request.")
                 return result # Return JSON anyway?
            else:
                 logger.error("Unexpected state in /run-tests endpoint after run_tests_local call.")
                 raise HTTPException(status_code=500, detail="Internal server error processing local test request.")                 
            
        elif config.mode == ExecutionMode.DOCKER:
            logger.info(f"Running Docker test execution for project: {config.project_path} (Stream: {streaming_mode})")
            
            # run_tests_docker now handles streaming internally based on config
            result = await run_tests_docker(config, db)
            
            # Only return StreamingResponse if stream=True was requested AND runner returned a generator
            if streaming_mode and inspect.isasyncgen(result):
                logger.info("Returning streaming response for Docker test execution")
                return StreamingResponse(result, media_type="text/plain")
            # Return JSON if stream=False was requested AND runner returned TestResult object
            elif not streaming_mode and not inspect.isasyncgen(result):
                 logger.info("Returning JSON response for non-streaming Docker test execution")
                 return result # Return the TestResult object directly
            # Handle mismatches (log errors, return best guess)
            elif streaming_mode and not inspect.isasyncgen(result): 
                 logger.error("Requested stream for Docker but received JSON result unexpectedly.")
                 return result # Return the JSON result anyway
            elif not streaming_mode and inspect.isasyncgen(result):
                 logger.warning("Requested JSON for Docker but received stream result unexpectedly. Consuming stream...")
                 # Attempt to consume the stream and return the final TestResult object
                 final_result_object = None
                 try:
                     async for item in result:
                         # The last item yielded should be the TestResult object
                         final_result_object = item
                 except Exception as e:
                     logger.error(f"Error consuming unexpected stream: {type(e).__name__}: {e}", exc_info=True)
                     # Fallback to error result if stream consumption fails
                     error_id = str(uuid.uuid4())
                     error_res = TestResult(id=error_id, status="error", summary=f"Failed to consume unexpected stream: {type(e).__name__}", details=str(e), execution_time=0, project_path=config.project_path, test_path=config.test_path, runner=config.runner.value, execution_mode=config.mode.value)
                     try: await db.store_test_result(result_id=error_id, status="error", summary=error_res.summary, details=error_res.details, execution_time=0, config=config.model_dump())
                     except Exception as db_err: logger.error(f"Failed to store stream consumption error result: {db_err}")
                     return error_res

                 if isinstance(final_result_object, TestResult):
                     logger.info("Successfully extracted TestResult object from consumed stream.")
                     return final_result_object
                 else:
                     # Log an error if the last item wasn't a TestResult
                     logger.error(f"Unexpected final item type received from stream: {type(final_result_object)}. Expected TestResult.")
                     error_id = str(uuid.uuid4())
                     error_res = TestResult(id=error_id, status="error", summary="Unexpected final item from Docker stream", details=f"Received type {type(final_result_object)}", execution_time=0, project_path=config.project_path, test_path=config.test_path, runner=config.runner.value, execution_mode=config.mode.value)
                     try: await db.store_test_result(result_id=error_id, status="error", summary=error_res.summary, details=error_res.details, execution_time=0, config=config.model_dump())
                     except Exception as db_err: logger.error(f"Failed to store unexpected item error result: {db_err}")
                     return error_res
            else:
                 logger.error("Unknown mismatch between requested streaming mode and Docker runner result type.")
                 raise HTTPException(status_code=500, detail="Internal server error processing Docker test result type.")
            
        else:
            raise HTTPException(status_code=400, detail=f"Invalid execution mode: {config.mode}")
            
    except HTTPException as http_exc:
         raise http_exc # Re-raise explicit HTTP exceptions
         
    except Exception as e:
         # Catch-all for unexpected errors during endpoint processing/calling run functions
         logger.error(f"Unexpected error in /run-tests endpoint: {type(e).__name__}: {e}", exc_info=True)
         # Create a generic error TestResult
         # Use a different ID to avoid potential collisions if run_* function partially succeeded
         error_id = str(uuid.uuid4()) 
         error_result = TestResult(
             id=error_id,
             project_path=config.project_path,
             test_path=config.test_path,
             runner=config.runner.value,
             execution_mode=config.mode.value,
             status="error",
             summary=f"Endpoint processing error: {type(e).__name__}",
             details=f"Error: {str(e)}\n{traceback.format_exc()}",
             execution_time=0
         )
         # Attempt to store this endpoint-level error result
         try:
             await db.store_test_result(
                 result_id=error_result.id, status=error_result.status, summary=error_result.summary,
                 details=error_result.details, passed_tests=[], failed_tests=[], skipped_tests=[],
                 execution_time=error_result.execution_time, config=config.model_dump()
             )
         except Exception as db_store_err:
             logger.error(f"Failed to store endpoint error result {error_id} to DB: {db_store_err}")
         # Return the error result even if DB store failed
         return error_result


@app.get("/results/{result_id}", response_model=TestResult)
async def get_test_result(result_id: str, db: DatabaseManager = Depends(get_request_db_manager), api_key: str = Depends(verify_api_key)):
    """Get the result of a previous test run"""
    result = await db.get_test_result(result_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Test result not found: {result_id}")
    
    return result


@app.get("/results", response_model=List[str])
async def list_test_results(db: DatabaseManager = Depends(get_request_db_manager), api_key: str = Depends(verify_api_key)):
    """List all test result IDs"""
    results = await db.list_test_results()
    return [r["id"] for r in results]


@app.get("/last-failed", response_model=List[str])
async def get_last_failed_tests(project_path: str, db: DatabaseManager = Depends(get_request_db_manager), api_key: str = Depends(verify_api_key)):
    """Get the list of last failed tests"""
    failed_tests = await db.get_last_failed_tests(project_path)
    return failed_tests


# Set up application startup
@app.on_event("startup")
async def startup_event():
    """Initialize the database on startup."""
    logger.info("[STARTUP] Entering startup_event...")
    db_manager = get_db_manager()
    await db_manager.connect()
    logger.info("[STARTUP] db_manager.connect() complete.")
    await db_manager._create_tables()
    logger.info("[STARTUP] db_manager._create_tables() complete.")
    await db_manager.disconnect()
    logger.info("[STARTUP] db_manager.disconnect() complete.")
    logger.info("[STARTUP] startup_event complete.")


def main():
    """Run the server"""
    port = int(os.environ.get("MCP_TEST_PORT", "8082"))
    host = os.environ.get("MCP_TEST_HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main() 