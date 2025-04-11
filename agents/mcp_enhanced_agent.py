#!/usr/bin/env python3
"""
Enhanced Agent with MCP Integration

This module provides an enhanced agent that integrates with all MCP servers,
including the main MCP server, code analysis server, and test runner server.

Usage:
    from agents.mcp_enhanced_agent import MCPEnhancedAgent
    agent = MCPEnhancedAgent()
    agent.run_conversation()
"""

import os
import sys
import logging
from typing import Dict, List, Any, Optional, Union

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from agents.agent import OllamaAgent, TaskType
    from examples.mcp_integration import register_mcp_tools, start_services, check_server_status
except ImportError as e:
    print(f"Error: Could not import required modules: {e}")
    print("Make sure you're running from the project root.")
    sys.exit(1)

# Set up logging
logger = logging.getLogger("mcp-enhanced-agent")
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


class MCPEnhancedAgent(OllamaAgent):
    """
    Enhanced agent with full MCP server integration
    Extends the OllamaAgent with code analysis and test runner capabilities
    """
    
    def __init__(
        self,
        model: str = "mistral:7b",
        mcp_enabled: bool = True,
        optimize_for_hardware: bool = True,
        workspace_path: Optional[str] = None,
        debug: bool = False,
        start_mcp_servers: bool = True,
        mcp_features: Optional[List[str]] = None
    ):
        """
        Initialize the enhanced agent
        
        Args:
            model: Ollama model to use
            mcp_enabled: Whether to enable MCP integration
            optimize_for_hardware: Whether to optimize settings for available hardware
            workspace_path: Path to the agent's workspace
            debug: Whether to enable debug logging
            start_mcp_servers: Whether to start MCP servers automatically
            mcp_features: List of MCP features to enable ('code', 'test', or None for all)
        """
        # Initialize the base OllamaAgent
        super().__init__(
            model=model,
            mcp_enabled=mcp_enabled,
            optimize_for_hardware=optimize_for_hardware,
            workspace_path=workspace_path,
            debug=debug
        )
        
        if debug:
            logger.setLevel(logging.DEBUG)
        
        # Store additional configuration
        self.mcp_features = mcp_features or ['code', 'test']
        
        # Start required MCP servers if enabled
        if start_mcp_servers and mcp_enabled:
            logger.info("Starting MCP servers...")
            services_to_start = ['main']
            if 'code' in self.mcp_features:
                services_to_start.append('code')
            if 'test' in self.mcp_features:
                services_to_start.append('test')
                
            service_results = start_services(services_to_start)
            
            for service, success in service_results.items():
                if success:
                    logger.info(f"Service '{service}' started successfully")
                else:
                    logger.warning(f"Failed to start service '{service}'")
        
        # Register MCP tools
        if mcp_enabled:
            logger.info("Registering MCP tools...")
            tool_results = register_mcp_tools(self, self.mcp_features)
            
            for feature, success in tool_results.items():
                if success:
                    logger.info(f"Feature '{feature}' registered successfully")
                else:
                    logger.warning(f"Failed to register feature '{feature}'")
    
    def run_tests(
        self,
        project_path: Optional[str] = None,
        test_path: Optional[str] = None,
        runner: str = "pytest",
        mode: str = "local",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Run tests in a project
        
        Args:
            project_path: Path to the project (defaults to workspace_path)
            test_path: Path to tests relative to project_path
            runner: Test runner to use ('pytest', 'unittest', 'uv')
            mode: Execution mode ('local' or 'docker')
            **kwargs: Additional arguments to pass to the test runner
            
        Returns:
            Dictionary containing test results
        """
        # Use workspace path as default project path if not specified
        if not project_path:
            project_path = self.context.workspace_path
            if not project_path:
                raise ValueError("No project path specified and no workspace path set")
        
        # Check if the test tool is available
        if "run_tests" not in self.context.tools:
            raise RuntimeError("Test tools not registered. Make sure the test MCP server is running.")
        
        # Execute the tool
        print(f"Initiating test run (Runner: {runner}, Mode: {mode})...")
        result = self.execute_tool("run_tests", {
            "project_path": project_path,
            "test_path": test_path,
            "runner": runner,
            "mode": mode,
            **kwargs
        })
        
        # Handle potential streaming output
        if isinstance(result, dict) and "details" in result and "summary" in result and "status" in result:
            # Check if details look like streamed output already printed by plugin
            # (The plugin currently prints and returns the full log in 'details')
            if "--- Streaming Test Output ---" in result["details"]:
                print(f"\nTest run finished. Status: {result.get('status', 'unknown')}")
                print(f"Summary: {result.get('summary', 'N/A')}")
                # Optionally, still return the full result dict
                return result 
            else:
                # If not streamed (e.g., Docker run), print summary and details
                print(f"\nTest run finished. Status: {result.get('status', 'unknown')}")
                print(f"Summary: {result.get('summary', 'N/A')}")
                print("--- Details ---")
                print(result["details"])
                print("---------------")
                return result
        else:
             # Fallback for unexpected result format
            print("Received unexpected result format from test runner:")
            print(result)
            return {"status": "error", "summary": "Unexpected result format", "details": str(result)}
    
    def analyze_code(
        self,
        code: str,
        language: str = "python"
    ) -> Dict[str, Any]:
        """
        Analyze code for issues and formatting
        
        Args:
            code: Code to analyze
            language: Programming language of the code
            
        Returns:
            Dictionary containing analysis results
        """
        # Check if the code analysis tool is available
        if "analyze_code" not in self.context.tools:
            raise RuntimeError("Code analysis tools not registered. Make sure the code MCP server is running.")
        
        # Execute the tool
        result = self.execute_tool("analyze_code", {
            "code": code,
            "language": language
        })
        
        return result
    
    def format_code(
        self,
        code: str,
        language: str = "python"
    ) -> Dict[str, Any]:
        """
        Format code according to best practices
        
        Args:
            code: Code to format
            language: Programming language of the code
            
        Returns:
            Dictionary containing formatted code
        """
        # Check if the code formatting tool is available
        if "format_code" not in self.context.tools:
            raise RuntimeError("Code formatting tools not registered. Make sure the code MCP server is running.")
        
        # Execute the tool
        result = self.execute_tool("format_code", {
            "code": code,
            "language": language
        })
        
        return result
    
    def generate_and_analyze_code(
        self,
        code_description: str,
        language: str = "python"
    ) -> Dict[str, Any]:
        """
        Generate code based on a description and analyze it
        
        Args:
            code_description: Description of the code to generate
            language: Programming language for the code
            
        Returns:
            Dictionary containing generated code, formatted code, and analysis
        """
        # Generate code
        generated_code = self.generate_code(code_description, language)
        
        # Analyze and format the generated code
        try:
            analysis_result = self.analyze_code(generated_code, language)
            format_result = self.format_code(generated_code, language)
            
            return {
                "success": True,
                "original_code": generated_code,
                "formatted_code": format_result.get("formatted_code", generated_code),
                "analysis": analysis_result,
                "issues": analysis_result.get("issues", [])
            }
        except Exception as e:
            return {
                "success": False,
                "original_code": generated_code,
                "error": str(e)
            }
    
    def help(self):
        """
        Display help information for the enhanced agent
        """
        print("\n=== MCPEnhancedAgent Help ===")
        print("This agent extends the base OllamaAgent with specialized MCP server integration.")
        print("\nAvailable MCP Features:")
        
        # Check which features are available
        code_available = "analyze_code" in self.context.tools
        test_available = "run_tests" in self.context.tools
        
        print(f"- Code Analysis: {'✅ Available' if code_available else '❌ Not available'}")
        print(f"- Test Runner: {'✅ Available' if test_available else '❌ Not available'}")
        
        print("\nCommands:")
        print("  /help - Display this help message")
        print("  /test <project_path> [test_path] - Run tests in a project")
        print("  /analyze - Analyze code (paste code after this command)")
        print("  /format - Format code (paste code after this command)")
        print("  /exit - Exit the conversation")
        
        # Show available tools
        print("\nRegistered Tools:")
        for name, tool in self.context.tools.items():
            print(f"- {name}: {tool.description}")
    
    def run_conversation(self):
        """
        Run an interactive conversation with the enhanced agent
        Extends the base method with additional commands
        """
        print(f"\n=== MCPEnhancedAgent ({self.model}) ===")
        print("Type /help for available commands, or /exit to quit.")
        
        history = []
        
        while True:
            try:
                # Get user input
                user_input = input("\nYou: ")
                
                # Check for commands
                if user_input.lower() in ['/exit', '/quit']:
                    print("Exiting conversation.")
                    break
                
                elif user_input.lower() == '/help':
                    self.help()
                    continue
                
                elif user_input.lower().startswith('/test'):
                    # Parse test command
                    parts = user_input.split(maxsplit=2)
                    if len(parts) < 2:
                        print("Usage: /test <project_path> [test_path]")
                        continue
                        
                    project_path = parts[1]
                    test_path = parts[2] if len(parts) > 2 else None
                    
                    print(f"Running tests in {project_path}...")
                    result = self.run_tests(
                        project_path=project_path,
                        test_path=test_path
                    )
                    
                    if result.get("success", False):
                        # If success, format the test result
                        test_id = result.get("test_id")
                        if test_id:
                            test_result = self.execute_tool("get_test_result", {"test_id": test_id})
                            if test_result.get("success", False):
                                formatted = self.execute_tool("format_test_result", {"result": test_result})
                                print("\nTest Results:")
                                print(formatted)
                    else:
                        print(f"Error: {result.get('error', 'Unknown error')}")
                    
                    continue
                
                elif user_input.lower() == '/analyze':
                    print("Enter or paste code to analyze (Ctrl+D or Ctrl+Z on a new line to finish):")
                    code_lines = []
                    while True:
                        try:
                            line = input()
                            code_lines.append(line)
                        except EOFError:
                            break
                    
                    code = "\n".join(code_lines)
                    if not code.strip():
                        print("No code provided.")
                        continue
                        
                    print("Analyzing code...")
                    result = self.analyze_code(code)
                    
                    if result.get("success", False):
                        issues = result.get("issues", [])
                        if issues:
                            print(f"\nFound {len(issues)} issues:")
                            for i, issue in enumerate(issues, 1):
                                print(f"{i}. Line {issue.get('location', {}).get('row', '?')}: "
                                    f"{issue.get('message', 'Unknown issue')}")
                        else:
                            print("No issues found!")
                    else:
                        print(f"Error: {result.get('message', 'Unknown error')}")
                    
                    continue
                
                elif user_input.lower() == '/format':
                    print("Enter or paste code to format (Ctrl+D or Ctrl+Z on a new line to finish):")
                    code_lines = []
                    while True:
                        try:
                            line = input()
                            code_lines.append(line)
                        except EOFError:
                            break
                    
                    code = "\n".join(code_lines)
                    if not code.strip():
                        print("No code provided.")
                        continue
                        
                    print("Formatting code...")
                    result = self.format_code(code)
                    
                    if result.get("success", False) and result.get("formatted_code"):
                        print("\nFormatted Code:")
                        print(result["formatted_code"])
                    else:
                        print(f"Error: {result.get('message', 'Unknown error')}")
                    
                    continue
                
                # For regular messages, use the base agent's functionality
                # Add the message to history
                history.append({"role": "user", "content": user_input})
                
                # Prepare the conversation input
                full_prompt = self._prepare_prompt(history)
                
                # Determine the task type based on the content
                task_type = self._determine_task_type(user_input)
                
                # Generate a response
                response = self.generate(full_prompt, task_type)
                
                # Print the response
                print("\nAgent:", response)
                
                # Add the response to history
                history.append({"role": "assistant", "content": response})
                
            except KeyboardInterrupt:
                print("\nInterrupted. Type /exit to quit.")
            except Exception as e:
                print(f"\nError: {str(e)}")
                if 'debug' in vars(self) and self.debug:
                    import traceback
                    traceback.print_exc()
    
    def _prepare_prompt(self, history: List[Dict[str, str]]) -> str:
        """
        Prepare a prompt from conversation history
        
        Args:
            history: List of conversation messages
            
        Returns:
            Formatted prompt string
        """
        prompt = ""
        
        for message in history:
            role = message["role"]
            content = message["content"]
            
            if role == "user":
                prompt += f"User: {content}\n\n"
            elif role == "assistant":
                prompt += f"Assistant: {content}\n\n"
        
        prompt += "Assistant: "
        return prompt
    
    def _determine_task_type(self, user_input: str) -> TaskType:
        """
        Determine the task type based on user input
        
        Args:
            user_input: User's message
            
        Returns:
            Appropriate TaskType enum value
        """
        lower_input = user_input.lower()
        
        # Check for code-related keywords
        code_keywords = ['code', 'function', 'class', 'implement', 'programming',
                        'script', 'algorithm', 'module', 'method', 'variable']
        
        plan_keywords = ['plan', 'steps', 'approach', 'strategy', 'procedure',
                        'process', 'methodology', 'outline', 'roadmap']
        
        if any(keyword in lower_input for keyword in code_keywords):
            return TaskType.CODE_GENERATION
        
        if any(keyword in lower_input for keyword in plan_keywords):
            return TaskType.PLANNING
        
        # Default to question answering
        return TaskType.QUESTION_ANSWERING


def main():
    """Command line interface for the enhanced agent"""
    import argparse
    
    parser = argparse.ArgumentParser(description='MCP Enhanced Agent')
    parser.add_argument('--model', default='mistral:7b', help='Ollama model to use')
    parser.add_argument('--no-mcp', action='store_true', help='Disable MCP integration')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--no-optimize', action='store_true', help='Disable hardware optimization')
    parser.add_argument('--workspace', help='Path to agent workspace')
    parser.add_argument('--no-startup', action='store_true', help='Do not start MCP servers automatically')
    parser.add_argument('--features', nargs='+', choices=['code', 'test'], 
                      help='Specific MCP features to enable')
    
    args = parser.parse_args()
    
    # Create and run the enhanced agent
    agent = MCPEnhancedAgent(
        model=args.model,
        mcp_enabled=not args.no_mcp,
        optimize_for_hardware=not args.no_optimize,
        workspace_path=args.workspace,
        debug=args.debug,
        start_mcp_servers=not args.no_startup,
        mcp_features=args.features
    )
    
    agent.run_conversation()


if __name__ == "__main__":
    main() 