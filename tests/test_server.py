"""Tests for MCP server functionality."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
from mcp_server.server import (
    analyze_project_dependencies,
    get_package_metadata,
    search_packages,
    check_package_compatibility,
    get_latest_version,
    _analyzer,
    _pkg
)
from mcp_server.models import Dependency, PackageInfo, ProjectInfo, PackageSearchResult


class TestAnalyzeProjectDependencies:
    """Test the analyze_project_dependencies MCP tool."""

    @patch('mcp_server.server._analyzer')
    def test_analyze_project_dependencies_default_path(self, mock_analyzer):
        """Test analyzing project with default path (CWD)."""
        mock_info = ProjectInfo(
            project_path="/current/dir",
            dependency_files=["requirements.txt"],
            dependencies=[Dependency(name="requests", version_spec=">=2.0")]
        )
        mock_analyzer.analyze_project.return_value = mock_info
        
        with patch('os.getcwd', return_value="/current/dir"):
            result = analyze_project_dependencies()
        
        assert result["project_path"] == "/current/dir"
        assert len(result["dependencies"]) == 1
        assert result["dependencies"][0]["name"] == "requests"
        mock_analyzer.analyze_project.assert_called_once_with("/current/dir")

    @patch('mcp_server.server._analyzer')
    def test_analyze_project_dependencies_custom_path(self, mock_analyzer):
        """Test analyzing project with custom path."""
        mock_info = ProjectInfo(
            project_path="/custom/path",
            dependency_files=["pyproject.toml"],
            dependencies=[Dependency(name="httpx", version_spec=">=0.27")]
        )
        mock_analyzer.analyze_project.return_value = mock_info
        
        result = analyze_project_dependencies(project_path="/custom/path")
        
        assert result["project_path"] == "/custom/path"
        assert len(result["dependency_files"]) == 1
        assert "pyproject.toml" in result["dependency_files"][0]
        mock_analyzer.analyze_project.assert_called_once_with("/custom/path")

    @patch('mcp_server.server._analyzer')
    def test_analyze_project_dependencies_serialization(self, mock_analyzer):
        """Test that result is properly serialized."""
        mock_info = ProjectInfo(
            project_path="/test",
            dependencies=[
                Dependency(
                    name="requests", 
                    version_spec=">=2.0", 
                    extras=["security"],
                    is_dev_dependency=True
                )
            ]
        )
        mock_analyzer.analyze_project.return_value = mock_info
        
        result = analyze_project_dependencies(project_path="/test")
        
        # Check serialization of complex objects
        dep = result["dependencies"][0]
        assert dep["name"] == "requests"
        assert dep["version_spec"] == ">=2.0"
        assert dep["extras"] == ["security"]
        assert dep["is_dev_dependency"] is True


class TestGetPackageMetadata:
    """Test the get_package_metadata MCP tool."""

    @patch('mcp_server.server._pkg')
    def test_get_package_metadata_basic(self, mock_pkg):
        """Test getting basic package metadata."""
        mock_info = PackageInfo(
            name="requests",
            version="2.25.0",
            description="HTTP library",
            author="Kenneth Reitz",
            license="Apache 2.0"
        )
        mock_pkg.get_package_info.return_value = mock_info
        
        result = get_package_metadata("requests")
        
        assert result["name"] == "requests"
        assert result["version"] == "2.25.0"
        assert result["description"] == "HTTP library"
        assert result["install_hint"] == "pip install requests"
        mock_pkg.get_package_info.assert_called_once_with("requests", version_spec=None)

    @patch('mcp_server.server._pkg')
    def test_get_package_metadata_with_version_spec(self, mock_pkg):
        """Test getting package metadata with version specifier."""
        mock_info = PackageInfo(name="requests", version="2.25.0")
        mock_pkg.get_package_info.return_value = mock_info
        
        result = get_package_metadata("requests", version_spec=">=2.0,<3.0")
        
        assert result["install_hint"] == "pip install requests>=2.0,<3.0"
        mock_pkg.get_package_info.assert_called_once_with("requests", version_spec=">=2.0,<3.0")

    @patch('mcp_server.server._pkg')
    def test_get_package_metadata_with_long_description(self, mock_pkg):
        """Test getting package metadata with long description."""
        mock_info = PackageInfo(
            name="requests",
            version="2.25.0",
            description="HTTP library",
            long_description="# Requests\n\nA simple HTTP library",
            long_description_content_type="text/markdown"
        )
        mock_pkg.get_package_info.return_value = mock_info
        
        result = get_package_metadata("requests")
        
        assert result["long_description"] == "# Requests\n\nA simple HTTP library"
        assert result["long_description_content_type"] == "text/markdown"


class TestSearchPackages:
    """Test the search_packages MCP tool."""

    @patch('mcp_server.server._pkg')
    def test_search_packages_basic(self, mock_pkg):
        """Test basic package search."""
        mock_results = [
            PackageSearchResult(
                name="requests",
                description="HTTP library",
                version="2.25.0",
                author="Kenneth Reitz"
            ),
            PackageSearchResult(
                name="httpx",
                description="Async HTTP client",
                version="0.27.0",
                author="Tom Christie"
            )
        ]
        mock_pkg.search_packages.return_value = mock_results
        
        result = search_packages("http client")
        
        assert len(result) == 2
        assert result[0]["name"] == "requests"
        assert result[1]["name"] == "httpx"
        mock_pkg.search_packages.assert_called_once_with("http client", limit=10, python_version=None)

    @patch('mcp_server.server._pkg')
    def test_search_packages_with_limit(self, mock_pkg):
        """Test package search with custom limit."""
        mock_pkg.search_packages.return_value = []
        
        search_packages("test", limit=5)
        
        mock_pkg.search_packages.assert_called_once_with("test", limit=5, python_version=None)

    @patch('mcp_server.server._pkg')
    def test_search_packages_with_python_version(self, mock_pkg):
        """Test package search with Python version hint."""
        mock_pkg.search_packages.return_value = []
        
        search_packages("test", python_version="3.11")
        
        mock_pkg.search_packages.assert_called_once_with("test", limit=10, python_version="3.11")

    @patch('mcp_server.server._pkg')
    def test_search_packages_fallback_to_exact_match(self, mock_pkg):
        """Test fallback to exact package name when search returns nothing."""
        # First call (search) returns empty
        # Second call (get_package_info) returns package info
        mock_pkg.search_packages.return_value = []
        mock_info = PackageInfo(
            name="exact-package",
            version="1.0.0",
            description="Exact match",
            author="Test Author"
        )
        mock_pkg.get_package_info.return_value = mock_info
        
        result = search_packages("exact-package")
        
        assert len(result) == 1
        assert result[0]["name"] == "exact-package"
        assert result[0]["description"] == "Exact match"
        mock_pkg.get_package_info.assert_called_once_with("exact-package")

    @patch('mcp_server.server._pkg')
    def test_search_packages_fallback_fails(self, mock_pkg):
        """Test fallback behavior when exact match also fails."""
        mock_pkg.search_packages.return_value = []
        mock_pkg.get_package_info.side_effect = Exception("Package not found")
        
        result = search_packages("nonexistent")
        
        assert result == []


class TestCheckPackageCompatibility:
    """Test the check_package_compatibility MCP tool."""

    @patch('mcp_server.server._analyzer')
    @patch('mcp_server.server._pkg')
    def test_check_package_compatibility_default_path(self, mock_pkg, mock_analyzer):
        """Test compatibility check with default path."""
        mock_info = ProjectInfo(
            project_path="/current/dir",
            dependencies=[Dependency(name="requests", version_spec=">=2.0")]
        )
        mock_analyzer.analyze_project.return_value = mock_info
        mock_pkg.check_compatibility.return_value = {"conflicts": []}
        
        with patch('os.getcwd', return_value="/current/dir"):
            result = check_package_compatibility("httpx")
        
        assert result["conflicts"] == []
        mock_analyzer.analyze_project.assert_called_once_with("/current/dir")
        mock_pkg.check_compatibility.assert_called_once_with(
            mock_info.dependencies, "httpx", None
        )

    @patch('mcp_server.server._analyzer')
    @patch('mcp_server.server._pkg')
    def test_check_package_compatibility_with_version(self, mock_pkg, mock_analyzer):
        """Test compatibility check with version specifier."""
        mock_info = ProjectInfo(project_path="/test", dependencies=[])
        mock_analyzer.analyze_project.return_value = mock_info
        mock_pkg.check_compatibility.return_value = {"conflicts": []}
        
        check_package_compatibility("httpx", version_spec=">=0.27", project_path="/test")
        
        mock_pkg.check_compatibility.assert_called_once_with([], "httpx", ">=0.27")

    @patch('mcp_server.server._analyzer')
    @patch('mcp_server.server._pkg')
    def test_check_package_compatibility_with_conflicts(self, mock_pkg, mock_analyzer):
        """Test compatibility check that finds conflicts."""
        mock_info = ProjectInfo(project_path="/test", dependencies=[])
        mock_analyzer.analyze_project.return_value = mock_info
        
        conflicts = [
            {
                "package": "requests",
                "reason": "No version satisfies all constraints",
                "constraints": [">=2.0", ">=3.0"]
            }
        ]
        mock_pkg.check_compatibility.return_value = {"conflicts": conflicts}
        
        result = check_package_compatibility("requests", version_spec=">=3.0")
        
        assert len(result["conflicts"]) == 1
        assert result["conflicts"][0]["package"] == "requests"


class TestGetLatestVersion:
    """Test the get_latest_version MCP tool."""

    @patch('mcp_server.server._pkg')
    def test_get_latest_version_basic(self, mock_pkg):
        """Test getting latest version."""
        mock_result = {
            "name": "requests",
            "version": "2.25.0",
            "is_prerelease": False,
            "source": "pypi"
        }
        mock_pkg.get_latest_version.return_value = mock_result
        
        result = get_latest_version("requests")
        
        assert result == mock_result
        mock_pkg.get_latest_version.assert_called_once_with("requests", allow_prerelease=False)

    @patch('mcp_server.server._pkg')
    def test_get_latest_version_with_prerelease(self, mock_pkg):
        """Test getting latest version including prereleases."""
        mock_result = {
            "name": "requests",
            "version": "2.26.0rc1",
            "is_prerelease": True,
            "source": "pypi"
        }
        mock_pkg.get_latest_version.return_value = mock_result
        
        result = get_latest_version("requests", allow_prerelease=True)
        
        assert result["version"] == "2.26.0rc1"
        assert result["is_prerelease"] is True
        mock_pkg.get_latest_version.assert_called_once_with("requests", allow_prerelease=True)


class TestServerIntegration:
    """Integration tests for the MCP server."""

    def test_server_singletons_exist(self):
        """Test that server singletons are properly initialized."""
        assert _analyzer is not None
        assert _pkg is not None

    @patch('mcp_server.server.mcp')
    def test_main_function_stdio(self, mock_mcp):
        """Test main function with stdio transport."""
        from mcp_server.server import main
        
        with patch('sys.argv', ['server.py', 'stdio']):
            main()
        
        mock_mcp.run.assert_called_once_with(transport='stdio')

    @patch('mcp_server.server.mcp')
    def test_main_function_default_transport(self, mock_mcp):
        """Test main function with default transport."""
        from mcp_server.server import main
        
        with patch('sys.argv', ['server.py']):
            main()
        
        mock_mcp.run.assert_called_once_with(transport='stdio')

    def test_real_project_analysis(self):
        """Integration test with real project structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a real requirements.txt
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("requests>=2.25.0\nhttpx==0.27.0\n")
            
            # Test the actual function
            result = analyze_project_dependencies(project_path=tmpdir)
            
            assert "project_path" in result
            assert "dependencies" in result
            assert len(result["dependencies"]) == 2
            
            # Check dependency details
            dep_names = {d["name"] for d in result["dependencies"]}
            assert dep_names == {"requests", "httpx"}

    def test_tool_error_handling(self):
        """Test that tools handle errors gracefully."""
        # This should not raise an exception even with invalid path
        result = analyze_project_dependencies(project_path="/nonexistent/path")
        
        # Should return valid structure even on error
        assert "project_path" in result
        assert "dependencies" in result
        assert isinstance(result["dependencies"], list)