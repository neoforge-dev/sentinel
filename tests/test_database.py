#!/usr/bin/env python3
"""Test database operations."""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.database import DatabaseManager

async def test_database_operations():
    """Test database operations."""
    # Initialize database manager
    db = DatabaseManager(":memory:")  # Use in-memory database for testing
    await db.connect()
    
    # Test data
    result_id = "test-123"
    test_data = {
        "result_id": result_id,
        "status": "success",
        "summary": "Test summary",
        "details": "Test details",
        "passed_tests": ["test1", "test2"],
        "failed_tests": [("test3", "AssertionError")],
        "skipped_tests": ["test4"],
        "execution_time": 1.23,
        "config": {
            "project_path": "/test/path",
            "test_path": "test_file.py",
            "runner": "pytest"
        }
    }
    
    try:
        # Store test result
        await db.store_test_result(
            result_id=test_data["result_id"],
            status=test_data["status"],
            summary=test_data["summary"],
            details=test_data["details"],
            passed_tests=test_data["passed_tests"],
            failed_tests=test_data["failed_tests"],
            skipped_tests=test_data["skipped_tests"],
            execution_time=test_data["execution_time"],
            config=test_data["config"]
        )
        print("✅ Test result stored successfully")
        
        # Retrieve test result
        result = await db.get_test_result(result_id)
        if result:
            print("✅ Test result retrieved successfully")
            print(f"Result: {json.dumps(result, indent=2)}")
        else:
            print("❌ Failed to retrieve test result")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(test_database_operations()) 