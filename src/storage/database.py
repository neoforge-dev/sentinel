#!/usr/bin/env python3
"""
Database manager for MCP servers.

This module provides a centralized database connection manager for all MCP services,
handling connection pooling, table creation, and data storage/retrieval operations.

Dependencies:
- aiosqlite: For async SQLite database operations
- json: For serializing/deserializing complex data structures
- logging: For logging database operations
- os: For environment variable access and path operations
- typing: For type annotations
"""

import aiosqlite
import json
import logging
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union, AsyncGenerator
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp.database")

# Get project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Default database location
DEFAULT_DB_PATH = os.path.join(PROJECT_ROOT, "data", "mcp.db")
DB_PATH = os.environ.get("MCP_DB_PATH", DEFAULT_DB_PATH)

# Ensure the data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Singleton database manager instance (RETAINED, but not used for request dependency)
_db_manager = None


def get_db_manager() -> 'DatabaseManager':
    """Get the singleton database manager instance (for non-request scope use if needed)."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(DB_PATH)
    return _db_manager

# NEW: Request-scoped dependency
async def get_request_db_manager() -> AsyncGenerator['DatabaseManager', None]:
    """FastAPI dependency that provides a DB manager connected for a single request."""
    db = DatabaseManager(DB_PATH) # Create instance for this request
    try:
        await db.connect()
        yield db
    finally:
        await db.disconnect()


class DatabaseManager:
    """
    Manages database connections and operations for all MCP services.
    
    This class implements a singleton pattern and provides methods for:
    - Connecting to and disconnecting from the database
    - Creating necessary tables
    - Storing and retrieving test results
    - Storing and retrieving code snippets
    - Storing and retrieving code analysis results
    - Storing and retrieving code fix results
    """
    
    def __init__(self, db_path: str):
        """Initialize the database manager with the given database path."""
        self.db_path = db_path
        self.conn = None
        self.initialized = False
        logger.info(f"Database manager initialized with path: {db_path}")
    
    async def connect(self) -> None:
        """Connect to the database and create tables if necessary."""
        if self.conn is None:
            logger.info(f"Connecting to database at {self.db_path}")
            self.conn = await aiosqlite.connect(self.db_path)
            # Enable foreign keys and json1 extension
            await self.conn.execute("PRAGMA foreign_keys = ON")
            
            # Create tables if not already initialized
            if not self.initialized:
                await self._create_tables()
                self.initialized = True
    
    async def disconnect(self) -> None:
        """Disconnect from the database."""
        if self.conn:
            logger.info("Disconnecting from database")
            await self.conn.close()
            self.conn = None
    
    async def _create_tables(self) -> None:
        """Create database tables if they don't exist."""
        if not self.conn:
            await self.connect()
        
        create_statements = [
            """
            CREATE TABLE IF NOT EXISTS test_results (
                id TEXT PRIMARY KEY,
                project_path TEXT,
                test_path TEXT,
                runner TEXT,
                execution_mode TEXT,
                status TEXT,
                summary TEXT,
                details TEXT,
                passed_tests TEXT,
                failed_tests TEXT,
                skipped_tests TEXT,
                execution_time REAL,
                config TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS last_failed_tests (
                test_name TEXT,
                project_path TEXT,
                timestamp REAL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS code_snippets (
                id TEXT PRIMARY KEY,
                code TEXT,
                language TEXT,
                timestamp REAL,
                metadata TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS code_analysis (
                id TEXT PRIMARY KEY,
                code_id TEXT,
                timestamp REAL,
                issues TEXT,
                formatted_code TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS code_fixes (
                id TEXT PRIMARY KEY,
                original_code TEXT,
                language TEXT,
                fixed_code TEXT,
                issues_remaining TEXT,
                applied_fixes TEXT,
                timestamp REAL,
                original_code_id TEXT
            )
            """
        ]
        
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_test_results_project_path ON test_results(project_path)",
            "CREATE INDEX IF NOT EXISTS idx_test_results_status ON test_results(status)",
            "CREATE INDEX IF NOT EXISTS idx_last_failed_tests_timestamp ON last_failed_tests(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_last_failed_tests_project_path ON last_failed_tests(project_path)"
        ]
        
        # Check if project_path column exists in last_failed_tests table
        try:
            async with self.conn.execute("PRAGMA table_info(last_failed_tests)") as cursor:
                columns = await cursor.fetchall()
                has_project_path = any(column[1] == 'project_path' for column in columns)
                
                # Add project_path column if it doesn't exist
                if not has_project_path:
                    await self.conn.execute("ALTER TABLE last_failed_tests ADD COLUMN project_path TEXT")
                    logger.info("Added project_path column to last_failed_tests table")
        except Exception as e:
            logger.error(f"Error checking last_failed_tests schema: {e}")
        
        try:
            # Execute create statements
            for statement in create_statements:
                await self.conn.execute(statement)
            
            # Create indexes
            for index in indexes:
                await self.conn.execute(index)
                
            await self.conn.commit()
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
            raise
    
    # Test Results Methods
    
    async def store_test_result(
        self,
        result_id: str,
        status: str,
        summary: str,
        details: str,
        passed_tests: list,
        failed_tests: list,
        skipped_tests: list,
        execution_time: float,
        config: dict
    ) -> None:
        """
        Store a test execution result in the database.
        
        Args:
            result_id: Unique identifier for the result
            status: Status of the test run (success, failed, error)
            summary: Summary of the test run
            details: Detailed output of the test run
            passed_tests: List of tests that passed
            failed_tests: List of tests that failed
            skipped_tests: List of tests that were skipped
            execution_time: Time taken to execute the tests
            config: Configuration used for the test run
        """
        if not self.conn:
            await self.connect()
        
        # Convert lists to JSON strings
        passed_tests_json = json.dumps(passed_tests)
        failed_tests_json = json.dumps(failed_tests)
        skipped_tests_json = json.dumps(skipped_tests)
        config_json = json.dumps(config)
        
        # Insert test result
        await self.conn.execute(
            """
            INSERT INTO test_results (
                id, status, summary, details, 
                passed_tests, failed_tests, skipped_tests, 
                execution_time, config
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result_id, status, summary, details,
                passed_tests_json, failed_tests_json, skipped_tests_json,
                execution_time, config_json
            )
        )
        
        # Get project path from config for storing with failed tests
        project_path = None
        if isinstance(config, dict):
            project_path = config.get('project_path')
        
        # If tests failed, store them in the last_failed_tests table with project_path
        if status == "failed" and failed_tests:
            # Clear existing failed tests for this project if provided
            if project_path:
                await self.conn.execute(
                    "DELETE FROM last_failed_tests WHERE project_path = ?",
                    (project_path,)
                )
            
            # Insert new failed tests
            current_time = time.time()
            for test in failed_tests:
                await self.conn.execute(
                    "INSERT INTO last_failed_tests (test_name, project_path, timestamp) VALUES (?, ?, ?)",
                    (test, project_path, current_time)
                )
            logger.info(f"Stored {len(failed_tests)} failed tests for result {result_id}")
        
        # Clear failed tests if status is success and project_path is provided
        elif status == "success" and project_path:
            await self.conn.execute(
                "DELETE FROM last_failed_tests WHERE project_path = ?", 
                (project_path,)
            )
            logger.info(f"Clearing last_failed_tests for successful run {result_id}")
        
        await self.conn.commit()
        logger.info(f"Stored test result with ID: {result_id}")

    async def get_test_result(self, result_id: str) -> Optional[dict]:
        """Retrieve a test result by its ID."""
        if not self.conn:
            await self.connect()
        
        async with self.conn.execute(
            "SELECT * FROM test_results WHERE id = ?",
            (result_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                logger.warning(f"Test result not found: {result_id}")
                return None
            
            # Get column names from cursor description
            columns = [col[0] for col in cursor.description]
            result = dict(zip(columns, row))
            
            # Deserialize JSON fields
            try:
                result["passed_tests"] = json.loads(result.get("passed_tests", "[]"))
                result["failed_tests"] = json.loads(result.get("failed_tests", "[]"))
                result["skipped_tests"] = json.loads(result.get("skipped_tests", "[]"))
                config_data = json.loads(result.get("config", "{}"))
                result["config"] = config_data
            except json.JSONDecodeError as e:
                logger.error(f"Failed to deserialize JSON for result {result_id}: {e}")
                # Assign default empty dict if deserialization fails
                result["config"] = {}
                config_data = {}

            # Extract fields from config to match TestResult model
            result["project_path"] = config_data.get("project_path")
            result["test_path"] = config_data.get("test_path")
            result["runner"] = config_data.get("runner")
            result["execution_mode"] = config_data.get("mode") # Map 'mode' from config to 'execution_mode'

            # Convert created_at to datetime object if it's a string
            created_at_val = result.get("created_at")
            if isinstance(created_at_val, str):
                try:
                    # Attempt parsing common ISO formats
                    result["created_at"] = datetime.fromisoformat(created_at_val.replace("Z", "+00:00"))
                except ValueError:
                     try:
                         # Fallback for other potential formats (e.g., space separator)
                         result["created_at"] = datetime.strptime(created_at_val, "%Y-%m-%d %H:%M:%S.%f")
                     except ValueError:
                          logger.warning(f"Could not parse created_at timestamp: {created_at_val}")
                          # Keep original or set to None/default? Let Pydantic handle for now.
                          pass 
            elif isinstance(created_at_val, (int, float)):
                # Handle potential Unix timestamps
                result["created_at"] = datetime.fromtimestamp(created_at_val)
                
            # Remove the original config blob as it's not in TestResult model
            # result.pop("config", None) # Keep the config field for direct DB access tests

            logger.info(f"Retrieved and processed test result with ID: {result_id}")
            return result
    
    async def list_test_results(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List all test results, returning dictionaries containing all necessary fields for ResultData model."""
        if not self.conn:
            await self.connect()
        
        # Select all columns necessary to build ResultData
        query = """
            SELECT 
                id, project_path, test_path, runner, execution_mode, status, 
                summary, details, passed_tests, failed_tests, skipped_tests, 
                execution_time, created_at
            FROM test_results
            ORDER BY created_at DESC
            LIMIT ?
        """
        
        results = []
        try:
            async with self.conn.execute(query, (limit,)) as cursor:
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                for row in rows:
                    result_dict = dict(zip(columns, row))
                    # Deserialize JSON fields
                    result_dict['passed_tests'] = json.loads(result_dict.get('passed_tests', '[]'))
                    result_dict['failed_tests'] = json.loads(result_dict.get('failed_tests', '[]'))
                    result_dict['skipped_tests'] = json.loads(result_dict.get('skipped_tests', '[]'))
                    # Optionally parse config if needed later, though not directly in ResultData
                    # result_dict['config'] = json.loads(result_dict.get('config', '{}'))
                    # Convert timestamp string back to datetime object if needed (or handle in Pydantic)
                    # result_dict['created_at'] = datetime.fromisoformat(result_dict['created_at'])
                    results.append(result_dict)
        except Exception as e:
            logger.error(f"Error listing test results: {e}", exc_info=True)
            # Consider re-raising or returning empty list/error indicator
        
        return results
    
    async def get_last_failed_tests(self, project_path: Optional[str] = None) -> List[str]:
        """
        Get the list of tests that failed in the most recent run.
        
        Args:
            project_path: Optional path to filter test results by project

        Returns:
            A list of test names that failed
        """
        if not self.conn:
            await self.connect()
        
        failed_tests = []
        
        if project_path:
            # Filter by project path if provided
            async with self.conn.execute(
                "SELECT test_name FROM last_failed_tests WHERE project_path = ? ORDER BY timestamp DESC",
                (project_path,)
            ) as cursor:
                rows = await cursor.fetchall()
                failed_tests = [row[0] for row in rows]
        else:
            # Get all failed tests if no project path filter
            async with self.conn.execute(
                "SELECT test_name FROM last_failed_tests ORDER BY timestamp DESC"
            ) as cursor:
                rows = await cursor.fetchall()
                failed_tests = [row[0] for row in rows]
        
        return failed_tests
    
    # Code Snippets Methods
    
    async def store_code_snippet(self, snippet_id: str, code: str, language: str, 
                                metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Store a code snippet in the database.
        
        Args:
            snippet_id: Unique identifier for the snippet
            code: The code content
            language: The programming language of the code
            metadata: Optional metadata associated with the snippet
            
        Returns:
            The ID of the stored snippet
        """
        if not self.conn:
            await self.connect()
        
        await self.conn.execute(
            """
            INSERT INTO code_snippets (id, code, language, timestamp, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                snippet_id,
                code,
                language,
                time.time(),
                json.dumps(metadata) if metadata else None
            )
        )
        
        await self.conn.commit()
        logger.info(f"Stored code snippet with ID: {snippet_id}")
        
        return snippet_id
    
    async def get_code_snippet(self, snippet_id: str) -> Dict[str, Any]:
        """
        Retrieve a code snippet by its ID.
        
        Args:
            snippet_id: The ID of the snippet to retrieve
            
        Returns:
            A dictionary containing the snippet information
        """
        if not self.conn:
            await self.connect()
        
        async with self.conn.execute(
            "SELECT * FROM code_snippets WHERE id = ?", (snippet_id,)
        ) as cursor:
            result = await cursor.fetchone()
            
            if not result:
                return None
            
            column_names = [col[0] for col in cursor.description]
            result_dict = dict(zip(column_names, result))
            
            # Convert metadata back to dict if it exists, default to empty dict if NULL
            metadata_json = result_dict.get("metadata")
            if metadata_json:
                result_dict["metadata"] = json.loads(metadata_json)
            else:
                result_dict["metadata"] = {}
        
        return result_dict
    
    async def list_code_snippets(self, language: Optional[str] = None, 
                                limit: int = 10) -> List[Dict[str, Any]]:
        """
        List recent code snippets, optionally filtered by language.
        
        Args:
            language: Filter snippets by programming language
            limit: Maximum number of snippets to return (default: 10)
            
        Returns:
            A list of dictionaries containing snippet information
        """
        if not self.conn:
            await self.connect()
        
        results = []
        
        if language:
            query = """
            SELECT id, language, timestamp
            FROM code_snippets
            WHERE language = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """
            params = (language, limit)
        else:
            query = """
            SELECT id, language, timestamp
            FROM code_snippets
            ORDER BY timestamp DESC
            LIMIT ?
            """
            params = (limit,)
        
        async with self.conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            column_names = [col[0] for col in cursor.description]
            
            for row in rows:
                results.append(dict(zip(column_names, row)))
        
        return results
    
    # Code Analysis Methods
    
    async def store_code_analysis(self, analysis_id: str,
                                 issues: List[Dict[str, Any]], 
                                 formatted_code: Optional[str] = None,
                                 code_id: Optional[str] = None) -> str:
        """
        Store code analysis results in the database.
        
        Args:
            analysis_id: Unique identifier for the analysis
            code_id: Optional ID of the code snippet that was analyzed
            issues: List of issues found in the code
            formatted_code: The formatted version of the code (if available)
            
        Returns:
            The ID of the stored analysis
        """
        if not self.conn:
            await self.connect()
        
        await self.conn.execute(
            """
            INSERT INTO code_analysis (id, code_id, timestamp, issues, formatted_code)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                analysis_id,
                code_id,
                time.time(),
                json.dumps(issues) if issues else None,
                formatted_code
            )
        )
        
        await self.conn.commit()
        logger.info(f"Stored code analysis with ID: {analysis_id}")
        
        return analysis_id
    
    async def get_code_analysis(self, analysis_id: str) -> Dict[str, Any]:
        """
        Retrieve code analysis results by ID.
        
        Args:
            analysis_id: The ID of the analysis to retrieve
            
        Returns:
            A dictionary containing the analysis information
        """
        if not self.conn:
            await self.connect()
        
        async with self.conn.execute(
            "SELECT * FROM code_analysis WHERE id = ?", (analysis_id,)
        ) as cursor:
            result = await cursor.fetchone()
            
            if not result:
                return None
            
            column_names = [col[0] for col in cursor.description]
            result_dict = dict(zip(column_names, result))
            
            # Convert issues back to list if it exists
            if result_dict.get("issues"):
                result_dict["issues"] = json.loads(result_dict["issues"])
        
        return result_dict
    
    async def get_analysis_for_snippet(self, code_id: str) -> Dict[str, Any]:
        """
        Get the most recent analysis for a code snippet.
        
        Args:
            code_id: The ID of the code snippet
            
        Returns:
            A dictionary containing the analysis information
        """
        if not self.conn:
            await self.connect()
        
        async with self.conn.execute(
            """
            SELECT * FROM code_analysis
            WHERE code_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (code_id,)
        ) as cursor:
            result = await cursor.fetchone()
            
            if not result:
                return None
            
            column_names = [col[0] for col in cursor.description]
            result_dict = dict(zip(column_names, result))
            
            # Convert issues back to list if it exists
            if result_dict.get("issues"):
                result_dict["issues"] = json.loads(result_dict["issues"])
        
        return result_dict
    
    # Code Fix Methods
    
    async def store_code_fix(self, fix_id: str, original_code: str, language: str, 
                           fixed_code: str, issues_remaining: List[Dict[str, Any]],
                           applied_fixes: List[str], original_code_id: Optional[str] = None) -> str:
        """
        Store the results of a code fix attempt.
        
        Args:
            fix_id: Unique identifier for this fix attempt
            original_code: The original code before fixing
            language: The programming language
            fixed_code: The code after attempting fixes
            issues_remaining: List of issues not fixed (as JSON string)
            applied_fixes: List of fixes applied (as JSON string)
            original_code_id: Optional ID of the original code snippet if stored
        
        Returns:
            The ID of the stored fix attempt
        """
        if not self.conn:
            await self.connect()
            
        await self.conn.execute(
            """
            INSERT INTO code_fixes 
            (id, original_code_id, timestamp, language, original_code, fixed_code, issues_remaining, applied_fixes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fix_id,
                original_code_id,
                time.time(),
                language,
                original_code,
                fixed_code,
                json.dumps(issues_remaining),
                json.dumps(applied_fixes)
            )
        )
        
        await self.conn.commit()
        logger.info(f"Stored code fix attempt with ID: {fix_id}")
        return fix_id

    async def get_code_fix(self, fix_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a code fix result by its ID.

        Args:
            fix_id: The ID of the code fix attempt to retrieve.

        Returns:
            A dictionary containing the fix result, or None if not found.
        """
        if not self.conn:
            await self.connect()
        
        async with self.conn.execute(
            "SELECT * FROM code_fixes WHERE id = ?", (fix_id,)
        ) as cursor:
            result = await cursor.fetchone()
            if not result:
                return None
            
            column_names = [col[0] for col in cursor.description]
            result_dict = dict(zip(column_names, result))
            
            # Deserialize JSON fields
            if result_dict.get("issues_remaining"):
                result_dict["issues_remaining"] = json.loads(result_dict["issues_remaining"])
            if result_dict.get("applied_fixes"):
                result_dict["applied_fixes"] = json.loads(result_dict["applied_fixes"])
                
        return result_dict

    async def list_code_fixes(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        List recent code fix attempts.

        Args:
            limit: Maximum number of results to return (default: 10).

        Returns:
            A list of dictionaries containing basic fix attempt information.
        """
        if not self.conn:
            await self.connect()

        results = []
        async with self.conn.execute(
            """
            SELECT id, timestamp, language, original_code_id
            FROM code_fixes 
            ORDER BY timestamp DESC 
            LIMIT ?
            """,
            (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            column_names = [col[0] for col in cursor.description]
            for row in rows:
                results.append(dict(zip(column_names, row)))
        
        return results 