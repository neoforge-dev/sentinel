# Active Context

## Current Focus

Building the initial project structure and implementing core components:
- MCP server implementation
- Basic agent implementation
- Setup script
- Documentation

## Recent Changes

1. Created the initial project structure
2. Implemented a simple MCP server using FastAPI
3. Created a basic agent that communicates with Ollama
4. Developed a setup script for easy installation
5. Updated documentation in README.md
6. Established memory-bank for project continuity

## Next Steps

1. **Test the MCP server** - Ensure it correctly stores and retrieves context
2. **Test the agent** - Verify it communicates with Ollama and the MCP server
3. **Enhance documentation** - Add more detailed examples and usage patterns
4. **Add more agent capabilities** - Implement file access, tool usage, etc.
5. **Implement proper error handling** - Improve robustness of the system

## Active Decisions

1. **API Design for MCP** - Using RESTful API with FastAPI for simplicity and flexibility
2. **Agent Architecture** - Single-file agents for portability and ease of use
3. **Context Storage** - Using in-memory storage initially, may add persistent storage later
4. **Default Models** - Using Mistral 7B as default, with option for DeepSeek R1
5. **UV for Dependencies** - Chosen for modern Python dependency management

## Current Considerations

1. Should we add a web UI for managing agents and contexts?
2. How to handle large context windows efficiently?
3. What additional metadata should be stored with context items?
4. How to implement authentication for the MCP server?
5. Should we support other LLM backends beyond Ollama? 