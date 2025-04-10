# Project Brief

## Project: BaseAgent

BaseAgent is an integration of Ollama, UV, and MCP (Model Context Protocol) designed to enable powerful local LLM agents with robust context management.

## Core Requirements

1. Integrate Ollama for running local LLMs (DeepSeek-R1:32B and Mistral 7B)
2. Use UV for Python dependency management and support single-file agents
3. Implement MCP server for context management
4. Provide a simple API for agents to communicate with LLMs and access context

## Goals

- Enable developers to easily create and run local AI agents
- Provide context management capabilities via MCP
- Create a simple but powerful single-file agent architecture
- Make setup and usage straightforward with good documentation

## Scope

### In Scope

- Ollama integration for running local LLMs
- MCP server implementation for context management
- Single-file agent implementation
- Basic setup script and documentation

### Out of Scope

- Web UI for agent management
- Complex agent orchestration
- Training custom models
- Cloud deployment options

## Success Criteria

- Agents can successfully communicate with Ollama LLMs
- MCP server properly stores and serves context
- Users can easily set up and run the project
- Agents can access and utilize context from MCP server 