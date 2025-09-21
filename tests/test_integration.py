"""Integration tests for the MCP server."""

import tempfile
from pathlib import Path
from unittest.mock import patch, Mock

import pytest
from mcp_server.project_analyzer import ProjectAnalyzer
from mcp_server.package_manager import PackageManager, LocalMetadataExtractor, PyPIClient
from mcp_server.models import Dependency, PackageInfo


class TestEndToEndIntegration:
    """End-to-end integration tests."""

    def test_full_project_analysis_workflow(self, temp_project_dir):
        """Test complete workflow from project analysis to package info."""
        # Create a realistic project structure
        req_file = temp_project_dir / "requirements.txt"
        req_file.write_text("requests>=2.25.0\nhttpx>=0.27.0\n")
        
        pyproject_file = temp_project_dir / "pyproject.toml"
        pyproject_content = """
[project]
dependencies = ["packaging>=21.0"]

[project.optional-dependencies]
dev = ["pytest>=7.0"]
        """
        pyproject_file.write_text(pyproject_content)
        
        # Analyze the project
        analyzer = ProjectAnalyzer()
        project_info = analyzer.analyze_project(str(temp_project_dir))
        
        # Verify project analysis
        assert len(project_info.dependency_files) == 2
        assert len(project_info.dependencies) == 4  # 3 prod + 1 dev
        
        dep_names = {d.name for d in project_info.dependencies}
        assert dep_names == {"requests", "httpx", "packaging", "pytest"}
        
        # Check dev dependency classification
        dev_deps = [d for d in project_info.dependencies if d.is_dev_dependency]
        assert len(dev_deps) == 1
        assert dev_deps[0].name == "pytest"

    def test_package_manager_local_first_strategy(self):
        """Test that PackageManager prefers local packages over PyPI."""
        mock_local = Mock(spec=LocalMetadataExtractor)
        mock_client = Mock(spec=PyPIClient)
        
        # Local package exists
        local_info = PackageInfo(
            name="requests",
            version="2.25.0",
            description="Local installation"
        )
        mock_local.is_package_installed.return_value = True
        mock_local.get_local_package_info.return_value = local_info
        
        manager = PackageManager(client=mock_client, local=mock_local)
        result = manager.get_package_info("requests")
        
        # Should return local info without calling PyPI
        assert result == local_info
        mock_local.is_package_installed.assert_called_once_with("requests")
        mock_client.get_project.assert_not_called()

    def test_package_manager_pypi_fallback(self):
        """Test PackageManager falls back to PyPI when package not local."""
        mock_local = Mock(spec=LocalMetadataExtractor)
        mock_client = Mock(spec=PyPIClient)
        
        # No local package
        mock_local.is_package_installed.return_value = False
        
        # Mock PyPI response
        pypi_data = {
            "info": {
                "name": "requests",
                "version": "2.25.0",
                "summary": "HTTP library"
            },
            "releases": {
                "2.25.0": [{"yanked": False}]
            }
        }
        mock_client.get_project.return_value = pypi_data
        mock_client.get_release.return_value = {"info": pypi_data["info"]}
        
        manager = PackageManager(client=mock_client, local=mock_local)
        result = manager.get_package_info("requests")
        
        assert result.name == "requests"
        assert result.version == "2.25.0"
        assert result.description == "HTTP library"
        mock_client.get_project.assert_called_once_with("requests")

    def test_error_handling_chain(self, temp_project_dir):
        """Test error handling throughout the system."""
        # Create invalid dependency file
        req_file = temp_project_dir / "requirements.txt"
        req_file.write_text("invalid requirement with spaces\n")
        
        analyzer = ProjectAnalyzer()
        project_info = analyzer.analyze_project(str(temp_project_dir))
        
        # Should have error dependency instead of crashing
        assert len(project_info.dependencies) == 1
        assert project_info.dependencies[0].name == "__parse_error__"
        assert "Invalid requirement line" in project_info.dependencies[0].version_spec

    def test_caching_behavior(self, temp_project_dir):
        """Test that caching works correctly across multiple calls."""
        req_file = temp_project_dir / "requirements.txt"
        req_file.write_text("requests>=2.25.0\n")
        
        analyzer = ProjectAnalyzer()
        
        # First analysis
        info1 = analyzer.analyze_project(str(temp_project_dir))
        
        # Second analysis should use cache
        info2 = analyzer.analyze_project(str(temp_project_dir))
        
        assert info1.dependencies == info2.dependencies
        assert len(analyzer._cache) == 1
        
        # Modify file to invalidate cache
        import time
        time.sleep(0.1)  # Ensure different mtime
        req_file.write_text("requests>=2.25.0\nhttpx>=0.27.0\n")
        
        # Third analysis should detect change
        info3 = analyzer.analyze_project(str(temp_project_dir))
        
        assert len(info3.dependencies) == 2
        assert len(info1.dependencies) == 1

    def test_multiple_file_types_integration(self, temp_project_dir):
        """Test handling multiple dependency file types in one project."""
        # Create requirements.txt
        req_file = temp_project_dir / "requirements.txt"
        req_file.write_text("requests>=2.25.0\n")
        
        # Create pyproject.toml
        pyproject_file = temp_project_dir / "pyproject.toml"
        pyproject_content = """
[project]
dependencies = ["httpx>=0.27.0"]

[project.optional-dependencies]
dev = ["pytest>=7.0"]
        """
        pyproject_file.write_text(pyproject_content)
        
        # Create Pipfile
        pipfile = temp_project_dir / "Pipfile"
        pipfile_content = """
[packages]
packaging = ">=21.0"

[dev-packages]
black = "*"
        """
        pipfile.write_text(pipfile_content)
        
        analyzer = ProjectAnalyzer()
        project_info = analyzer.analyze_project(str(temp_project_dir))
        
        # Should find all files
        assert len(project_info.dependency_files) == 3
        
        # Should parse all dependencies
        dep_names = {d.name for d in project_info.dependencies}
        assert dep_names == {"requests", "httpx", "pytest", "packaging", "black"}
        
        # Check dev dependency classification
        dev_deps = [d for d in project_info.dependencies if d.is_dev_dependency]
        dev_names = {d.name for d in dev_deps}
        assert dev_names == {"pytest", "black"}

    @patch('mcp_server.package_manager.httpx.Client')
    def test_network_error_handling(self, mock_client_class):
        """Test graceful handling of network errors."""
        # Mock network failure
        mock_client = Mock()
        mock_client.get.side_effect = Exception("Network error")
        mock_client_class.return_value = mock_client
        
        client = PyPIClient()
        
        with pytest.raises(Exception):  # Should propagate as NetworkError
            client.search("test")

    def test_version_compatibility_checking(self):
        """Test version compatibility checking logic."""
        existing_deps = [
            Dependency(name="requests", version_spec=">=2.0,<3.0"),
            Dependency(name="urllib3", version_spec=">=1.21")
        ]
        
        mock_client = Mock(spec=PyPIClient)
        
        # Mock PyPI responses
        def mock_get_project(name):
            if name == "requests":
                return {
                    "releases": {
                        "2.25.0": [{"yanked": False}],
                        "2.26.0": [{"yanked": False}],
                        "3.0.0": [{"yanked": False}]  # This would conflict
                    }
                }
            elif name == "urllib3":
                return {
                    "releases": {
                        "1.26.0": [{"yanked": False}]
                    }
                }
            return {"releases": {}}
        
        mock_client.get_project.side_effect = mock_get_project
        
        manager = PackageManager(client=mock_client)
        result = manager.check_compatibility(existing_deps, "requests", ">=3.0")
        
        # Should detect conflict
        assert len(result["conflicts"]) == 1
        assert result["conflicts"][0]["package"] == "requests"