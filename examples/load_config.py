#!/usr/bin/env python3
"""
Example showing how to load configuration from a file
and use it with the agent
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from agents.agent import OllamaAgent, TaskType
except ImportError:
    print("Error: Could not import from agents.agent. Make sure you're running from the project root.")
    sys.exit(1)


def load_config() -> Dict[str, Any]:
    """
    Load configuration from the config/models.json file
    """
    config_path = Path(__file__).parent.parent / "config" / "models.json"
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return {
            "models": {},
            "task_types": {},
            "default_settings": {}
        }


def get_model_settings(config: Dict[str, Any], model_name: str) -> Dict[str, Any]:
    """
    Get settings for a specific model from the config
    """
    models = config.get("models", {})
    return models.get(model_name, {})


def get_task_settings(config: Dict[str, Any], task_type: str) -> Dict[str, Any]:
    """
    Get settings for a specific task type from the config
    """
    task_types = config.get("task_types", {})
    return task_types.get(task_type, {})


def recommend_model(config: Dict[str, Any], task_type: str) -> str:
    """
    Recommend a model for a specific task type
    """
    task_settings = get_task_settings(config, task_type)
    recommended_models = task_settings.get("recommended_models", [])
    
    if not recommended_models:
        return config.get("default_settings", {}).get("default_model", "mistral:7b")
    
    return recommended_models[0]  # Return the first recommended model


def main():
    # Load configuration
    config = load_config()
    
    # Print available models
    print("=== Available Models ===")
    for model_name, model_settings in config.get("models", {}).items():
        hw_req = model_settings.get("hardware_requirements", {})
        print(f"- {model_name}:")
        print(f"  - RAM: {hw_req.get('min_ram_gb', 'N/A')}GB minimum, {hw_req.get('recommended_ram_gb', 'N/A')}GB recommended")
        print(f"  - GPU Recommended: {'Yes' if hw_req.get('gpu_recommended', False) else 'No'}")
    
    # Print task types and recommended models
    print("\n=== Task Types ===")
    for task_name, task_settings in config.get("task_types", {}).items():
        print(f"- {task_name}:")
        print(f"  - Recommended models: {', '.join(task_settings.get('recommended_models', []))}")
    
    # Example: Initialize agent with config
    task_type = "code_generation"
    recommended_model = recommend_model(config, task_type)
    model_settings = get_model_settings(config, recommended_model)
    
    print(f"\n=== Initializing Agent for {task_type} task ===")
    print(f"- Recommended model: {recommended_model}")
    
    # Create agent with config
    agent = OllamaAgent(model=recommended_model)
    
    # Apply task-specific settings
    task_settings = get_task_settings(config, task_type)
    temp_adjustment = task_settings.get("temperature_adjustment", 0.0)
    
    # Example: Generate code with adjusted settings
    code_description = "Create a function that calculates the Fibonacci sequence up to n terms"
    
    print(f"\n=== Generating Code ===")
    print(f"Description: {code_description}")
    print(f"Using model: {recommended_model} with temperature adjustment: {temp_adjustment}")
    
    # In a real implementation, you would apply the settings to the agent
    # and then generate the code
    print("\nCode would be generated here using the agent with appropriate settings.")
    print("This is just a configuration example.")


if __name__ == "__main__":
    main() 