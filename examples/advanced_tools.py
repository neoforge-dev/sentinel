#!/usr/bin/env python3
"""
Advanced tools plugin for the Matrix agent
Shows how to extend the agent with custom tools
"""

import os
import sys
import json
import time
from typing import Dict, Any, Optional, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from agents.agent import OllamaAgent, ToolConfig, TaskType
except ImportError:
    print("Error: Could not import from agents.agent. Make sure you're running from the project root.")
    sys.exit(1)


def summarize_text(text: str, max_length: int = 200) -> Dict[str, Any]:
    """
    Summarize a text using the agent's LLM
    """
    agent = OllamaAgent(mcp_enabled=False)
    
    prompt = f"""
    Please summarize the following text in about {max_length//10} sentences:
    
    {text}
    
    Keep your summary under {max_length} characters.
    """
    
    try:
        summary = agent.generate(prompt, task_type=TaskType.QUESTION_ANSWERING)
        return {
            "success": True,
            "summary": summary,
            "original_length": len(text),
            "summary_length": len(summary)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def code_review(code: str, language: str = "python") -> Dict[str, Any]:
    """
    Review code using the agent's LLM
    """
    agent = OllamaAgent(mcp_enabled=False)
    
    prompt = f"""
    Please review the following {language} code:
    
    ```{language}
    {code}
    ```
    
    Identify:
    1. Bugs or errors
    2. Security issues
    3. Performance problems
    4. Style/readability issues
    
    Format as JSON with keys: bugs, security_issues, performance_issues, style_issues
    """
    
    try:
        review_text = agent.generate(prompt, task_type=TaskType.CODE_GENERATION)
        
        # Try to extract JSON
        try:
            # Look for JSON pattern in the response
            json_match = review_text.find('{')
            if json_match >= 0:
                # Extract JSON part
                json_text = review_text[json_match:]
                review = json.loads(json_text)
            else:
                # Fallback structure
                review = {
                    "bugs": ["Could not parse response"],
                    "security_issues": [],
                    "performance_issues": [],
                    "style_issues": []
                }
        except json.JSONDecodeError:
            review = {
                "bugs": ["Failed to parse review"],
                "security_issues": [],
                "performance_issues": [],
                "style_issues": []
            }
        
        return {
            "success": True,
            "review": review,
            "raw_response": review_text
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def register_advanced_tools(agent: OllamaAgent):
    """
    Register all advanced tools with the agent
    """
    # Text summarization tool
    agent.register_tool(
        ToolConfig(
            name="summarize_text",
            description="Summarize a text to a specified length",
            parameters={
                "text": "The text to summarize",
                "max_length": "Maximum length of the summary (default: 200)"
            },
            function=summarize_text
        )
    )
    
    # Code review tool
    agent.register_tool(
        ToolConfig(
            name="code_review",
            description="Review code to find issues",
            parameters={
                "code": "The code to review",
                "language": "Programming language (default: python)"
            },
            function=code_review
        )
    )
    
    # Example of a simplified web search tool
    agent.register_tool(
        ToolConfig(
            name="simple_web_search",
            description="Search the web for information (simplified)",
            parameters={
                "query": "Search query"
            },
            function=lambda query: {
                "success": True,
                "results": [
                    f"Simulated search result for: {query}",
                    f"Another simulated result about {query}",
                    f"Third simulated result related to {query}"
                ],
                "note": "This is a simulation. Implement actual web search API here."
            }
        )
    )


if __name__ == "__main__":
    # Example of how to use the advanced tools
    agent = OllamaAgent(model="mistral:7b")
    register_advanced_tools(agent)
    
    # Example of using the summarize tool
    text_to_summarize = """
    The Matrix is a 1999 science fiction action film written and directed by the Wachowskis. 
    It depicts a dystopian future in which humanity is unknowingly trapped inside a simulated reality, 
    the Matrix, which intelligent machines have created to distract humans while using their bodies as 
    an energy source. When computer programmer Thomas Anderson, under the hacker alias "Neo", uncovers 
    the truth, he joins a rebellion against the machines along with other people who have been freed from 
    the Matrix.
    """
    
    result = agent.execute_tool("summarize_text", {"text": text_to_summarize})
    
    print("=== Text Summarization Example ===")
    if result.get("success"):
        print(f"Summary: {result['summary']}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    print("\n=== Available Tools ===")
    for name, tool in agent.context.tools.items():
        print(f"- {name}: {tool.description}") 