#!/usr/bin/env python3
"""
Script to initialize an agent with both MCP integrations:
- Code Analysis MCP: Code formatting, analysis, and storage
- Test Runner MCP: Run tests, analyze failures, and test fixes

This integrates all MCP server features into a single powerful agent.
"""

import os
import sys
import argparse

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from agents.agent import OllamaAgent
    from examples.code_analysis_plugin import register_code_tools
    from examples.test_runner_plugin import register_test_tools
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Make sure you're running from the project root and have all dependencies installed.")
    sys.exit(1)


def setup_agent(model="mistral:7b", mcp_enabled=True):
    """
    Set up an agent with both MCP integrations
    
    Args:
        model: Ollama model to use
        mcp_enabled: Whether to enable MCP for the agent itself
        
    Returns:
        Configured OllamaAgent instance
    """
    # Initialize the agent
    agent = OllamaAgent(model=model, mcp_enabled=mcp_enabled)
    
    # Register code analysis tools
    register_code_tools(agent)
    
    # Register test runner tools
    register_test_tools(agent)
    
    return agent


def print_available_tools(agent):
    """Print all available tools registered with the agent"""
    print("\n=== Available Tools ===")
    
    # Group tools by category for better organization
    categories = {
        "Code": [],
        "Test": [],
        "Other": []
    }
    
    for name, tool in agent.context.tools.items():
        if name.startswith("analyze_code") or name.startswith("format_code") or name.startswith("store_"):
            categories["Code"].append((name, tool.description))
        elif name.startswith("run_tests") or name.startswith("test_") or name.startswith("analyze_test") or name.startswith("get_"):
            categories["Test"].append((name, tool.description))
        else:
            categories["Other"].append((name, tool.description))
    
    # Print tools by category
    for category, tools in categories.items():
        if tools:
            print(f"\n{category} Tools:")
            for name, description in sorted(tools):
                print(f"- {name}: {description}")


def main():
    """Initialize agent with both MCPs and demonstrate functionality"""
    parser = argparse.ArgumentParser(description="Initialize agent with MCP integrations")
    parser.add_argument("--model", default="mistral:7b", help="Ollama model to use")
    parser.add_argument("--no-mcp", action="store_true", help="Disable MCP integration")
    args = parser.parse_args()
    
    # Set up the agent
    print(f"Initializing agent with model: {args.model}")
    agent = setup_agent(model=args.model, mcp_enabled=not args.no_mcp)
    
    # Print available tools
    print_available_tools(agent)
    
    # Verify MCP servers are running
    code_mcp_url = os.environ.get("MCP_CODE_SERVER_URL", "http://localhost:8081")
    test_mcp_url = os.environ.get("MCP_TEST_SERVER_URL", "http://localhost:8082")
    
    print("\n=== MCP Server Status ===")
    
    # Check Code MCP
    try:
        import requests
        response = requests.get(f"{code_mcp_url}")
        if response.status_code == 200:
            print(f"✅ Code MCP Server: Connected ({code_mcp_url})")
        else:
            print(f"❌ Code MCP Server: Error - Status code {response.status_code} ({code_mcp_url})")
    except requests.RequestException:
        print(f"❌ Code MCP Server: Not running or unreachable ({code_mcp_url})")
    
    # Check Test MCP
    try:
        import requests
        response = requests.get(f"{test_mcp_url}")
        if response.status_code == 200:
            print(f"✅ Test MCP Server: Connected ({test_mcp_url})")
        else:
            print(f"❌ Test MCP Server: Error - Status code {response.status_code} ({test_mcp_url})")
    except requests.RequestException:
        print(f"❌ Test MCP Server: Not running or unreachable ({test_mcp_url})")
    
    print("\nAgent is ready!")
    print("Use agent.execute_tool('tool_name', parameters) to run tools")
    print("Example: agent.execute_tool('run_tests', {'project_path': '/path/to/project'})")
    
    # Return agent for interactive use
    return agent


if __name__ == "__main__":
    agent = main()
    
    # Make the agent available in interactive sessions
    print("\nThe 'agent' object is now available for use.")
    
    # If running in a non-interactive environment, keep the script alive
    try:
        import IPython
        IPython.embed(banner1="", banner2="")
    except ImportError:
        try:
            import code
            code.interact(local=locals())
        except ImportError:
            # If no interactive shells are available, just exit
            pass 