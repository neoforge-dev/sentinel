#!/usr/bin/env python3
"""
Plugin for connecting our agent with the MCP Code Server
Adds code analysis and formatting capabilities to the agent
"""

import os
import sys
import json
import requests
from typing import Dict, Any, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from agents.agent import OllamaAgent, ToolConfig, TaskType
except ImportError:
    print("Error: Could not import from agents.agent. Make sure you're running from the project root.")
    sys.exit(1)

# Default settings
MCP_CODE_SERVER_URL = os.environ.get("MCP_CODE_SERVER_URL", "http://localhost:8081")


def analyze_code_with_mcp(code: str, language: str = "python") -> Dict[str, Any]:
    """
    Analyze code using the MCP Code Server
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


def format_code_with_mcp(code: str, language: str = "python") -> Dict[str, Any]:
    """
    Format code using the MCP Code Server
    """
    # Analysis also returns formatted code
    result = analyze_code_with_mcp(code, language)
    
    if result["success"] and result.get("formatted_code"):
        return {
            "success": True,
            "formatted_code": result["formatted_code"],
            "message": "Formatting successful"
        }
    else:
        return {
            "success": False,
            "formatted_code": None,
            "message": result.get("message", "Formatting failed")
        }


def store_snippet_with_mcp(code: str, language: str = "python", snippet_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Store a code snippet in the MCP Code Server
    """
    if not snippet_id:
        import uuid
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


def register_code_tools(agent: OllamaAgent):
    """
    Register code analysis tools with the agent
    """
    # Code Analysis Tool
    agent.register_tool(
        ToolConfig(
            name="analyze_code",
            description="Analyze code for issues and suggestions using Ruff",
            parameters={
                "code": "The code to analyze",
                "language": "Programming language (default: python)"
            },
            function=analyze_code_with_mcp
        )
    )
    
    # Code Formatting Tool
    agent.register_tool(
        ToolConfig(
            name="format_code",
            description="Format code according to best practices using Ruff",
            parameters={
                "code": "The code to format",
                "language": "Programming language (default: python)"
            },
            function=format_code_with_mcp
        )
    )
    
    # Code Storage Tool
    agent.register_tool(
        ToolConfig(
            name="store_code",
            description="Store a code snippet for later retrieval",
            parameters={
                "code": "The code to store",
                "language": "Programming language (default: python)",
                "snippet_id": "Optional ID for the snippet (default: auto-generated UUID)"
            },
            function=store_snippet_with_mcp
        )
    )


if __name__ == "__main__":
    # Example usage
    agent = OllamaAgent(model="mistral:7b")
    register_code_tools(agent)
    
    example_code = """
def hello_world():
    print ('Hello, world!')
    
    unused_var = "This is never used"
    
    return None
"""
    
    print("=== Code Analysis Example ===")
    result = agent.execute_tool("analyze_code", {"code": example_code})
    
    if result.get("success"):
        issues = result.get("issues", [])
        if issues:
            print(f"Found {len(issues)} issues:")
            for i, issue in enumerate(issues, 1):
                print(f"{i}. Line {issue.get('location', {}).get('row', '?')}: "
                      f"{issue.get('message', 'Unknown issue')}")
        else:
            print("No issues found!")
            
        if result.get("formatted_code"):
            print("\n=== Formatted Code ===")
            print(result.get("formatted_code"))
    else:
        print(f"Error: {result.get('message', 'Unknown error')}")
    
    print("\n=== Available Tools ===")
    for name, tool in agent.context.tools.items():
        print(f"- {name}: {tool.description}") 