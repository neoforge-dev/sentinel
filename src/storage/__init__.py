#!/usr/bin/env python3
"""
Storage package initialization.

Exposes key components like the DatabaseManager for easy access.
"""

from .database import DatabaseManager, get_db_manager

__all__ = ["DatabaseManager", "get_db_manager"] 