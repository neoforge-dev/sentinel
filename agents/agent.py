#!/usr/bin/env python3
"""
Basic UV single-file agent for Ollama with MCP integration
"""
import argparse
import sys
import os
from typing import Dict, Any, Optional
import json
import requests


class OllamaAgent:
    """A simple agent that communicates with Ollama and integrates with MCP"""
    
    def __init__(self, model: str = "mistral:7b", mcp_enabled: bool = True):
        self.model = model
        self.mcp_enabled = mcp_enabled
        self.ollama_url = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self.mcp_url = os.environ.get("MCP_SERVER_URL", "http://localhost:8080")
        
    def generate(self, prompt: str) -> str:
        """Generate a response using Ollama"""
        response = requests.post(
            f"{self.ollama_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False
            }
        )
        
        if response.status_code != 200:
            raise Exception(f"Ollama API error: {response.text}")
            
        return response.json().get("response", "")
    
    def get_context(self) -> Optional[Dict[str, Any]]:
        """Get context from MCP server if enabled"""
        if not self.mcp_enabled:
            return None
            
        try:
            response = requests.get(f"{self.mcp_url}/context")
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Warning: Could not fetch MCP context. Status: {response.status_code}")
                return None
        except Exception as e:
            print(f"Warning: MCP service unavailable: {e}")
            return None
    
    def run_conversation(self):
        """Run an interactive conversation with the agent"""
        print(f"🤖 BaseAgent using {self.model}")
        print("Type 'exit' or 'quit' to end the conversation.")
        
        if self.mcp_enabled:
            print("MCP integration enabled. Attempting to fetch context...")
            context = self.get_context()
            if context:
                print("✅ MCP context loaded successfully")
            else:
                print("⚠️ No MCP context available")
        
        while True:
            try:
                user_input = input("\n👤 You: ")
                if user_input.lower() in ["exit", "quit"]:
                    break
                    
                # Augment with MCP context if available
                prompt = user_input
                if self.mcp_enabled:
                    context = self.get_context()
                    if context:
                        prompt = f"[Context] {json.dumps(context)}\n\n[User Query] {user_input}"
                
                print("\n🤖 Agent: ", end="", flush=True)
                response = self.generate(prompt)
                print(response)
                
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"\nError: {e}")


def main():
    parser = argparse.ArgumentParser(description="BaseAgent - Ollama with MCP integration")
    parser.add_argument("--model", default="mistral:7b", help="Model to use (default: mistral:7b)")
    parser.add_argument("--no-mcp", action="store_true", help="Disable MCP integration")
    
    args = parser.parse_args()
    
    agent = OllamaAgent(model=args.model, mcp_enabled=not args.no_mcp)
    agent.run_conversation()


if __name__ == "__main__":
    main() 