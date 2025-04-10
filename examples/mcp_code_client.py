#!/usr/bin/env python3
"""
Example client for interacting with the MCP Code Server
Shows how to analyze and format Python code
"""

import sys
import os
import json
import requests
from typing import Dict, Any, Optional
import uuid

# Default settings
MCP_CODE_SERVER_URL = os.environ.get("MCP_CODE_SERVER_URL", "http://localhost:8081")


def analyze_code(code: str, language: str = "python") -> Dict[str, Any]:
    """
    Analyze code using the MCP Code Server
    Returns analysis results with linting issues and formatted code
    """
    url = f"{MCP_CODE_SERVER_URL}/analyze"
    
    payload = {
        "code": code,
        "language": language
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {
            "success": False,
            "message": f"Error connecting to MCP Code Server: {str(e)}",
            "issues": [],
            "formatted_code": None
        }


def store_snippet(code: str, language: str = "python", snippet_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Store a code snippet in the MCP Code Server for later retrieval
    Returns the ID of the stored snippet
    """
    if not snippet_id:
        snippet_id = str(uuid.uuid4())
    
    url = f"{MCP_CODE_SERVER_URL}/store/{snippet_id}"
    
    payload = {
        "code": code,
        "language": language
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return {"success": True, "id": snippet_id}
    except requests.RequestException as e:
        return {
            "success": False,
            "message": f"Error storing snippet: {str(e)}"
        }


def retrieve_snippet(snippet_id: str) -> Dict[str, Any]:
    """
    Retrieve a code snippet from the MCP Code Server
    """
    url = f"{MCP_CODE_SERVER_URL}/retrieve/{snippet_id}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        return {"success": True, "snippet": response.json()}
    except requests.RequestException as e:
        return {
            "success": False,
            "message": f"Error retrieving snippet: {str(e)}"
        }


def print_analysis_results(result: Dict[str, Any]):
    """
    Print analysis results in a readable format
    """
    print("\n=== Analysis Results ===")
    
    if not result.get("success"):
        print(f"Error: {result.get('message', 'Unknown error')}")
        return
    
    issues = result.get("issues", [])
    if issues:
        print(f"\nFound {len(issues)} issues:")
        for i, issue in enumerate(issues, 1):
            print(f"{i}. Line {issue.get('location', {}).get('row', '?')}: "
                  f"{issue.get('message', 'Unknown issue')} "
                  f"({issue.get('code', '?')})")
    else:
        print("No issues found!")
    
    if result.get("formatted_code"):
        print("\n=== Formatted Code ===")
        print(result.get("formatted_code"))


def main():
    # Example code with issues
    example_code = """
def calculate_fibonacci(n):
    '''Calculate Fibonacci sequence up to n elements'''
    result = []
    a, b = 0, 1
    for i in range(n):
      result.append(a)
      a, b = b, a + b
    
    unused_var = "This variable is never used"
    
    return result

# Example usage
if __name__ == "__main__":
    fib_sequence = calculate_fibonacci(10)
    print(f"Fibonacci sequence: {fib_sequence}")
    """
    
    print("Analyzing code...")
    analysis_result = analyze_code(example_code)
    print_analysis_results(analysis_result)
    
    # Store the snippet
    print("\nStoring snippet...")
    storage_result = store_snippet(example_code, snippet_id="fibonacci_example")
    if storage_result.get("success"):
        print(f"Snippet stored with ID: {storage_result.get('id')}")
        
        # Retrieve the snippet
        print("\nRetrieving snippet...")
        retrieval_result = retrieve_snippet(storage_result.get('id'))
        if retrieval_result.get("success"):
            print(f"Retrieved snippet: {retrieval_result.get('snippet', {}).get('language', '')} "
                  f"code, {len(retrieval_result.get('snippet', {}).get('code', ''))} characters")
        else:
            print(f"Error: {retrieval_result.get('message')}")
    else:
        print(f"Error: {storage_result.get('message')}")


if __name__ == "__main__":
    main() 