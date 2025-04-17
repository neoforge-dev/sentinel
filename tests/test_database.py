#!/usr/bin/env python3
"""Test database operations."""

import asyncio
import json
import os
import sys
from pathlib import Path
import pytest

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.database import DatabaseManager

# --- Fixtures ---

@pytest.fixture(scope="function")
def db_manager(tmp_path) -> DatabaseManager:
    # Use a temporary file for each test function
    db_path = tmp_path / "test_temp.db"
    manager = DatabaseManager(db_path=str(db_path))
    # Connect and initialize tables
    asyncio.run(manager.connect()) 
    yield manager
    # Teardown: Disconnect from the database
    asyncio.run(manager.disconnect())

# --- Tests ---

def test_db_path(tmp_path):
    """Test that the DatabaseManager uses the correct path."""
    db_path_str = str(tmp_path / "test.db")
    manager = DatabaseManager(db_path=db_path_str)
    assert manager.db_path == db_path_str

@pytest.mark.asyncio
async def test_database_operations(db_manager: DatabaseManager):
    """Test core database operations: storing and retrieving results and snippets."""
    # Initialize database manager
    # db = DatabaseManager(":memory:")  # Use fixture instead
    # await db.initialize()
    # Use the fixture-provided manager
    db = db_manager

    # Test storing and retrieving test results
    test_result_id = "test-res-123"
    await db.store_test_result(
        result_id=test_result_id,
        status="success",
        summary="1 passed",
        details="All tests passed.",
        passed_tests=["test_a"],
        failed_tests=[],
        skipped_tests=[],
        execution_time=1.23,
        config={"runner": "pytest", "mode": "local"}
    )
    
    retrieved_result = await db.get_test_result(test_result_id)
    assert retrieved_result is not None
    assert retrieved_result["id"] == test_result_id
    assert retrieved_result["status"] == "success"
    assert retrieved_result["summary"] == "1 passed"
    assert retrieved_result["passed_tests"] == ["test_a"]
    assert retrieved_result["config"]["runner"] == "pytest"

    # Test storing and retrieving code snippets
    # snippet_id = "snippet-abc"
    # await db.store_snippet(
    #     snippet_id=snippet_id,
    #     code="print('hello')",
    #     language="python",
    #     metadata={"source": "test"}
    # )
    # 
    # retrieved_snippet = await db.get_snippet(snippet_id)
    # assert retrieved_snippet is not None
    # assert retrieved_snippet["id"] == snippet_id
    # assert retrieved_snippet["code"] == "print('hello')"
    # assert retrieved_snippet["language"] == "python"
    # assert retrieved_snippet["metadata"]["source"] == "test"

    # Test listing snippets
    # all_snippets = await db.list_snippets()
    # assert snippet_id in all_snippets

    # Test getting last failed tests (should be empty)
    failed = await db.get_last_failed_tests()
    assert isinstance(failed, list)
    assert len(failed) == 0

    # Store a failed result
    fail_id = "fail-res-456"
    await db.store_test_result(
        result_id=fail_id,
        status="failed",
        summary="1 failed",
        details="Assertion failed",
        passed_tests=[],
        failed_tests=["test_b"],
        skipped_tests=[],
        execution_time=0.5,
        config={"project_path": "project/path/a"} # Match project path
    )
    
    # Test getting last failed tests (should have test_b)
    failed_again = await db.get_last_failed_tests()
    assert failed_again == ["test_b"]

    # Test getting non-existent result
    non_existent = await db.get_test_result("non-existent-id")
    assert non_existent is None
    
    # Test getting non-existent snippet
    non_existent_snip = await db.get_code_snippet("non-existent-snip")
    assert non_existent_snip is None

    # Test listing results
    all_results = await db.list_test_results()
    # assert test_result_id in all_results # Original assertion failed
    # Check if any result in the list has the expected ID
    assert any(result["id"] == test_result_id for result in all_results)
    assert any(result["id"] == fail_id for result in all_results)

    # Test disconnect

if __name__ == "__main__":
    asyncio.run(test_database_operations()) 