#!/usr/bin/env python3
"""
Minimal Code-focused MCP server for coding agents
Provides endpoints for code evaluation, linting, and analysis

Dependencies:
- fastapi==0.104.1
- uvicorn==0.23.2
- ruff==0.1.5
- pydantic==2.4.2
"""
# [dependencies]
# fastapi = "^0.104.1"
# uvicorn = "^0.23.2" 
# ruff = "^0.1.5"
# pydantic = "^2.4.2"

import os
import sys
import json
import tempfile
import subprocess
from typing import Dict, Any, List, Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

# Initialize FastAPI app
app = FastAPI(title="MCP Code Server", description="MCP server for code evaluation and analysis")

# Models
class CodeSnippet(BaseModel):
    code: str
    language: str = "python"
    filename: Optional[str] = None

class CodeAnalysisResult(BaseModel):
    issues: List[Dict[str, Any]] = []
    formatted_code: Optional[str] = None
    success: bool = True
    message: str = ""

# In-memory database for code snippets
code_db = {}

@app.get("/")
async def root():
    return {"status": "active", "service": "MCP Code Server"}

@app.post("/analyze", response_model=CodeAnalysisResult)
async def analyze_code(snippet: CodeSnippet):
    """Analyze code using Ruff for linting and formatting"""
    if snippet.language != "python":
        return CodeAnalysisResult(
            success=False, 
            message=f"Language not supported: {snippet.language}. Only Python is currently supported."
        )
    
    # Create temporary file for analysis
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as temp:
        temp.write(snippet.code.encode())
        temp_path = temp.name
    
    try:
        # Run Ruff linting
        process = subprocess.run(
            ["ruff", "check", temp_path, "--format=json"],
            capture_output=True, text=True
        )
        
        issues = []
        if process.stdout:
            issues = json.loads(process.stdout)
        
        # Run Ruff formatting
        format_process = subprocess.run(
            ["ruff", "format", temp_path, "--diff"],
            capture_output=True, text=True
        )
        
        # Get formatted code
        with open(temp_path, "r") as f:
            formatted_code = f.read()
        
        return CodeAnalysisResult(
            issues=issues, 
            formatted_code=formatted_code,
            success=True,
            message="Analysis complete"
        )
    finally:
        # Clean up temp file
        os.unlink(temp_path)

@app.post("/store/{snippet_id}")
async def store_snippet(snippet_id: str, snippet: CodeSnippet):
    """Store a code snippet for later retrieval"""
    code_db[snippet_id] = snippet.dict()
    return {"status": "success", "id": snippet_id}

@app.get("/retrieve/{snippet_id}")
async def retrieve_snippet(snippet_id: str):
    """Retrieve a stored code snippet"""
    if snippet_id not in code_db:
        raise HTTPException(status_code=404, detail=f"Snippet {snippet_id} not found")
    return code_db[snippet_id]

def main():
    port = int(os.environ.get("MCP_CODE_PORT", "8081"))
    uvicorn.run(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main() 