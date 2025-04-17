#!/usr/bin/env python3
"""
Matrix-inspired UV single-file agent for Ollama with MCP integration

Dependencies:
- requests==2.31.0
- pydantic==2.4.2
- tqdm==4.66.1
- colorama==0.4.6
- tenacity==8.2.3
"""
# [dependencies]
# requests = "^2.31.0"
# pydantic = "^2.4.2" 
# tqdm = "^4.66.1"
# colorama = "^0.4.6"
# tenacity = "^8.2.3"

import argparse
import sys
import os
from typing import Dict, Any, Optional, List, Tuple, Union, Callable, Iterator
import json
import time
import logging
from enum import Enum
from dataclasses import dataclass, field
import re
import traceback
from pathlib import Path

# Third-party imports
import requests
from pydantic import BaseModel, Field
from tqdm import tqdm
import colorama
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Initialize colorama for cross-platform colored terminal output
colorama.init()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(stream=sys.stdout)
    ]
)
logger = logging.getLogger("neo-agent")

# Constants
DEFAULT_MODEL = "mistral:7b-instruct"
DEEPSEEK_MODEL = "deepseek-r1:32b"
DEFAULT_MCP_URL = "http://localhost:8080"
DEFAULT_OLLAMA_URL = "http://localhost:11434"
MAX_RETRIES = 3
RETRY_WAIT_MULTIPLIER = 2
RETRY_MAX_WAIT = 30

# Model-specific settings
MODEL_SETTINGS = {
    "mistral:7b-instruct": {
        "temperature": 0.7,
        "max_tokens": 2048,
        "top_p": 0.9,
        "system_prompt": "You are a helpful AI assistant using the Mistral 7B model. Answer questions accurately and concisely."
    },
    "deepseek-r1:32b": {
        "temperature": 0.5,
        "max_tokens": 4096,
        "top_p": 0.95,
        "system_prompt": "You are a powerful AI assistant running on the DeepSeek-R1 32B model. Provide detailed, accurate, and well-reasoned responses."
    }
}

# Task types
class TaskType(str, Enum):
    QUESTION_ANSWERING = "question_answering"
    CODE_GENERATION = "code_generation"
    PLANNING = "planning"
    TOOL_EXECUTION = "tool_execution"


class MCPResource(BaseModel):
    """Resource model for MCP interactions"""
    id: str
    content: str
    metadata: Optional[Dict[str, Any]] = None


class ToolConfig(BaseModel):
    """Configuration for a tool that the agent can use"""
    name: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    function: Optional[Callable] = None


@dataclass
class AgentContext:
    """Context container for the agent"""
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    current_task: Optional[str] = None
    resources: Dict[str, MCPResource] = field(default_factory=dict)
    tools: Dict[str, ToolConfig] = field(default_factory=dict)
    workspace_path: Optional[str] = None
    task_plan: List[str] = field(default_factory=list)


class OllamaAgent:
    """Advanced agent for Ollama with planning, code generation, and MCP integration"""
    
    def __init__(
        self, 
        model: str = DEFAULT_MODEL, 
        mcp_enabled: bool = True,
        optimize_for_hardware: bool = True,
        workspace_path: Optional[str] = None,
        debug: bool = False
    ):
        """Initialize the agent with configuration options"""
        self.model = model
        self.mcp_enabled = mcp_enabled
        self.optimize_for_hardware = optimize_for_hardware
        self.ollama_url = os.environ.get("OLLAMA_HOST", DEFAULT_OLLAMA_URL)
        self.mcp_url = os.environ.get("MCP_SERVER_URL", DEFAULT_MCP_URL)
        
        # Set up debug mode
        if debug:
            logger.setLevel(logging.DEBUG)
            
        # Model settings from config or defaults
        self.model_settings = MODEL_SETTINGS.get(model, MODEL_SETTINGS[DEFAULT_MODEL])
        
        # Initialize context
        self.context = AgentContext(
            workspace_path=workspace_path or os.getcwd()
        )
        
        # Configure hardware optimization if enabled
        if optimize_for_hardware:
            self._configure_for_hardware()
        
        # Register default tools
        self._register_default_tools()
        
        logger.info(f"Agent initialized with model: {model}")
        logger.info(f"MCP integration: {'enabled' if mcp_enabled else 'disabled'}")
    
    def _configure_for_hardware(self):
        """Configure model settings based on available hardware"""
        try:
            import psutil
            available_ram = psutil.virtual_memory().available / (1024**3)  # GB
            cpu_count = psutil.cpu_count(logical=False)
            
            logger.debug(f"Available RAM: {available_ram:.2f} GB, CPU cores: {cpu_count}")
            
            # Adjust settings based on hardware
            if self.model == DEEPSEEK_MODEL:
                if available_ram < 16:
                    logger.warning(f"Limited RAM detected ({available_ram:.2f} GB). DeepSeek model may run slowly.")
                    # Adjust to use less memory
                    self.model_settings["max_tokens"] = 2048
            
            # Configure batch size based on available RAM
            batch_size = max(1, min(8, int(available_ram / 4)))
            self.model_settings["batch_size"] = batch_size
            
        except ImportError:
            logger.warning("psutil not available. Hardware optimization disabled.")
            return
        except Exception as e:
            logger.warning(f"Error during hardware configuration: {e}")
    
    def _register_default_tools(self):
        """Register the default set of tools"""
        default_tools = [
            ToolConfig(
                name="file_read",
                description="Read a file from the workspace",
                parameters={"path": "Path to the file to read"}
            ),
            ToolConfig(
                name="file_write", 
                description="Write content to a file in the workspace",
                parameters={
                    "path": "Path to the file to write",
                    "content": "Content to write to the file"
                }
            ),
            ToolConfig(
                name="execute_command",
                description="Execute a shell command",
                parameters={"command": "Command to execute"}
            ),
            ToolConfig(
                name="web_search",
                description="Search the web for information",
                parameters={"query": "Search query"}
            )
        ]
        
        for tool in default_tools:
            self.register_tool(tool)
    
    def register_tool(self, tool_config: ToolConfig):
        """Register a tool for the agent to use"""
        self.context.tools[tool_config.name] = tool_config
        logger.debug(f"Registered tool: {tool_config.name}")
    
    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=RETRY_WAIT_MULTIPLIER, max=RETRY_MAX_WAIT),
        retry=retry_if_exception_type((requests.RequestException, ConnectionError))
    )
    def generate(self, prompt: str, task_type: TaskType = TaskType.QUESTION_ANSWERING) -> Iterator[str]:
        """Generate a response using Ollama, yielding results incrementally (streaming)."""
        # Adjust settings based on task type
        settings = self.model_settings.copy()
        if task_type == TaskType.CODE_GENERATION:
            settings["temperature"] = 0.2  # Lower temperature for code
        elif task_type == TaskType.PLANNING:
            settings["temperature"] = 0.7  # Moderate temperature for planning
        
        try:
            logger.debug(f"Sending streaming request to Ollama ({self.model}, task: {task_type})")
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": True,
                    "temperature": settings.get("temperature", 0.7),
                    "max_tokens": settings.get("max_tokens", 2048),
                    "top_p": settings.get("top_p", 0.9),
                    "system": settings.get("system_prompt", "")
                },
                timeout=60,
                stream=True
            )
            
            # Check for initial connection errors (e.g., 404, 500 before stream starts)
            response.raise_for_status() 

            # Process the stream
            full_response_for_error = ""
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    full_response_for_error += decoded_line + '\n'
                    try:
                        chunk = json.loads(decoded_line)
                        if "response" in chunk:
                            yield chunk["response"]
                        if chunk.get("done"):
                            logger.debug("Ollama stream finished.")
                            break
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to decode JSON chunk: {decoded_line}")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama API request failed: {e}", exc_info=True)
            yield f"[ERROR: Ollama request failed: {e}]"
        except Exception as e:
            logger.error(f"Unexpected error during Ollama generation: {e}", exc_info=True)
            logger.error(f"Last received content before error: {full_response_for_error[-500:]}")
            yield f"[ERROR: Unexpected error: {e}]"
    
    def get_context(self) -> Optional[Dict[str, Any]]:
        """Get context from MCP server if enabled"""
        if not self.mcp_enabled:
            return None
            
        try:
            logger.debug("Requesting context from MCP")
            response = requests.get(f"{self.mcp_url}/context", timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Could not fetch MCP context. Status: {response.status_code}")
                return None
        except requests.RequestException as e:
            logger.warning(f"MCP service request error: {str(e)}")
            return None
        except Exception as e:
            logger.warning(f"MCP service error: {str(e)}")
            return None
    
    def load_resource(self, resource_id: str) -> Optional[MCPResource]:
        """Load a resource from MCP or local cache"""
        # Check if already in local cache
        if resource_id in self.context.resources:
            return self.context.resources[resource_id]
        
        # Try to fetch from MCP if enabled
        if self.mcp_enabled:
            try:
                response = requests.get(
                    f"{self.mcp_url}/context/documents/{resource_id}", 
                    timeout=10
                )
                if response.status_code == 200:
                    resource_data = response.json()
                    resource = MCPResource(**resource_data)
                    # Cache the resource
                    self.context.resources[resource_id] = resource
                    return resource
                else:
                    logger.warning(f"Resource not found: {resource_id}")
            except Exception as e:
                logger.error(f"Error loading resource {resource_id}: {str(e)}")
        
        return None
    
    def save_resource(self, resource: MCPResource) -> bool:
        """Save a resource to MCP and local cache"""
        # Add to local cache
        self.context.resources[resource.id] = resource
        
        # Save to MCP if enabled
        if self.mcp_enabled:
            try:
                response = requests.post(
                    f"{self.mcp_url}/context/documents",
                    json=resource.dict(),
                    timeout=10
                )
                if response.status_code in (200, 201):
                    logger.debug(f"Resource saved to MCP: {resource.id}")
                    return True
                else:
                    logger.warning(f"Failed to save resource to MCP: {response.status_code}")
                    return False
            except Exception as e:
                logger.error(f"Error saving resource to MCP: {str(e)}")
                return False
        
        return True  # Successfully saved to local cache
    
    def create_task_plan(self, task_description: str) -> List[str]:
        """Create a step-by-step plan for completing a task"""
        prompt = f"""
        Create a step-by-step plan to accomplish the following task:
        
        {task_description}
        
        Break down the task into clear, executable steps. Each step should be concise and actionable.
        Format the output as a numbered list of steps.
        """
        
        try:
            response = self.generate(prompt, task_type=TaskType.PLANNING)
            # The generate function NOW returns a generator. We need the full response.
            full_response = "".join(list(response))

            # Parse the response to extract steps
            steps = []
            # Process the accumulated full_response string
            for line in full_response.split("\n"):
                line = line.strip()
                # Match numbered items with format "1. Step description"
                match = re.match(r"^\s*\d+[\.\)]\s*(.*)", line)
                if match:
                    steps.append(match.group(1).strip())
                elif line and not line.lower().startswith("here is a plan") and not line.lower().startswith("plan:"):
                    # Add lines that aren't just headers
                    steps.append(line)
            
            if not steps:
                # Fallback if parsing fails
                steps = [s.strip() for s in full_response.split("\n") if s.strip()]
            
            self.context.task_plan = steps
            return steps
            
        except Exception as e:
            logger.error(f"Error creating task plan: {str(e)}")
            return ["Error: Could not create task plan"]
    
    def generate_code(self, code_description: str, language: str = "python") -> str:
        """Generate code based on a description"""
        prompt = f"""
        Generate {language} code for the following:
        
        {code_description}
        
        Requirements:
        - Code should be well-structured and documented
        - Include error handling
        - Follow best practices for {language}
        - Be efficient and readable
        
        Please provide only the code, without explanations before or after.
        """
        
        try:
            return self.generate(prompt, task_type=TaskType.CODE_GENERATION)
        except Exception as e:
            logger.error(f"Error generating code: {str(e)}")
            return f"# Error generating code: {str(e)}"
    
    def evaluate_code(self, code: str, language: str = "python") -> Dict[str, Any]:
        """Evaluate generated code for quality and correctness"""
        prompt = f"""
        Evaluate the following {language} code:
        
        ```{language}
        {code}
        ```
        
        Provide an assessment with the following:
        1. Overall quality (1-10)
        2. Potential bugs or issues
        3. Suggestions for improvement
        4. Security concerns (if any)
        
        Format your response as JSON with keys: quality_score, issues, improvements, security_concerns
        """
        
        try:
            response = self.generate(prompt)
            # Try to parse JSON response
            try:
                # Extract JSON if it's embedded in text
                json_match = re.search(r"\{[\s\S]*\}", response)
                if json_match:
                    json_str = json_match.group(0)
                    result = json.loads(json_str)
                    return result
                else:
                    # Fallback to manual parsing
                    return {
                        "quality_score": 0,
                        "issues": ["Could not parse evaluation"],
                        "improvements": [],
                        "security_concerns": []
                    }
            except json.JSONDecodeError:
                # Structured fallback if JSON parsing fails
                return {
                    "quality_score": 0,
                    "issues": ["Failed to parse evaluation result"],
                    "improvements": [],
                    "security_concerns": ["Unknown - parsing failed"]
                }
                
        except Exception as e:
            logger.error(f"Error evaluating code: {str(e)}")
            return {
                "quality_score": 0,
                "issues": [f"Error: {str(e)}"],
                "improvements": [],
                "security_concerns": []
            }
    
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a registered tool"""
        if tool_name not in self.context.tools:
            return {"error": f"Tool not found: {tool_name}"}
        
        tool = self.context.tools[tool_name]
        
        try:
            # Check for missing required parameters
            for param_name, param_desc in tool.parameters.items():
                if param_name not in parameters:
                    return {"error": f"Missing required parameter: {param_name}"}
            
            # Handle built-in tools
            if tool_name == "file_read":
                return self._tool_file_read(parameters["path"])
            elif tool_name == "file_write":
                return self._tool_file_write(parameters["path"], parameters["content"])
            elif tool_name == "execute_command":
                return self._tool_execute_command(parameters["command"])
            elif tool_name == "web_search":
                return {"error": "Web search not implemented yet"}
            
            # Custom tool with function
            if tool.function:
                return tool.function(**parameters)
            
            return {"error": "Tool has no implementation"}
            
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {str(e)}")
            return {
                "error": f"Tool execution failed: {str(e)}",
                "details": traceback.format_exc()
            }
    
    def _tool_file_read(self, file_path: str) -> Dict[str, Any]:
        """Read a file from the workspace"""
        try:
            # Security: Ensure path is within workspace
            full_path = os.path.abspath(os.path.join(self.context.workspace_path or "", file_path))
            if not full_path.startswith(os.path.abspath(self.context.workspace_path or "")):
                return {"error": "File path is outside workspace"}
            
            if not os.path.exists(full_path):
                return {"error": f"File not found: {file_path}"}
            
            with open(full_path, "r", encoding="utf-8") as file:
                content = file.read()
            
            return {
                "success": True,
                "content": content,
                "path": file_path
            }
            
        except Exception as e:
            return {"error": f"Error reading file: {str(e)}"}
    
    def _tool_file_write(self, file_path: str, content: str) -> Dict[str, Any]:
        """Write content to a file in the workspace"""
        try:
            # Security: Ensure path is within workspace
            full_path = os.path.abspath(os.path.join(self.context.workspace_path or "", file_path))
            if not full_path.startswith(os.path.abspath(self.context.workspace_path or "")):
                return {"error": "File path is outside workspace"}
            
            # Create directories if they don't exist
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            with open(full_path, "w", encoding="utf-8") as file:
                file.write(content)
            
            return {
                "success": True,
                "path": file_path,
                "bytes_written": len(content)
            }
            
        except Exception as e:
            return {"error": f"Error writing file: {str(e)}"}
    
    def _tool_execute_command(self, command: str) -> Dict[str, Any]:
        """Execute a shell command"""
        try:
            import subprocess
            
            # Security: Basic check for dangerous commands
            dangerous_patterns = [
                r"rm\s+-rf\s+/", 
                r"mkfs", 
                r":(){:|\:&};:"  # Fork bomb
            ]
            
            for pattern in dangerous_patterns:
                if re.search(pattern, command):
                    return {"error": "Potentially dangerous command rejected"}
            
            # Execute command
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate(timeout=30)
            
            return {
                "success": process.returncode == 0,
                "return_code": process.returncode,
                "stdout": stdout,
                "stderr": stderr
            }
            
        except subprocess.TimeoutExpired:
            return {"error": "Command execution timed out"}
        except Exception as e:
            return {"error": f"Error executing command: {str(e)}"}
    
    def run_conversation(self):
        """Run an interactive conversation with the agent"""
        print(f"{colorama.Fore.GREEN}🤖 Agent initialized with {self.model}{colorama.Style.RESET_ALL}")
        print("Type 'exit' or 'quit' to end the conversation.")
        print("Type 'help' for available commands.")
        
        if self.mcp_enabled:
            print("MCP integration enabled. Attempting to fetch context...")
            context = self.get_context()
            if context:
                print(f"{colorama.Fore.GREEN}✅ MCP context loaded successfully{colorama.Style.RESET_ALL}")
            else:
                print(f"{colorama.Fore.YELLOW}⚠️ No MCP context available{colorama.Style.RESET_ALL}")
        
        while True:
            try:
                user_input = input(f"\n{colorama.Fore.CYAN}👤 -> {colorama.Style.RESET_ALL}")
                if user_input.lower() in ["exit", "quit"]:
                    break
                
                # Handle special commands
                if user_input.lower() == "help":
                    self._show_help()
                    continue
                elif user_input.lower().startswith("!plan "):
                    # Create a task plan
                    task = user_input[6:].strip()
                    print(f"{colorama.Fore.YELLOW}Creating plan for: {task}{colorama.Style.RESET_ALL}")
                    steps = self.create_task_plan(task)
                    print(f"\n{colorama.Fore.GREEN}📋 Task Plan:{colorama.Style.RESET_ALL}")
                    for i, step in enumerate(steps, 1):
                        print(f"{i}. {step}")
                    continue
                elif user_input.lower().startswith("!code "):
                    # Handle !code command
                    parts = user_input.split(" ", 1)
                    if len(parts) < 2 or not parts[1].strip():
                        print(colorama.Fore.YELLOW + "Usage: !code <description>" + colorama.Style.RESET_ALL)
                        continue
                    
                    code_description = parts[1].strip()
                    # Optional language specification: !code python: <desc>
                    language = "python" # Default
                    if ":" in code_description:
                         lang_part, desc_part = code_description.split(":", 1)
                         # Basic check if lang_part looks like a language identifier
                         if len(lang_part) < 15 and not ' ' in lang_part.strip(): 
                              language = lang_part.strip()
                              code_description = desc_part.strip()
                    
                    print(colorama.Fore.YELLOW + f"Generating code for: {code_description} ({language})" + colorama.Style.RESET_ALL)
                    code_prompt = f"Generate {language} code for the following description: {code_description}"
                    
                    # --- FIX: Consume the generator --- 
                    generated_code_generator = self.generate(prompt=code_prompt, task_type=TaskType.CODE_GENERATION)
                    generated_code_parts = []
                    print(colorama.Fore.CYAN + "💻 Generated Code:")
                    print(f"```{language}")
                    try:
                        for chunk in generated_code_generator:
                             print(chunk, end='', flush=True) # Print chunk as it arrives
                             generated_code_parts.append(chunk)
                        print() # Print newline after stream ends
                    except Exception as e:
                        print(f"\nError during code generation stream: {e}")
                    
                    full_generated_code = "".join(generated_code_parts)
                    print("```" + colorama.Style.RESET_ALL)
                    # --- End Fix --- 

                    # Add generated code to context or handle as needed
                    # self.context.resources['last_generated_code'] = MCPResource(id="last_gen_code", content=full_generated_code, metadata={'language': language})

                    continue
                elif user_input.lower().startswith("!tool "):
                    # Execute a tool
                    tool_input = user_input[6:].strip()
                    try:
                        # Parse as "tool_name param1=value1 param2=value2"
                        parts = tool_input.split()
                        tool_name = parts[0]
                        params = {}
                        
                        for param in parts[1:]:
                            if "=" in param:
                                key, value = param.split("=", 1)
                                params[key] = value
                        
                        print(f"{colorama.Fore.YELLOW}Executing tool: {tool_name}{colorama.Style.RESET_ALL}")
                        result = self.execute_tool(tool_name, params)
                        
                        print(f"\n{colorama.Fore.GREEN}🔧 Tool Result:{colorama.Style.RESET_ALL}")
                        print(json.dumps(result, indent=2))
                    except Exception as e:
                        print(f"{colorama.Fore.RED}Error parsing tool command: {str(e)}{colorama.Style.RESET_ALL}")
                    continue
                
                # Add to conversation history
                self.context.conversation_history.append({
                    "role": "user",
                    "content": user_input
                })
                
                # Augment with MCP context if available
                prompt = user_input
                if self.mcp_enabled:
                    context = self.get_context()
                    if context:
                        # Format conversation history for context
                        history_str = "\n".join([
                            f"{msg['role']}: {msg['content']}" 
                            for msg in self.context.conversation_history[-5:]  # Last 5 messages
                        ])
                        
                        prompt = f"""
                        [Context]
                        {json.dumps(context, indent=2)}
                        
                        [Conversation History]
                        {history_str}
                        
                        [Current User Query]
                        {user_input}
                        """
                
                print(f"\n{colorama.Fore.GREEN}🤖 Agent: {colorama.Style.RESET_ALL}", end="", flush=True)
                
                # Removed tqdm progress bar
                # Process the streaming response
                full_response = ""
                for chunk in self.generate(prompt):
                    print(chunk, end="", flush=True) # Print each chunk as it arrives
                    full_response += chunk
                print() # Add a newline after the stream finishes

                # Add full response to conversation history
                self.context.conversation_history.append({
                    "role": "assistant",
                    "content": full_response # Store accumulated response
                })
                
                # Update MCP with conversation if enabled
                if self.mcp_enabled:
                    try:
                        requests.post(
                            f"{self.mcp_url}/context/conversation",
                            json={
                                "role": "assistant",
                                "content": full_response, # Send accumulated response
                                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                            }
                        )
                    except Exception as e:
                        logger.debug(f"Failed to update MCP conversation: {str(e)}")
                
            except KeyboardInterrupt:
                print(f"\n{colorama.Fore.YELLOW}Exiting...{colorama.Style.RESET_ALL}")
                break
            except Exception as e:
                print(f"\n{colorama.Fore.RED}Error: {str(e)}{colorama.Style.RESET_ALL}")
                logger.error(f"Error in conversation loop: {str(e)}")
                logger.debug(traceback.format_exc())
    
    def _show_help(self):
        """Show help information"""
        help_text = f"""
{colorama.Fore.GREEN}Available Commands:{colorama.Style.RESET_ALL}
  help               - Show this help message
  exit, quit         - Exit the agent
  !plan <task>       - Create a step-by-step plan for a task
  !code <desc>       - Generate code based on description
  !code <lang>: <desc> - Generate code in specified language
  !tool <name> <params> - Execute a registered tool

{colorama.Fore.GREEN}Available Tools:{colorama.Style.RESET_ALL}
"""
        for name, tool in self.context.tools.items():
            help_text += f"  {name} - {tool.description}\n"
            for param_name, param_desc in tool.parameters.items():
                help_text += f"    {param_name}: {param_desc}\n"
        
        print(help_text)


def main():
    parser = argparse.ArgumentParser(description="Matrix-inspired Agent with Ollama and MCP integration")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model to use (default: {DEFAULT_MODEL})")
    parser.add_argument("--no-mcp", action="store_true", help="Disable MCP integration")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--workspace", help="Set the workspace path for file operations")
    parser.add_argument("--no-optimize", action="store_true", help="Disable hardware optimization")
    
    args = parser.parse_args()
    
    agent = OllamaAgent(
        model=args.model, 
        mcp_enabled=not args.no_mcp,
        optimize_for_hardware=not args.no_optimize,
        workspace_path=args.workspace,
        debug=args.debug
    )
    agent.run_conversation()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{colorama.Fore.YELLOW}Agent terminated by user{colorama.Style.RESET_ALL}")
    except Exception as e:
        print(f"\n{colorama.Fore.RED}Unhandled error: {str(e)}{colorama.Style.RESET_ALL}")
        traceback.print_exc() 