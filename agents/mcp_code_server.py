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
import uuid
import time
import enum
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

import fastapi
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Add src directory to path so we can import storage modules
sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.storage.database import get_db_manager, DatabaseManager

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

# Database dependency
async def get_db():
    """Dependency to get database manager."""
    db_manager = get_db_manager()
    await db_manager.connect()
    try:
        yield db_manager
    finally:
        await db_manager.disconnect()

async def analyze_python_code(code: str, filename: Optional[str] = None) -> CodeAnalysisResult:
    """Analyze Python code using Ruff."""
    import tempfile
    import subprocess
    
    with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as f:
        f.write(code.encode())
        temp_filename = f.name
    
    try:
        # Run ruff for linting
        result = subprocess.run(
            ["ruff", "check", "--output-format=json", temp_filename],
            capture_output=True,
            text=True
        )
        
        issues = []
        if result.stdout:
            try:
                issues = json.loads(result.stdout)
            except json.JSONDecodeError:
                issues = [{"message": "Error parsing ruff output", "location": {"row": 1, "column": 1}}]
        
        # Run ruff for formatting
        format_result = subprocess.run(
            ["ruff", "format", "--diff", temp_filename],
            capture_output=True,
            text=True
        )
        
        formatted_code = code
        if not format_result.returncode:
            # If successful, read the formatted file
            try:
                with open(temp_filename, 'r') as f:
                    formatted_code = f.read()
            except Exception as e:
                logger.error(f"Error reading formatted file: {e}")
        
        return CodeAnalysisResult(issues=issues, formatted_code=formatted_code)
    finally:
        # Clean up the temporary file
        try:
            os.unlink(temp_filename)
        except:
            pass

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

@app.post("/analyze")
async def analyze_code(request: CodeAnalysisRequest, db: DatabaseManager = Depends(get_db)):
    """Analyze code and return issues found."""
    if request.language == CodeLanguage.PYTHON:
        result = await analyze_python_code(request.code, request.filename)
        
        # Store the analysis result in the database
        await db.store_code_analysis(
            code=request.code,
            language=request.language.value,
            issues=result.issues,
            formatted_code=result.formatted_code
        )
        
        return result
    else:
        # For now, only Python is supported
        # In the future, we can add support for other languages
        return CodeAnalysisResult(issues=[], formatted_code=request.code)

@app.post("/format")
async def format_code(request: CodeFormatRequest, db: DatabaseManager = Depends(get_db)):
    """Format code and return the formatted version."""
    if request.language == CodeLanguage.PYTHON:
        result = await analyze_python_code(request.code, request.filename)
        
        # Store the formatting result in the database
        await db.store_code_analysis(
            code=request.code,
            language=request.language.value,
            issues=[],
            formatted_code=result.formatted_code
        )
        
        return {"formatted_code": result.formatted_code}
    else:
        # For now, only Python is supported
        return {"formatted_code": request.code}

@app.post("/fix")
async def fix_code(request: CodeAnalysisRequest, db: DatabaseManager = Depends(get_db)):
    """Analyze code, attempt to fix issues, and return the fixed code."""
    if request.language == CodeLanguage.PYTHON:
        result = await fix_python_code(request.code, request.filename)
        
        # Generate a unique ID for the fix attempt
        fix_id = str(uuid.uuid4())
        
        # Store the result in the database
        await db.store_code_fix(
            fix_id=fix_id,
            original_code=request.code,
            language=request.language.value,
            fixed_code=result.fixed_code,
            issues_remaining=result.issues_remaining,
            applied_fixes=result.applied_fixes
        )
        
        return result
    else:
        # For now, only Python is supported
        return CodeFixResult(fixed_code=request.code, issues_remaining=[], applied_fixes=[])

@app.post("/snippets", response_model=CodeSnippet)
async def store_snippet(request: StoreSnippetRequest, db: DatabaseManager = Depends(get_db)):
    """Store a code snippet and return its ID."""
    snippet_id = str(uuid.uuid4())
    snippet = CodeSnippet(
        id=snippet_id,
        code=request.code,
        language=request.language.value,
        metadata=request.metadata
    )
    
    # Store the snippet in the database
    await db.store_code_snippet(
        snippet_id=snippet.id,
        code=snippet.code,
        language=snippet.language,
        metadata=snippet.metadata
    )
    
    return snippet

@app.get("/snippets/{snippet_id}", response_model=CodeSnippet)
async def get_snippet(snippet_id: str, db: DatabaseManager = Depends(get_db)):
    """Retrieve a stored code snippet by ID."""
    snippet = await db.get_code_snippet(snippet_id)
    if not snippet:
        raise HTTPException(status_code=404, detail=f"Snippet {snippet_id} not found")
    return snippet

@app.get("/snippets")
async def list_snippets(db: DatabaseManager = Depends(get_db)):
    """List all stored code snippet IDs."""
    snippets = await db.list_code_snippets()
    return {"snippet_ids": [s["id"] for s in snippets]}

# Set up application startup
@app.on_event("startup")
async def startup_event():
    """Initialize the database on startup."""
    db_manager = get_db_manager()
    await db_manager.connect()
    await db_manager.create_tables()
    await db_manager.disconnect()
    logger.info("MCP Code Server initialized")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("MCP_CODE_SERVER_PORT", 8000))
    uvicorn.run("mcp_code_server:app", host="0.0.0.0", port=port, reload=True) 