"""Tests for error classes."""

import pytest
from mcp_server.errors import MCPServerError, NetworkError, FileSystemError, ParsingError


def test_mcp_server_error_inheritance():
    """Test that all custom errors inherit from MCPServerError."""
    assert issubclass(NetworkError, MCPServerError)
    assert issubclass(FileSystemError, MCPServerError)
    assert issubclass(ParsingError, MCPServerError)


def test_network_error():
    """Test NetworkError can be raised and caught."""
    with pytest.raises(NetworkError) as exc_info:
        raise NetworkError("Connection failed")
    assert str(exc_info.value) == "Connection failed"


def test_filesystem_error():
    """Test FileSystemError can be raised and caught."""
    with pytest.raises(FileSystemError) as exc_info:
        raise FileSystemError("File not found")
    assert str(exc_info.value) == "File not found"


def test_parsing_error():
    """Test ParsingError can be raised and caught."""
    with pytest.raises(ParsingError) as exc_info:
        raise ParsingError("Invalid syntax")
    assert str(exc_info.value) == "Invalid syntax"


def test_error_chaining():
    """Test that errors can be chained properly."""
    original = ValueError("Original error")
    
    with pytest.raises(NetworkError) as exc_info:
        try:
            raise original
        except ValueError as e:
            raise NetworkError("Network issue") from e
    
    assert exc_info.value.__cause__ is original