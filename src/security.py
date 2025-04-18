import os
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
import sys

# Define the header name for the API key
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# Load the expected API key from environment variable
# Provide a default for local development if not set, but log a warning.
EXPECTED_API_KEY = os.environ.get("MCP_API_KEY")
if not EXPECTED_API_KEY:
    EXPECTED_API_KEY = "dev_secret_key" # Replace with a more secure default or raise error
    print("WARNING: MCP_API_KEY environment variable not set. Using default insecure key for development.", file=sys.stderr)

async def verify_api_key(api_key_header: str = Security(API_KEY_HEADER)):
    """Dependency function to verify the API key in the X-API-Key header."""
    if not api_key_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key in X-API-Key header",
        )
    if api_key_header != EXPECTED_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key",
        )
    # If the key is valid, the function returns None implicitly, allowing access
    return api_key_header # Optionally return the key if needed elsewhere 