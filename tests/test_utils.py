"""Tests for utility functions."""

from datetime import datetime, timezone
from dataclasses import dataclass
from typing import List

import pytest
from mcp_server.utils import to_serializable
from mcp_server.models import Dependency, PackageInfo


def test_to_serializable_basic_types():
    """Test serialization of basic Python types."""
    assert to_serializable("string") == "string"
    assert to_serializable(42) == 42
    assert to_serializable(3.14) == 3.14
    assert to_serializable(True) is True
    assert to_serializable(None) is None


def test_to_serializable_collections():
    """Test serialization of collections."""
    assert to_serializable([1, 2, 3]) == [1, 2, 3]
    assert to_serializable((1, 2, 3)) == [1, 2, 3]
    assert to_serializable({"a": 1, "b": 2}) == {"a": 1, "b": 2}


def test_to_serializable_nested_collections():
    """Test serialization of nested collections."""
    data = {"items": [1, 2, {"nested": True}]}
    expected = {"items": [1, 2, {"nested": True}]}
    assert to_serializable(data) == expected


def test_to_serializable_dataclass():
    """Test serialization of dataclass objects."""
    dep = Dependency(name="requests", version_spec=">=2.0", extras=["security"])
    result = to_serializable(dep)
    
    expected = {
        "name": "requests",
        "version_spec": ">=2.0", 
        "extras": ["security"],
        "source_file": "",
        "is_dev_dependency": False
    }
    assert result == expected


def test_to_serializable_nested_dataclass():
    """Test serialization of nested dataclass objects."""
    dep = Dependency(name="httpx", version_spec=">=0.27")
    pkg = PackageInfo(
        name="test-package",
        version="1.0.0",
        dependencies=[dep]
    )
    
    result = to_serializable(pkg)
    assert result["name"] == "test-package"
    assert result["version"] == "1.0.0"
    assert len(result["dependencies"]) == 1
    assert result["dependencies"][0]["name"] == "httpx"


def test_to_serializable_datetime():
    """Test serialization of datetime objects."""
    dt = datetime(2023, 12, 25, 10, 30, 45, tzinfo=timezone.utc)
    result = to_serializable(dt)
    assert result == "2023-12-25T10:30:45+00:00"


def test_to_serializable_datetime_without_timezone():
    """Test serialization of naive datetime objects."""
    dt = datetime(2023, 12, 25, 10, 30, 45)
    result = to_serializable(dt)
    assert result == "2023-12-25T10:30:45"


@dataclass
class CustomClass:
    value: int
    items: List[str]


def test_to_serializable_custom_dataclass():
    """Test serialization of custom dataclass."""
    obj = CustomClass(value=42, items=["a", "b", "c"])
    result = to_serializable(obj)
    
    expected = {"value": 42, "items": ["a", "b", "c"]}
    assert result == expected


def test_to_serializable_complex_structure():
    """Test serialization of complex nested structure."""
    data = {
        "packages": [
            Dependency(name="requests", version_spec=">=2.0"),
            Dependency(name="httpx", version_spec=">=0.27", is_dev_dependency=True)
        ],
        "metadata": {
            "created": datetime(2023, 1, 1, tzinfo=timezone.utc),
            "count": 2
        }
    }
    
    result = to_serializable(data)
    
    assert len(result["packages"]) == 2
    assert result["packages"][0]["name"] == "requests"
    assert result["packages"][1]["is_dev_dependency"] is True
    assert result["metadata"]["created"] == "2023-01-01T00:00:00+00:00"
    assert result["metadata"]["count"] == 2