#!/usr/bin/env python3
"""
MCP Code Server - Microservice for code analysis and formatting

This server provides endpoints for:
- Analyzing code with Ruff (Python) or appropriate tools for other languages
- Formatting code with Ruff (Python) or appropriate tools for other languages
- Storing code snippets for future reference

Dependencies:
- fastapi
- uvicorn 
- pydantic
- ruff
"""

import os
import sys
import json
import subprocess
import uuid
import time
import enum
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from contextlib import asynccontextmanager

import fastapi
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import Security and Database Components
try:
    from src.storage.database import DatabaseManager, get_request_db_manager, get_db_manager
    from src.security import verify_api_key # Import the new dependency
except ImportError as e:
    # Log the specific import error
    logger.error(f"Failed to import required modules: {e}. Ensure src directory is in PYTHONPATH.")
    # Decide how to handle missing dependencies (exit, use dummies, etc.)
    # For now, let's define dummies to allow basic server startup for inspection
    class DatabaseManager: pass
    async def get_request_db_manager(): return None
    async def verify_api_key(): pass # Dummy dependency
    # sys.exit(1)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("mcp-code-server")

# Server setup
app = FastAPI(title="MCP Code Server")

# Add CORS middleware to allow requests from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CodeLanguage(str, enum.Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    RUST = "rust"
    GO = "go"
    JAVA = "java"
    CSHARP = "csharp"
    CPP = "cpp"
    OTHER = "other"

class CodeAnalysisRequest(BaseModel):
    code: str
    language: CodeLanguage = CodeLanguage.PYTHON
    filename: Optional[str] = None

class CodeFormatRequest(BaseModel):
    code: str
    language: CodeLanguage = CodeLanguage.PYTHON
    filename: Optional[str] = None

class CodeSnippet(BaseModel):
    id: str
    code: str
    language: str
    metadata: Dict[str, Any] = {}
    created_at: float = Field(default_factory=time.time)

class CodeAnalysisResult(BaseModel):
    issues: List[Dict[str, Any]]
    formatted_code: str

class CodeFixResult(BaseModel):
    fixed_code: str
    issues_remaining: List[Dict[str, Any]]
    applied_fixes: List[str]

class StoreSnippetRequest(BaseModel):
    code: str
    language: CodeLanguage = CodeLanguage.PYTHON
    metadata: Dict[str, Any] = {}

class CodeFormatResult(BaseModel):
    formatted_code: str

async def analyze_python_code(code: str, filename: Optional[str] = None) -> CodeAnalysisResult:
    """Analyze Python code using Ruff for issues and formatting."""
    import tempfile
    import subprocess
    import shutil
    
    issues = []
    formatted_code = code # Default to original code
    temp_filename = None

    # Find ruff executable
    ruff_executable = shutil.which("ruff")
    if not ruff_executable:
        logger.error("Ruff executable not found in PATH.")
        # Return original code and an error message as an issue
        return CodeAnalysisResult(
            issues=[{"code": "MCP500", "message": "Ruff executable not found.", "location": {"row": 1, "column": 1}}],
            formatted_code=code
        )
    
    try:
        with tempfile.NamedTemporaryFile(suffix='.py', delete=False, mode='w', encoding='utf-8') as f:
            f.write(code)
            temp_filename = f.name

        # 1. Run ruff check for issues
        check_cmd = [ruff_executable, "check", "--output-format=json", "--exit-zero", temp_filename]
        logger.debug(f"Running ruff check: {' '.join(check_cmd)}")
        check_result = subprocess.run(
            check_cmd,
            capture_output=True,
            text=True,
            encoding='utf-8' # Specify encoding
        )
        
        if check_result.stdout:
            try:
                issues = json.loads(check_result.stdout)
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing ruff check output: {e}")
                logger.error(f"Ruff check stdout: {check_result.stdout}")
                issues = [{"code": "MCP501", "message": f"Error parsing ruff check output: {e}", "location": {"row": 1, "column": 1}}]
        elif check_result.stderr:
             logger.error(f"Ruff check error: {check_result.stderr}")
             issues = [{"code": "MCP502", "message": f"Ruff check failed: {check_result.stderr[:100]}...", "location": {"row": 1, "column": 1}}]

        # 2. Run ruff format separately
        # Rerun on the original code to ensure formatting is clean
        # (Checking might have modified the temp file if --fix was ever used, though not currently)
        format_cmd = [ruff_executable, "format", temp_filename]
        logger.debug(f"Running ruff format: {' '.join(format_cmd)}")
        format_result = subprocess.run(
            format_cmd,
            capture_output=True,
            text=True,
            encoding='utf-8' # Specify encoding
        )

        if format_result.returncode == 0:
            # If format succeeded, read the formatted file content
            try:
                with open(temp_filename, 'r', encoding='utf-8') as f_read:
                    formatted_code = f_read.read()
            except Exception as e:
                logger.error(f"Error reading formatted temp file: {e}")
                # Keep original code as formatted_code, but add an issue
                issues.append({"code": "MCP503", "message": f"Error reading formatted code: {e}", "location": {"row": 1, "column": 1}})
        elif format_result.returncode != 0: # Check explicitly for non-zero return code
            # Formatting failed, likely syntax error. Keep original code.
            error_message = format_result.stderr or f"Ruff format exited with code {format_result.returncode}"
            logger.warning(f"Ruff format failed: {error_message}")
            # Add the specific MCP504 issue
            issues.append({"code": "MCP504", "message": f"Ruff format failed (likely syntax error): {error_message[:200]}...", "location": {"row": 1, "column": 1}})
            # Ensure original code is returned as formatted_code
            formatted_code = code

        return CodeAnalysisResult(issues=issues, formatted_code=formatted_code)
    
    except Exception as e:
        logger.error(f"Unexpected error during Ruff execution: {e}")
        return CodeAnalysisResult(
            issues=[{"code": "MCP505", "message": f"Internal server error during analysis: {e}", "location": {"row": 1, "column": 1}}],
            formatted_code=code # Return original code on error
        )

    finally:
        # Clean up the temporary file
        if temp_filename and os.path.exists(temp_filename):
            try:
                os.unlink(temp_filename)
            except OSError as e:
                 logger.error(f"Error deleting temp file {temp_filename}: {e}")

async def fix_python_code(code: str, filename: Optional[str] = None) -> CodeFixResult:
    """Analyze and attempt to fix Python code using Ruff."""
    import tempfile
    import subprocess
    
    with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as f:
        f.write(code.encode())
        temp_filename = f.name
    
    try:
        # Run ruff to fix issues
        fix_result = subprocess.run(
            ["ruff", "check", "--fix", "--output-format=json", "--exit-zero", temp_filename],
            capture_output=True,
            text=True
        )
        
        # Read the fixed code
        fixed_code = code
        try:
            with open(temp_filename, 'r') as f:
                fixed_code = f.read()
        except Exception as e:
            logger.error(f"Error reading fixed file: {e}")
        
        # Get the remaining issues after fixing
        issues_remaining = []
        if fix_result.stdout:
            try:
                # Filter for issues that were not fixed
                all_output = json.loads(fix_result.stdout)
                issues_remaining = [issue for issue in all_output if not issue.get("fix") or not issue["fix"].get("applied")]
            except json.JSONDecodeError:
                logger.error("Error parsing ruff fix output")

        # Identify applied fixes (Ruff JSON output indicates this)
        applied_fixes = []
        if fix_result.stdout:
            try:
                all_output = json.loads(fix_result.stdout)
                applied_fixes = [f"{issue['code']}: {issue['message']}" 
                                 for issue in all_output 
                                 if issue.get("fix") and issue["fix"].get("applied")]
            except json.JSONDecodeError:
                logger.error("Error parsing ruff fix output for applied fixes")

        # Optional: Run formatter after fixing
        format_result = subprocess.run(
            ["ruff", "format", "--diff", temp_filename],
            capture_output=True,
            text=True
        )
        if not format_result.returncode:
             try:
                with open(temp_filename, 'r') as f:
                    fixed_code = f.read()
             except Exception as e:
                logger.error(f"Error reading formatted file after fix: {e}")

        return CodeFixResult(
            fixed_code=fixed_code, 
            issues_remaining=issues_remaining,
            applied_fixes=applied_fixes
        )
    finally:
        # Clean up the temporary file
        try:
            os.unlink(temp_filename)
        except:
            pass

# Error handling helper
def handle_subprocess_error(e: subprocess.CalledProcessError, action: str) -> Dict[str, Any]:
    logger.error(f"Error during {action}: {e.stderr}")
    return {"success": False, "message": f"{action.capitalize()} failed", "details": e.stderr}

@app.get("/")
async def root(api_key: str = Depends(verify_api_key)):
    """Root endpoint for health check."""
    return {"service": "MCP Code Server", "status": "active"}

@app.post("/analyze", response_model=CodeAnalysisResult)
async def analyze_code(request: CodeAnalysisRequest, db: DatabaseManager = Depends(get_request_db_manager), api_key: str = Depends(verify_api_key)):
    """Analyze code and return issues found."""
    try:
        if request.language == CodeLanguage.PYTHON:
            result = await analyze_python_code(request.code, request.filename)
            # Check for internal errors signaled by the helper
            if any(issue.get("code") == "MCP500" for issue in result.issues): # Ruff not found
                raise HTTPException(status_code=500, detail="Server configuration error: Ruff executable not found.")
            if any(issue.get("code") == "MCP501" for issue in result.issues): # Parse error
                raise HTTPException(status_code=500, detail="Internal server error parsing analysis results.")
            if any(issue.get("code") == "MCP502" for issue in result.issues): # Ruff check error
                 raise HTTPException(status_code=500, detail=f"Ruff check execution failed: {result.issues[0].get('message', 'Unknown error')}")
            if any(issue.get("code") == "MCP505" for issue in result.issues): # Unexpected error in helper
                raise HTTPException(status_code=500, detail=f"Internal server error during analysis: {result.issues[0].get('message', 'Unknown error')}")

            analysis_id = str(uuid.uuid4())
            await db.store_code_analysis(analysis_id=analysis_id, issues=result.issues, formatted_code=result.formatted_code)
            return result
        else:
            # Return empty result for non-Python, maybe raise 400 later if unsupported?
            return CodeAnalysisResult(issues=[], formatted_code=request.code)
    except HTTPException as e:
        raise e # Re-raise specific HTTP exceptions from helper checks
    except Exception as e:
        logger.error(f"Unexpected error in /analyze endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@app.post("/format", response_model=CodeFormatResult)
async def format_code(request: CodeFormatRequest, db: DatabaseManager = Depends(get_request_db_manager), api_key: str = Depends(verify_api_key)):
    """Format code and return the formatted version."""
    try:
        if request.language == CodeLanguage.PYTHON:
            # analyze_python_code also handles formatting
            analysis_result = await analyze_python_code(request.code, request.filename)

            # Check for internal errors signaled by the helper
            if any(issue.get("code") == "MCP500" for issue in analysis_result.issues): # Ruff not found
                raise HTTPException(status_code=500, detail="Server configuration error: Ruff executable not found.")
            if any(issue.get("code") == "MCP503" for issue in analysis_result.issues): # Error reading formatted file
                 raise HTTPException(status_code=500, detail="Internal server error reading formatted code.")
            if any(issue.get("code") == "MCP505" for issue in analysis_result.issues): # Unexpected error in helper
                raise HTTPException(status_code=500, detail=f"Internal server error during formatting: {analysis_result.issues[0].get('message', 'Unknown error')}")

            # Check if formatting specifically failed (MCP504)
            format_failed = any(issue.get("code") == "MCP504" for issue in analysis_result.issues)
            if format_failed:
                error_msg = "Formatting failed (likely syntax error)."
                for issue in analysis_result.issues:
                    if issue.get("code") == "MCP504":
                        error_msg = issue.get("message", error_msg)
                        break
                # Raise 400 for syntax errors preventing formatting
                raise HTTPException(status_code=400, detail=error_msg)
            
            # Store analysis result (even if only formatting)
            analysis_id = str(uuid.uuid4())
            await db.store_code_analysis(analysis_id=analysis_id, issues=analysis_result.issues, formatted_code=analysis_result.formatted_code)
            return {"formatted_code": analysis_result.formatted_code}
        else:
            return {"formatted_code": request.code}
    except HTTPException as e:
        raise e # Re-raise specific HTTP exceptions
    except Exception as e:
        logger.error(f"Unexpected error in /format endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@app.post("/fix")
async def fix_code(request: CodeAnalysisRequest, db: DatabaseManager = Depends(get_request_db_manager), api_key: str = Depends(verify_api_key)):
    """Analyze code, attempt to fix issues, and return the fixed code."""
    try:
        if request.language == CodeLanguage.PYTHON:
            result = await fix_python_code(request.code, request.filename)
            
            # Check for internal errors from helper
            if any(issue.get("code") == "MCP500" for issue in result.issues_remaining): # Ruff not found
                raise HTTPException(status_code=500, detail="Server configuration error: Ruff executable not found.")
            # Add checks for other potential error codes from fix_python_code if implemented

            fix_id = str(uuid.uuid4())
            await db.store_code_fix(
                fix_id=fix_id, original_code=request.code, language=request.language.value,
                fixed_code=result.fixed_code, issues_remaining=result.issues_remaining, applied_fixes=result.applied_fixes
            )
            return result
        else:
            return CodeFixResult(fixed_code=request.code, issues_remaining=[], applied_fixes=[])
    except HTTPException as e:
        raise e # Re-raise specific HTTP exceptions
    except Exception as e:
        logger.error(f"Unexpected error in /fix endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@app.post("/snippets", response_model=CodeSnippet)
async def store_snippet(request: StoreSnippetRequest, db: DatabaseManager = Depends(get_request_db_manager), api_key: str = Depends(verify_api_key)):
    """Store a code snippet and return its ID."""
    snippet_id = str(uuid.uuid4())
    snippet = CodeSnippet(
        id=snippet_id, code=request.code, language=request.language.value, metadata=request.metadata
    )
    try:
        await db.store_code_snippet(
            snippet_id=snippet.id, code=snippet.code, language=snippet.language, metadata=snippet.metadata
        )
        logger.info(f"Stored snippet {snippet_id}")
        return snippet
    except Exception as e: # Catch generic DB errors
        logger.error(f"Database error storing snippet {snippet_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error storing snippet: {str(e)}")

@app.get("/snippets/{snippet_id}", response_model=CodeSnippet)
async def get_snippet(snippet_id: str, db: DatabaseManager = Depends(get_request_db_manager), api_key: str = Depends(verify_api_key)):
    """Retrieve a stored code snippet by ID."""
    try:
        snippet = await db.get_code_snippet(snippet_id)
        if not snippet:
            logger.warning(f"Snippet {snippet_id} not found in DB.")
            raise HTTPException(status_code=404, detail=f"Snippet {snippet_id} not found")
        return snippet
    except HTTPException as http_exc:
        raise http_exc # Re-raise 404
    except Exception as e: # Catch generic DB errors
        logger.error(f"Database error retrieving snippet {snippet_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error retrieving snippet: {str(e)}")

@app.get("/snippets")
async def list_snippets(db: DatabaseManager = Depends(get_request_db_manager), api_key: str = Depends(verify_api_key)):
    """List all stored code snippet IDs."""
    try:
        snippets = await db.list_code_snippets()
        snippet_list = snippets if snippets is not None else []
        return {"snippet_ids": [s["id"] for s in snippet_list]}
    except Exception as e: # Catch generic DB errors
        logger.error(f"Database error listing snippets: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error listing snippets: {str(e)}")

# Set up application startup/shutdown lifecycle using lifespan context manager (preferred over on_event)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Connect to DB and ensure tables using the singleton manager
    db_manager = get_db_manager()
    try:
        await db_manager.connect()
        await db_manager._create_tables()
        logger.info("Database connected and tables ensured during startup.")
    except Exception as e:
        logger.error(f"Database initialization failed during startup: {e}", exc_info=True)
        # Depending on policy, might want to raise error here to prevent startup
        # raise RuntimeError("Database initialization failed") from e
    
    yield # Application runs here
    
    # Shutdown: Disconnect from DB using the same singleton manager
    if db_manager and db_manager.conn:
        try:
            await db_manager.disconnect()
            logger.info("Database disconnected during shutdown.")
        except Exception as e:
            logger.error(f"Error during database disconnection: {e}", exc_info=True)

# Apply the lifespan context manager to the app
app.router.lifespan_context = lifespan

if __name__ == "__main__":
    import uvicorn
    # Read port from environment variable, default to 8081 if not set
    DEFAULT_PORT = 8081
    PORT = int(os.environ.get("MCP_CODE_PORT", DEFAULT_PORT))
    logger.info(f"Starting MCP Code Server on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info") 