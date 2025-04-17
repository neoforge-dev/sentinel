# Project Brief: BaseAgent

## Purpose
Integrate **Ollama**, **UV**, and **MCP** (Model Context Protocol) to create context-aware local AI agents with a standardized build/test/deploy process.

## Core Requirements
- Use Ollama for local LLMs.
- Use UV for Python dependencies.
- Implement MCP Code (8081) & Test (8082) servers.
- Agent interacts with Ollama & MCPs.
- SQLite DB persistence for MCP servers.
- Standardized JSON communication layer.

## Goals
- Simplify local AI agent development.
- Provide extensible context via MCPs.
- Easy setup & use.
- Clear architectural boundaries.
- Support local & Docker test execution.

## Scope
- **In**: Ollama, MCP Servers (Code, Test), Agent+Plugins, DB, CI/CD, Basic UI, Docker tests, Integration tests.
- **Out**: Advanced orchestration, Model training, Complex UI, Prod deployment automation.

## Success Criteria
- Agent uses Ollama & MCPs.
- MCPs perform tasks (analyze, test, store data).
- CI/CD runs tests & builds images.
- Basic UI works.
- Setup via `uv pip install -r requirements.txt`.
- Tests pass locally & in Docker.
- Integration tests verify component interaction.

## Current Status
- Core functionality operational.
- MCP servers running on standard ports (8081, 8082).
- Local & Docker test modes working.
- Focus: Stabilizing tests, resolving warnings.
