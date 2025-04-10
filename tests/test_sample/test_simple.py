#!/usr/bin/env python3
"""Simple test file for testing the MCP test server."""

import unittest


class SimpleTest(unittest.TestCase):
    """A simple test class with passing and failing tests."""

    def test_passing_test(self):
        """A test that always passes."""
        self.assertEqual(2 + 2, 4)
        self.assertTrue(True)
        self.assertFalse(False)

    def test_another_passing_test(self):
        """Another test that always passes."""
        self.assertEqual("hello world".split(), ["hello", "world"])
        self.assertIn("hello", "hello world")

    def test_failing_test(self):
        """A test that always fails."""
        self.assertEqual(2 + 2, 5)  # This will fail

    def test_error_test(self):
        """A test that raises an error."""
        raise ValueError("This test raises an error on purpose") 