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
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp.database")

# Default database location
DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "../../data/mcp.db")
DB_PATH = os.environ.get("MCP_DB_PATH", DEFAULT_DB_PATH)

# Ensure the data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Singleton database manager instance
_db_manager = None


def get_db_manager() -> 'DatabaseManager':
    """Get the singleton database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(DB_PATH)
    return _db_manager


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
        """Create all necessary tables if they don't exist."""
        if not self.conn:
            await self.connect()
        
        logger.info("Creating database tables if they don't exist")
        
        # Test Results table
        await self.conn.execute("""
        CREATE TABLE IF NOT EXISTS test_results (
            id TEXT PRIMARY KEY,
            timestamp REAL NOT NULL,
            status TEXT NOT NULL,
            summary TEXT NOT NULL,
            execution_time REAL,
            project_path TEXT,
            test_path TEXT,
            runner TEXT,
            mode TEXT,
            max_failures INTEGER,
            run_last_failed BOOLEAN,
            timeout INTEGER,
            max_tokens INTEGER,
            docker_image TEXT,
            additional_args TEXT
        )
        """)
        
        # Test Details table
        await self.conn.execute("""
        CREATE TABLE IF NOT EXISTS test_details (
            id TEXT PRIMARY KEY,
            test_result_id TEXT NOT NULL,
            test_type TEXT NOT NULL,
            test_name TEXT NOT NULL,
            details TEXT,
            FOREIGN KEY (test_result_id) REFERENCES test_results(id) ON DELETE CASCADE
        )
        """)
        
        # Last Failed Tests table
        await self.conn.execute("""
        CREATE TABLE IF NOT EXISTS last_failed_tests (
            test_name TEXT PRIMARY KEY,
            timestamp REAL NOT NULL
        )
        """)
        
        # Code Snippets table
        await self.conn.execute("""
        CREATE TABLE IF NOT EXISTS code_snippets (
            id TEXT PRIMARY KEY,
            code TEXT NOT NULL,
            language TEXT NOT NULL,
            timestamp REAL NOT NULL,
            metadata TEXT
        )
        """)
        
        # Code Analysis table
        await self.conn.execute("""
        CREATE TABLE IF NOT EXISTS code_analysis (
            id TEXT PRIMARY KEY,
            code_id TEXT, -- Made optional, removed NOT NULL
            timestamp REAL NOT NULL,
            issues TEXT,
            formatted_code TEXT,
            FOREIGN KEY (code_id) REFERENCES code_snippets(id) ON DELETE CASCADE
        )
        """)
        
        # Code Fixes table
        await self.conn.execute("""
        CREATE TABLE IF NOT EXISTS code_fixes (
            id TEXT PRIMARY KEY,
            original_code_id TEXT, -- Can be NULL if not linked to a snippet
            timestamp REAL NOT NULL,
            language TEXT NOT NULL,
            original_code TEXT NOT NULL,
            fixed_code TEXT NOT NULL,
            issues_remaining TEXT, -- JSON list of remaining issues
            applied_fixes TEXT, -- JSON list of applied fixes
            FOREIGN KEY (original_code_id) REFERENCES code_snippets(id) ON DELETE SET NULL
        )
        """)
        
        await self.conn.commit()
        logger.info("Database tables created successfully")
    
    # Test Results Methods
    
    async def store_test_result(self, result_id: str, status: str, summary: str, 
                               details: str, passed_tests: List[str], 
                               failed_tests: List[Tuple[str, str]], 
                               skipped_tests: List[str], 
                               execution_time: float, config: Dict[str, Any]) -> None:
        """
        Store a test execution result in the database.
        
        Args:
            result_id: Unique identifier for the test result
            status: Status of the test run (success, failure, error)
            summary: Summary of the test execution
            details: Detailed output from the test execution
            passed_tests: List of tests that passed
            failed_tests: List of failed tests with their error messages
            skipped_tests: List of tests that were skipped
            execution_time: Time taken to execute the tests (in seconds)
            config: Configuration used for the test execution
        """
        if not self.conn:
            await self.connect()
        
        # Store the test result
        await self.conn.execute(
            """
            INSERT INTO test_results 
            (id, timestamp, status, summary, execution_time, project_path, test_path, 
            runner, mode, max_failures, run_last_failed, timeout, max_tokens, 
            docker_image, additional_args)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result_id,
                time.time(),
                status,
                summary,
                execution_time,
                config.get("project_path", ""),
                config.get("test_path", ""),
                config.get("runner", ""),
                config.get("mode", ""),
                config.get("max_failures", None),
                config.get("run_last_failed", False),
                config.get("timeout", None),
                config.get("max_tokens", None),
                config.get("docker_image", ""),
                json.dumps(config.get("additional_args", {}))
            )
        )
        
        # Store passed tests
        for test_name in passed_tests:
            await self.conn.execute(
                """
                INSERT INTO test_details (id, test_result_id, test_type, test_name)
                VALUES (?, ?, ?, ?)
                """,
                (f"{result_id}_{test_name}_passed", result_id, "passed", test_name)
            )
        
        # Store failed tests
        for test_name, error_msg in failed_tests:
            await self.conn.execute(
                """
                INSERT INTO test_details (id, test_result_id, test_type, test_name, details)
                VALUES (?, ?, ?, ?, ?)
                """,
                (f"{result_id}_{test_name}_failed", result_id, "failed", test_name, error_msg)
            )
            
            # Update last failed tests
            await self.conn.execute(
                """
                INSERT OR REPLACE INTO last_failed_tests (test_name, timestamp)
                VALUES (?, ?)
                """,
                (test_name, time.time())
            )
        
        # Store skipped tests
        for test_name in skipped_tests:
            await self.conn.execute(
                """
                INSERT INTO test_details (id, test_result_id, test_type, test_name)
                VALUES (?, ?, ?, ?)
                """,
                (f"{result_id}_{test_name}_skipped", result_id, "skipped", test_name)
            )
        
        await self.conn.commit()
        logger.info(f"Stored test result with ID: {result_id}")
    
    async def get_test_result(self, result_id: str) -> Dict[str, Any]:
        """
        Retrieve a test result by its ID.
        
        Args:
            result_id: The ID of the test result to retrieve
            
        Returns:
            A dictionary containing the test result information
        """
        if not self.conn:
            await self.connect()
        
        # Get the test result
        async with self.conn.execute(
            "SELECT * FROM test_results WHERE id = ?", (result_id,)
        ) as cursor:
            result = await cursor.fetchone()
            
            if not result:
                return None
            
            column_names = [col[0] for col in cursor.description]
            result_dict = dict(zip(column_names, result))
            
            # Convert additional_args back to dict if it exists
            if result_dict.get("additional_args"):
                result_dict["additional_args"] = json.loads(result_dict["additional_args"])
        
        # Get test details
        passed_tests = []
        failed_tests = []
        skipped_tests = []
        
        async with self.conn.execute(
            "SELECT test_type, test_name, details FROM test_details WHERE test_result_id = ?",
            (result_id,)
        ) as cursor:
            details = await cursor.fetchall()
            
            for test_type, test_name, error_msg in details:
                if test_type == "passed":
                    passed_tests.append(test_name)
                elif test_type == "failed":
                    failed_tests.append((test_name, error_msg))
                elif test_type == "skipped":
                    skipped_tests.append(test_name)
        
        # Combine everything into a complete result
        complete_result = {
            **result_dict,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "skipped_tests": skipped_tests
        }
        
        return complete_result
    
    async def list_test_results(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        List recent test results.
        
        Args:
            limit: Maximum number of results to return (default: 10)
            
        Returns:
            A list of dictionaries containing basic test result information
        """
        if not self.conn:
            await self.connect()
        
        results = []
        async with self.conn.execute(
            """
            SELECT id, timestamp, status, summary, execution_time 
            FROM test_results 
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
    
    async def get_last_failed_tests(self) -> List[str]:
        """
        Get the list of tests that failed in the most recent run.
        
        Returns:
            A list of test names that failed
        """
        if not self.conn:
            await self.connect()
        
        failed_tests = []
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