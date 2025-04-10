# System Patterns

## System Architecture

The BaseAgent system consists of several main components:

1. **Ollama** - Local LLM runtime service
2. **Main MCP Server** - Core context management service
3. **Specialized MCP Servers** - Purpose-specific services
   - **Code Analysis MCP Server** - For code analysis and formatting
   - **Test Runner MCP Server** - For running and analyzing tests
4. **Agent** - Client application that interacts with Ollama and MCP servers
   - **Base Agent** - Core agent implementation
   - **Enhanced Agent** - Extended agent with specialized MCP capabilities
5. **Integration Module** - Connects and manages interactions with all MCP servers
6. **Plugins** - Extensions that connect the agent to specialized MCP servers

```
┌───────────┐     ┌───────────┐     ┌───────────┐
│   Agent   │◄────┤   Ollama  │     │ User/App  │
│           │     │           │     │           │
│  (Python) │────►│  (LLMs)   │     │           │
└─────┬─────┘     └───────────┘     └─────┬─────┘
      │                                   │
      │                                   │
      │           ┌───────────┐           │
      └──────────►│Integration│◄──────────┘
                  │  Module   │
                  └─────┬─────┘
                        │
                ┌───────┴───────┐
                │               │
        ┌───────▼─────┐ ┌───────▼─────┐ ┌───────▼─────┐
        │    Main     │ │Code Analysis│ │ Test Runner │
        │  MCP Server │ │ MCP Server  │ │ MCP Server  │
        └─────────────┘ └─────────────┘ └─────────────┘
```

## Key Technical Decisions

1. **RESTful API for MCP** - Using HTTP/JSON for simplicity and compatibility
2. **In-Memory Context Storage** - Starting with in-memory storage for simplicity
3. **Single-File Agent Design** - Making agents portable and easy to deploy
4. **Environment Variables for Configuration** - Using env vars for flexibility
5. **Specialized MCP Servers** - Creating purpose-specific servers for better separation of concerns
6. **Plugin Architecture** - Using plugins to extend agent capabilities
7. **Token Budget Management** - Managing output size for optimal LLM consumption
8. **Inheritance-based Extension** - Enhanced agent extends base agent functionality
9. **Unified Integration Module** - Central module manages all MCP server connections
10. **Server Auto-Discovery** - Integration module automatically locates and connects to services

## Design Patterns in Use

1. **Client-Server Pattern** - For MCP and Ollama communication
2. **Repository Pattern** - For context storage
3. **Dependency Injection** - For flexible configuration
4. **Command Pattern** - For agent actions
5. **Plugin Pattern** - For extending agent functionality
6. **Adapter Pattern** - For integrating different test frameworks
7. **Factory Pattern** - For creating appropriate handlers based on input
8. **Facade Pattern** - Integration module provides a simple interface to complex systems
9. **Proxy Pattern** - Enhanced agent uses a proxy to communicate with MCP servers
10. **Strategy Pattern** - Different strategies for test execution and code analysis

## Component Relationships

### Main MCP Server Components

```
┌─────────────────────────────────────────┐
│              Main MCP Server            │
│                                         │
│  ┌─────────┐   ┌─────────┐  ┌────────┐  │
│  │ API     │   │Context  │  │Document│  │
│  │Endpoints│──►│Store    │◄─┤Manager │  │
│  └─────────┘   └─────────┘  └────────┘  │
│       │                          │      │
│       └──────────────────────────┘      │
└─────────────────────────────────────────┘
```

### Code Analysis MCP Server Components

```
┌─────────────────────────────────────────┐
│        Code Analysis MCP Server         │
│                                         │
│  ┌─────────┐   ┌─────────┐  ┌────────┐  │
│  │ API     │   │ Code    │  │ Ruff   │  │
│  │Endpoints│──►│Analyzer │◄─┤Integration│
│  └─────────┘   └─────────┘  └────────┘  │
│       │                          │      │
│       └──────────────────────────┘      │
└─────────────────────────────────────────┘
```

### Test Runner MCP Server Components

```
┌─────────────────────────────────────────┐
│          Test Runner MCP Server         │
│                                         │
│  ┌─────────┐   ┌─────────┐  ┌────────┐  │
│  │ API     │   │ Test    │  │Docker  │  │
│  │Endpoints│──►│Executor │◄─┤Integration│
│  └─────────┘   └─────────┘  └────────┘  │
│       │            │            │       │
│       │            ▼            │       │
│       │     ┌─────────────┐    │       │
│       │     │Test Result  │    │       │
│       │     │Processor    │◄───┘       │
│       │     └─────────────┘            │
│       │            │                   │
│       └────────────┘                   │
└─────────────────────────────────────────┘
```

### Integration Module Components

```
┌─────────────────────────────────────────┐
│          Integration Module             │
│                                         │
│  ┌─────────┐   ┌─────────┐  ┌────────┐  │
│  │ Service │   │ Tool    │  │ Error  │  │
│  │Discovery│──►│Registry │◄─┤Handling│  │
│  └─────────┘   └─────────┘  └────────┘  │
│       │             │           │       │
│       └─────────────┼───────────┘       │
│                     ▼                   │
│              ┌────────────┐             │
│              │ Server     │             │
│              │ Management │             │
│              └────────────┘             │
└─────────────────────────────────────────┘
```

### Enhanced Agent Components

```
┌─────────────────────────────────────────┐
│           Enhanced Agent                │
│                                         │
│  ┌─────────┐   ┌─────────┐  ┌────────┐  │
│  │ Base    │   │ Code    │  │ Test   │  │
│  │ Agent   │──►│Analysis │  │Runner  │  │
│  └─────────┘   └─────────┘  └────────┘  │
│       │             │           │       │
│       └─────────────┼───────────┘       │
│                     ▼                   │
│              ┌────────────┐             │
│              │Command     │             │
│              │Interpreter │             │
│              └────────────┘             │
│                     │                   │
│                     ▼                   │
│              ┌────────────┐             │
│              │Integration │             │
│              │ Module     │             │
│              └────────────┘             │
└─────────────────────────────────────────┘
```

## Data Flow

1. **User Input → Enhanced Agent**: User provides input to the agent
2. **Command Interpreter → Specialized Tools**: Special commands (/test, /analyze) are processed
3. **Enhanced Agent → Integration Module**: Agent uses the integration module to communicate with MCP servers
4. **Integration Module → MCP Servers**: Integration module routes requests to appropriate servers
5. **MCP Servers → Integration Module**: Servers return results to the integration module
6. **Integration Module → Enhanced Agent**: Integration module returns processed results to the agent
7. **Enhanced Agent → Ollama**: For regular questions, agent sends prompt to Ollama
8. **Ollama → Enhanced Agent**: Ollama returns the LLM response
9. **Enhanced Agent → User**: Agent presents the processed results to the user

## Error Handling Strategy

1. **Graceful Degradation**: If MCP fails, continue with reduced functionality
2. **Retry Logic**: For transient failures in LLM communication
3. **Informative Errors**: Clear error messages for debugging
4. **Fallback Options**: Alternative paths when primary components fail
5. **Timeout Management**: Handle long-running operations like tests appropriately
6. **Token Budget Constraints**: Manage output size for optimal LLM consumption
7. **Service Health Checks**: Integration module checks server health before operations
8. **Automatic Recovery**: Attempt to restart failed services
9. **Dependency Validation**: Check for required dependencies before operations 