import pytest
import os
import asyncio

# Adjust the path to import from the 'src' directory added to pythonpath
from storage.database import get_db_manager, DB_PATH

@pytest.fixture(scope="session", autouse=True)
def initialize_test_database():
    """Fixture to ensure a clean database schema for the test session."""
    # Delete existing DB file before session
    if os.path.exists(DB_PATH):
        print(f"\nRemoving existing test database: {DB_PATH}")
        try:
            os.remove(DB_PATH)
        except OSError as e:
            print(f"Error removing database file: {e}. Tests might use old schema.")
            # Proceed anyway, maybe permissions issue or file lock

    # Initialize schema using the manager
    print("Initializing new test database schema...")
    db_manager = get_db_manager() # Get singleton instance
    
    # Run async initialization in a temporary event loop
    async def _init_db():
        await db_manager.connect() # This implicitly calls _create_tables if not initialized
        await db_manager.disconnect()
    
    try:
        asyncio.run(_init_db())
        print("Test database initialized.")
    except Exception as e:
        print(f"Error initializing test database: {e}")
        # Fail fast if DB init fails
        pytest.fail(f"Could not initialize test database: {e}")

    # Yield control to the test session
    yield

    # Optional: Cleanup after session if needed, though often test DBs are left
    # print("\nTest session finished.") 