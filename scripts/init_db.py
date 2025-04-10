#!/usr/bin/env python3
"""
Database initialization script

This script initializes the database for MCP servers and verifies that all required
dependencies are installed.

Usage:
    python scripts/init_db.py --db-url "sqlite:///./mcp_data.db"
"""

import os
import sys
import asyncio
import argparse
import importlib.util
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def check_dependency(package_name: str) -> bool:
    """Check if a Python package is installed"""
    return importlib.util.find_spec(package_name) is not None


def verify_dependencies():
    """Verify that all required dependencies are installed"""
    required_packages = [
        "sqlalchemy",
        "databases",
        "aiosqlite",  # For SQLite async support
        "uvicorn",
        "fastapi",
        "pydantic"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        if not check_dependency(package):
            missing_packages.append(package)
    
    if missing_packages:
        print("Error: Missing required packages:")
        for package in missing_packages:
            print(f"  - {package}")
        print("\nPlease install these packages with:")
        print(f"  pip install {' '.join(missing_packages)}")
        return False
    
    return True


async def init_database(db_url: str):
    """Initialize the database"""
    try:
        # Import here to avoid import errors if dependencies are missing
        from src.storage.database import initialize_db, get_db_manager
        
        print(f"Initializing database at: {db_url}")
        db_manager = get_db_manager(db_url)
        
        # Connect and create tables
        await db_manager.connect()
        print("Database connection successful.")
        
        # Verify tables were created
        tables = db_manager.engine.table_names()
        print(f"Created {len(tables)} tables:")
        for table in tables:
            print(f"  - {table}")
        
        # Disconnect
        await db_manager.disconnect()
        print("Database initialization complete.")
        
    except Exception as e:
        print(f"Error initializing database: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Initialize the MCP database")
    parser.add_argument("--db-url", default="sqlite:///./mcp_data.db", help="Database URL")
    args = parser.parse_args()
    
    if not verify_dependencies():
        sys.exit(1)
    
    if not await init_database(args.db_url):
        sys.exit(1)
    
    print("\nDatabase initialization successful!")
    print(f"Database URL: {args.db_url}")
    print("\nYou can now start the MCP servers with persistent storage.")


if __name__ == "__main__":
    asyncio.run(main()) 