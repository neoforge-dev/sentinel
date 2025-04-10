#!/usr/bin/env python3
"""
MCP Integration Module

This module provides a unified way to integrate all MCP servers with the main agent,
including the code analysis server and test runner server.

Usage:
    from examples.mcp_integration import register_mcp_tools
    register_mcp_tools(agent)
"""

import os
import sys
import logging
from typing import Optional, List, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from agents.agent import OllamaAgent
    from examples.code_analysis_plugin import register_code_tools
    from examples.test_analysis_plugin import register_test_tools
except ImportError as e:
    print(f"Error: Could not import required modules: {e}")
    print("Make sure you're running from the project root.")
    sys.exit(1)

# Set up logging
logger = logging.getLogger("mcp-integration")
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Configuration
DEFAULT_MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:8080")
DEFAULT_MCP_CODE_SERVER_URL = os.environ.get("MCP_CODE_SERVER_URL", "http://localhost:8000")
DEFAULT_MCP_TEST_SERVER_URL = os.environ.get("MCP_TEST_SERVER_URL", "http://localhost:8001")


def check_server_status(url: str) -> bool:
    """
    Check if a server is running at the given URL
    
    Args:
        url: Server URL to check
        
    Returns:
        True if server is running, False otherwise
    """
    import requests
    
    try:
        response = requests.get(f"{url}/", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


def register_mcp_tools(agent: OllamaAgent, features: Optional[List[str]] = None) -> Dict[str, bool]:
    """
    Register all MCP tools with the agent
    
    Args:
        agent: OllamaAgent instance to register tools with
        features: List of features to enable ('code', 'test', or None for all)
        
    Returns:
        Dictionary of {feature: success} indicating which features were successfully registered
    """
    if features is None:
        features = ['code', 'test']
    
    results = {}
    
    # Register code analysis tools
    if 'code' in features:
        try:
            if check_server_status(DEFAULT_MCP_CODE_SERVER_URL):
                register_code_tools(agent)
                logger.info("Registered code analysis tools")
                results['code'] = True
            else:
                logger.warning(f"Code analysis server not running at {DEFAULT_MCP_CODE_SERVER_URL}")
                results['code'] = False
        except Exception as e:
            logger.error(f"Error registering code analysis tools: {e}")
            results['code'] = False
    
    # Register test tools
    if 'test' in features:
        try:
            if check_server_status(DEFAULT_MCP_TEST_SERVER_URL):
                # Create a wrapper function to convert the agent's register_tool signature
                def register_tool_wrapper(name, func, description):
                    from agents.agent import ToolConfig
                    agent.register_tool(
                        ToolConfig(
                            name=name,
                            description=description,
                            function=func
                        )
                    )
                
                register_test_tools(register_tool_wrapper)
                logger.info("Registered test tools")
                results['test'] = True
            else:
                logger.warning(f"Test server not running at {DEFAULT_MCP_TEST_SERVER_URL}")
                results['test'] = False
        except Exception as e:
            logger.error(f"Error registering test tools: {e}")
            results['test'] = False
    
    return results


def start_services(services: Optional[List[str]] = None) -> Dict[str, bool]:
    """
    Attempt to start the required MCP servers
    
    Args:
        services: List of services to start ('main', 'code', 'test', or None for all)
        
    Returns:
        Dictionary of {service: success} indicating which services were successfully started
    """
    if services is None:
        services = ['main', 'code', 'test']
    
    import subprocess
    import time
    
    results = {}
    
    # Start main MCP server
    if 'main' in services:
        try:
            if not check_server_status(DEFAULT_MCP_SERVER_URL):
                logger.info("Starting main MCP server...")
                process = subprocess.Popen(
                    ["python", "src/mcp_server.py"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                # Wait briefly to see if it starts successfully
                time.sleep(2)
                if process.poll() is None:  # Process is still running
                    results['main'] = True
                else:
                    stdout, stderr = process.communicate()
                    logger.error(f"Failed to start main MCP server: {stderr.decode()}")
                    results['main'] = False
            else:
                logger.info("Main MCP server already running")
                results['main'] = True
        except Exception as e:
            logger.error(f"Error starting main MCP server: {e}")
            results['main'] = False
    
    # Start code analysis server
    if 'code' in services:
        try:
            if not check_server_status(DEFAULT_MCP_CODE_SERVER_URL):
                logger.info("Starting code analysis server...")
                process = subprocess.Popen(
                    ["python", "agents/mcp_code_server.py"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                # Wait briefly to see if it starts successfully
                time.sleep(2)
                if process.poll() is None:  # Process is still running
                    results['code'] = True
                else:
                    stdout, stderr = process.communicate()
                    logger.error(f"Failed to start code analysis server: {stderr.decode()}")
                    results['code'] = False
            else:
                logger.info("Code analysis server already running")
                results['code'] = True
        except Exception as e:
            logger.error(f"Error starting code analysis server: {e}")
            results['code'] = False
    
    # Start test runner server
    if 'test' in services:
        try:
            if not check_server_status(DEFAULT_MCP_TEST_SERVER_URL):
                logger.info("Starting test runner server...")
                process = subprocess.Popen(
                    ["python", "agents/mcp_test_server.py"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                # Wait briefly to see if it starts successfully
                time.sleep(2)
                if process.poll() is None:  # Process is still running
                    results['test'] = True
                else:
                    stdout, stderr = process.communicate()
                    logger.error(f"Failed to start test runner server: {stderr.decode()}")
                    results['test'] = False
            else:
                logger.info("Test runner server already running")
                results['test'] = True
        except Exception as e:
            logger.error(f"Error starting test runner server: {e}")
            results['test'] = False
    
    return results


if __name__ == "__main__":
    """Example usage of this module"""
    import argparse
    
    parser = argparse.ArgumentParser(description='MCP Integration Module')
    parser.add_argument('--start', action='store_true', help='Start MCP servers')
    parser.add_argument('--services', nargs='+', choices=['main', 'code', 'test'], 
                        help='Specific services to start')
    parser.add_argument('--check', action='store_true', help='Check server status')
    
    args = parser.parse_args()
    
    if args.start:
        print("Starting MCP services...")
        results = start_services(args.services)
        for service, success in results.items():
            print(f"- {service}: {'✅ Running' if success else '❌ Failed'}")
    
    if args.check:
        print("Checking MCP services status...")
        print(f"- Main MCP: {'✅ Running' if check_server_status(DEFAULT_MCP_SERVER_URL) else '❌ Not running'}")
        print(f"- Code Analysis: {'✅ Running' if check_server_status(DEFAULT_MCP_CODE_SERVER_URL) else '❌ Not running'}")
        print(f"- Test Runner: {'✅ Running' if check_server_status(DEFAULT_MCP_TEST_SERVER_URL) else '❌ Not running'}")
    
    if not args.start and not args.check:
        # Example of integrating with the agent
        try:
            print("Creating agent and registering tools...")
            agent = OllamaAgent()
            
            # First make sure services are running
            start_services()
            
            # Register tools
            results = register_mcp_tools(agent)
            
            print("Registration results:")
            for feature, success in results.items():
                print(f"- {feature}: {'✅ Registered' if success else '❌ Failed'}")
                
            print("\nAvailable tools:")
            for name, tool in agent.context.tools.items():
                print(f"- {name}: {tool.description}")
                
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1) 