#!/usr/bin/env python3
"""
MCP (Model Context Protocol) Server
Provides context to agents from various sources
"""
import os
import json
import argparse
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from datetime import datetime

app = FastAPI(title="MCP Server", description="Model Context Protocol Server")

# In-memory context store (in production, use a database)
context_store: Dict[str, Any] = {
    "system": {
        "server_start_time": datetime.now().isoformat(),
        "version": "0.1.0"
    },
    "documents": [],
    "conversation": []
}


class Document(BaseModel):
    """Document Model for context"""
    id: str
    content: str
    metadata: Optional[Dict[str, Any]] = None


class Message(BaseModel):
    """Message Model for conversation history"""
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: Optional[str] = None


@app.get("/")
def read_root():
    """Root endpoint"""
    return {"message": "MCP Server is running", "status": "active"}


@app.get("/context")
def get_context():
    """Get the full context"""
    return context_store


@app.get("/context/system")
def get_system_context():
    """Get system context"""
    return context_store.get("system", {})


@app.post("/context/documents")
def add_document(document: Document):
    """Add a document to context"""
    if not isinstance(context_store.get("documents"), list):
        context_store["documents"] = []
        
    # Check if document with same ID exists
    for i, doc in enumerate(context_store["documents"]):
        if doc.get("id") == document.id:
            # Replace existing document
            context_store["documents"][i] = document.dict()
            return {"status": "updated", "document_id": document.id}
            
    # Add new document
    context_store["documents"].append(document.dict())
    return {"status": "added", "document_id": document.id}


@app.delete("/context/documents/{document_id}")
def delete_document(document_id: str):
    """Delete a document from context"""
    if not isinstance(context_store.get("documents"), list):
        raise HTTPException(status_code=404, detail="No documents found")
        
    original_length = len(context_store["documents"])
    context_store["documents"] = [
        doc for doc in context_store["documents"] 
        if doc.get("id") != document_id
    ]
    
    if len(context_store["documents"]) == original_length:
        raise HTTPException(status_code=404, detail=f"Document with ID {document_id} not found")
        
    return {"status": "deleted", "document_id": document_id}


@app.post("/context/conversation")
def add_message(message: Message):
    """Add a message to conversation history"""
    if not isinstance(context_store.get("conversation"), list):
        context_store["conversation"] = []
        
    # Add timestamp if not provided
    if not message.timestamp:
        message.timestamp = datetime.now().isoformat()
        
    context_store["conversation"].append(message.dict())
    return {"status": "added", "message_id": len(context_store["conversation"]) - 1}


@app.delete("/context/conversation")
def clear_conversation():
    """Clear conversation history"""
    context_store["conversation"] = []
    return {"status": "cleared"}


def main():
    parser = argparse.ArgumentParser(description="MCP Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind server to")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind server to")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    
    args = parser.parse_args()
    
    print(f"🚀 Starting MCP Server on {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="debug" if args.debug else "info")


if __name__ == "__main__":
    main() 