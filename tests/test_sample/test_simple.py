#!/usr/bin/env python3
"""Simple test file with passing and failing tests."""

import pytest

def test_passing():
    """A test that passes."""
    assert 2 + 2 == 4
    assert True is True
    assert False is False

def test_another_passing():
    """Another test that passes."""
    assert "hello world".split() == ["hello", "world"]
    assert "hello" in "hello world"

def test_failing():
    """A test that fails."""
    assert 2 + 2 == 5, "This test is designed to fail"

def test_error():
    """A test that raises an error."""
    raise ValueError("This test raises an error on purpose") 