# System Patterns

## System Architecture

The BaseAgent system consists of three main components:

1. **Ollama** - Local LLM runtime service
2. **MCP Server** - Context management service
3. **Agent** - Client application that interacts with Ollama and MCP

```
┌───────────┐     ┌───────────┐     ┌───────────┐
│   Agent   │◄────┤   Ollama  │     │ User/App  │
│           │     │           │     │           │
│  (Python) │────►│  (LLMs)   │     │           │
└─────┬─────┘     └───────────┘     └─────┬─────┘
      │                                   │
      │                                   │
      │                                   │
      │           ┌───────────┐           │
      └──────────►│    MCP    │◄──────────┘
                  │  Server   │
                  │           │
                  └───────────┘
```

## Key Technical Decisions

1. **RESTful API for MCP** - Using HTTP/JSON for simplicity and compatibility
2. **In-Memory Context Storage** - Starting with in-memory storage for simplicity
3. **Single-File Agent Design** - Making agents portable and easy to deploy
4. **Environment Variables for Configuration** - Using env vars for flexibility

## Design Patterns in Use

1. **Client-Server Pattern** - For MCP and Ollama communication
2. **Repository Pattern** - For context storage
3. **Dependency Injection** - For flexible configuration
4. **Command Pattern** - For agent actions

## Component Relationships

### MCP Server Components

```
┌─────────────────────────────────────────┐
│              MCP Server                 │
│                                         │
│  ┌─────────┐   ┌─────────┐  ┌────────┐  │
│  │ API     │   │Context  │  │Document│  │
│  │Endpoints│──►│Store    │◄─┤Manager │  │
│  └─────────┘   └─────────┘  └────────┘  │
│       │                          │      │
│       └──────────────────────────┘      │
└─────────────────────────────────────────┘
```

### Agent Components

```
┌─────────────────────────────────────────┐
│              Agent                      │
│                                         │
│  ┌─────────┐   ┌─────────┐  ┌────────┐  │
│  │ Ollama  │   │ MCP     │  │ CLI    │  │
│  │ Client  │   │ Client  │  │Interface│  │
│  └─────────┘   └─────────┘  └────────┘  │
│       │             │           │       │
│       └─────────────┼───────────┘       │
│                     ▼                   │
│              ┌────────────┐             │
│              │Conversation│             │
│              │  Manager   │             │
│              └────────────┘             │
└─────────────────────────────────────────┘
```

## Data Flow

1. **User Input → Agent**: User provides input to the agent
2. **Agent → MCP Server**: Agent fetches relevant context
3. **Agent → Ollama**: Agent sends prompt (with context) to Ollama
4. **Ollama → Agent**: Ollama returns the LLM response
5. **Agent → User**: Agent presents the response to the user
6. **Agent → MCP Server**: Agent updates conversation history

## Error Handling Strategy

1. **Graceful Degradation**: If MCP fails, continue with reduced functionality
2. **Retry Logic**: For transient failures in LLM communication
3. **Informative Errors**: Clear error messages for debugging
4. **Fallback Options**: Alternative paths when primary components fail 