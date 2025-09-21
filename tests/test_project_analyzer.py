"""Tests for project analyzer functionality."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open

import pytest
from mcp_server.project_analyzer import DependencyParser, ProjectAnalyzer, DEPENDENCY_FILE_NAMES
from mcp_server.models import Dependency, ProjectInfo
from mcp_server.errors import FileSystemError, ParsingError


class TestDependencyParser:
    """Test the DependencyParser class."""

    def setup_method(self):
        self.parser = DependencyParser()

    def test_parse_requirements_txt_simple(self):
        """Test parsing simple requirements.txt content."""
        content = "requests>=2.25.0\nhttpx==0.27.0\n"
        
        with patch("builtins.open", mock_open(read_data=content)):
            deps = self.parser.parse_requirements_txt("requirements.txt")
        
        assert len(deps) == 2
        assert deps[0].name == "requests"
        assert deps[0].version_spec == ">=2.25.0"
        assert deps[1].name == "httpx"
        assert deps[1].version_spec == "==0.27.0"

    def test_parse_requirements_txt_with_comments(self):
        """Test parsing requirements.txt with comments and empty lines."""
        content = """
# This is a comment
requests>=2.25.0

# Another comment
httpx==0.27.0
        """
        
        with patch("builtins.open", mock_open(read_data=content)):
            deps = self.parser.parse_requirements_txt("requirements.txt")
        
        assert len(deps) == 2
        assert deps[0].name == "requests"
        assert deps[1].name == "httpx"

    def test_parse_requirements_txt_with_extras(self):
        """Test parsing requirements with extras."""
        content = "requests[security,socks]>=2.25.0\n"
        
        with patch("builtins.open", mock_open(read_data=content)):
            deps = self.parser.parse_requirements_txt("requirements.txt")
        
        assert len(deps) == 1
        assert deps[0].name == "requests"
        assert deps[0].extras == ["security", "socks"]

    def test_parse_requirements_txt_file_not_found(self):
        """Test handling of missing requirements.txt file."""
        with pytest.raises(FileSystemError, match="File not found"):
            self.parser.parse_requirements_txt("nonexistent.txt")

    def test_parse_requirements_txt_invalid_line(self):
        """Test handling of invalid requirement lines."""
        content = "invalid requirement with spaces\n"
        
        with patch("builtins.open", mock_open(read_data=content)):
            with pytest.raises(ParsingError, match="Invalid requirement line"):
                self.parser.parse_requirements_txt("requirements.txt")

    def test_parse_pyproject_toml_basic(self):
        """Test parsing basic pyproject.toml dependencies."""
        toml_content = """
[project]
dependencies = [
    "requests>=2.25.0",
    "httpx==0.27.0"
]
        """
        
        with patch("pathlib.Path.read_text", return_value=toml_content):
            deps = self.parser.parse_pyproject_toml("pyproject.toml")
        
        assert len(deps) == 2
        assert deps[0].name == "requests"
        assert deps[0].version_spec == ">=2.25.0"
        assert deps[0].is_dev_dependency is False

    def test_parse_pyproject_toml_with_optional_dependencies(self):
        """Test parsing pyproject.toml with optional dependencies."""
        toml_content = """
[project]
dependencies = ["requests>=2.25.0"]

[project.optional-dependencies]
dev = ["pytest>=7.0", "black>=22.0"]
test = ["coverage>=6.0"]
        """
        
        with patch("pathlib.Path.read_text", return_value=toml_content):
            deps = self.parser.parse_pyproject_toml("pyproject.toml")
        
        assert len(deps) == 4
        
        # Main dependency
        main_deps = [d for d in deps if not d.is_dev_dependency]
        assert len(main_deps) == 1
        assert main_deps[0].name == "requests"
        
        # Dev dependencies
        dev_deps = [d for d in deps if d.is_dev_dependency]
        assert len(dev_deps) == 3
        dev_names = {d.name for d in dev_deps}
        assert dev_names == {"pytest", "black", "coverage"}

    def test_parse_pyproject_toml_invalid(self):
        """Test handling of invalid TOML content."""
        invalid_toml = "invalid toml content ["
        
        with patch("pathlib.Path.read_text", return_value=invalid_toml):
            with pytest.raises(ParsingError, match="Failed to parse pyproject.toml"):
                self.parser.parse_pyproject_toml("pyproject.toml")

    def test_parse_pipfile_basic(self):
        """Test parsing basic Pipfile."""
        pipfile_content = """
[packages]
requests = ">=2.25.0"
httpx = "*"

[dev-packages]
pytest = ">=7.0"
        """
        
        with patch("pathlib.Path.read_text", return_value=pipfile_content):
            deps = self.parser.parse_pipfile("Pipfile")
        
        assert len(deps) == 3
        
        prod_deps = [d for d in deps if not d.is_dev_dependency]
        assert len(prod_deps) == 2
        
        dev_deps = [d for d in deps if d.is_dev_dependency]
        assert len(dev_deps) == 1
        assert dev_deps[0].name == "pytest"

    def test_parse_pipfile_with_dict_specs(self):
        """Test parsing Pipfile with dictionary specifications."""
        pipfile_content = """
[packages]
requests = {version = ">=2.25.0", extras = ["security"]}
        """
        
        with patch("pathlib.Path.read_text", return_value=pipfile_content):
            deps = self.parser.parse_pipfile("Pipfile")
        
        assert len(deps) == 1
        assert deps[0].name == "requests"
        assert deps[0].version_spec == ">=2.25.0"

    def test_parse_setup_py_basic(self):
        """Test parsing basic setup.py file."""
        setup_content = '''
from setuptools import setup

setup(
    name="test-package",
    install_requires=[
        "requests>=2.25.0",
        "httpx==0.27.0"
    ]
)
        '''
        
        with patch("pathlib.Path.read_text", return_value=setup_content):
            deps = self.parser.parse_setup_py("setup.py")
        
        assert len(deps) == 2
        assert deps[0].name == "requests"
        assert deps[0].version_spec == ">=2.25.0"
        assert deps[1].name == "httpx"

    def test_parse_setup_py_no_install_requires(self):
        """Test parsing setup.py without install_requires."""
        setup_content = '''
from setuptools import setup

setup(
    name="test-package",
    version="1.0.0"
)
        '''
        
        with patch("pathlib.Path.read_text", return_value=setup_content):
            deps = self.parser.parse_setup_py("setup.py")
        
        assert len(deps) == 0

    def test_parse_setup_py_invalid_syntax(self):
        """Test handling of invalid Python syntax in setup.py."""
        invalid_content = "invalid python syntax ["
        
        with patch("pathlib.Path.read_text", return_value=invalid_content):
            with pytest.raises(ParsingError, match="Failed to parse setup.py"):
                self.parser.parse_setup_py("setup.py")


class TestProjectAnalyzer:
    """Test the ProjectAnalyzer class."""

    def setup_method(self):
        self.analyzer = ProjectAnalyzer()

    def test_scan_files_finds_existing_files(self):
        """Test that _scan_files finds existing dependency files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some dependency files
            (Path(tmpdir) / "requirements.txt").touch()
            (Path(tmpdir) / "pyproject.toml").touch()
            
            files = self.analyzer._scan_files(tmpdir)
            
            assert len(files) == 2
            assert any("requirements.txt" in f for f in files)
            assert any("pyproject.toml" in f for f in files)

    def test_scan_files_empty_directory(self):
        """Test _scan_files with directory containing no dependency files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            files = self.analyzer._scan_files(tmpdir)
            assert len(files) == 0

    def test_analyze_project_with_requirements_txt(self):
        """Test analyzing project with requirements.txt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("requests>=2.25.0\nhttpx==0.27.0\n")
            
            info = self.analyzer.analyze_project(tmpdir)
            
            assert isinstance(info, ProjectInfo)
            assert len(info.dependency_files) == 1
            assert len(info.dependencies) == 2
            assert info.dependencies[0].name == "requests"

    def test_analyze_project_caching(self):
        """Test that project analysis results are cached properly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("requests>=2.25.0\n")
            
            # First analysis
            info1 = self.analyzer.analyze_project(tmpdir)
            
            # Second analysis should use cache
            info2 = self.analyzer.analyze_project(tmpdir)
            
            assert info1.dependencies == info2.dependencies
            assert len(self.analyzer._cache) == 1

    def test_analyze_project_cache_invalidation(self):
        """Test that cache is invalidated when files change."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("requests>=2.25.0\n")
            
            # First analysis
            info1 = self.analyzer.analyze_project(tmpdir)
            assert len(info1.dependencies) == 1
            
            # Modify file
            import time
            time.sleep(0.1)  # Ensure different mtime
            req_file.write_text("requests>=2.25.0\nhttpx==0.27.0\n")
            
            # Second analysis should detect change
            info2 = self.analyzer.analyze_project(tmpdir)
            assert len(info2.dependencies) == 2

    def test_analyze_project_with_parse_error(self):
        """Test handling of parse errors in dependency files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("invalid requirement with spaces\n")
            
            info = self.analyzer.analyze_project(tmpdir)
            
            # Should have an error dependency
            assert len(info.dependencies) == 1
            assert info.dependencies[0].name == "__parse_error__"

    def test_analyze_project_multiple_files(self):
        """Test analyzing project with multiple dependency files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create requirements.txt
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("requests>=2.25.0\n")
            
            # Create pyproject.toml
            toml_file = Path(tmpdir) / "pyproject.toml"
            toml_content = """
[project]
dependencies = ["httpx>=0.27.0"]
            """
            toml_file.write_text(toml_content)
            
            info = self.analyzer.analyze_project(tmpdir)
            
            assert len(info.dependency_files) == 2
            assert len(info.dependencies) == 2
            dep_names = {d.name for d in info.dependencies}
            assert dep_names == {"requests", "httpx"}

    def test_get_dependencies_empty_cache(self):
        """Test get_dependencies with empty cache."""
        deps = self.analyzer.get_dependencies()
        assert deps == []

    def test_get_dependencies_with_cache(self):
        """Test get_dependencies with populated cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("requests>=2.25.0\n")
            
            # Populate cache
            self.analyzer.analyze_project(tmpdir)
            
            # Get dependencies
            deps = self.analyzer.get_dependencies()
            assert len(deps) == 1
            assert deps[0].name == "requests"

    def test_dependency_file_names_constant(self):
        """Test that DEPENDENCY_FILE_NAMES contains expected files."""
        expected_files = ["requirements.txt", "pyproject.toml", "Pipfile", "setup.py"]
        assert DEPENDENCY_FILE_NAMES == expected_files