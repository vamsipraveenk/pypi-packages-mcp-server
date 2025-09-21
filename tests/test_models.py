"""Tests for data models."""

from datetime import datetime, timezone
from mcp_server.models import Dependency, PackageInfo, PackageSearchResult, ProjectInfo


class TestDependency:
    """Test the Dependency model."""

    def test_dependency_defaults(self):
        """Test Dependency with minimal required fields."""
        d = Dependency(name="requests")
        assert d.name == "requests"
        assert d.version_spec == ""
        assert d.extras == []
        assert d.source_file == ""
        assert d.is_dev_dependency is False

    def test_dependency_full(self):
        """Test Dependency with all fields."""
        d = Dependency(
            name="requests",
            version_spec=">=2.25.0",
            extras=["security", "socks"],
            source_file="requirements.txt",
            is_dev_dependency=True
        )
        assert d.name == "requests"
        assert d.version_spec == ">=2.25.0"
        assert d.extras == ["security", "socks"]
        assert d.source_file == "requirements.txt"
        assert d.is_dev_dependency is True

    def test_dependency_equality(self):
        """Test Dependency equality comparison."""
        d1 = Dependency(name="requests", version_spec=">=2.0")
        d2 = Dependency(name="requests", version_spec=">=2.0")
        d3 = Dependency(name="httpx", version_spec=">=2.0")
        
        assert d1 == d2
        assert d1 != d3


class TestPackageInfo:
    """Test the PackageInfo model."""

    def test_package_info_defaults(self):
        """Test PackageInfo with minimal required fields."""
        pkg = PackageInfo(name="requests")
        assert pkg.name == "requests"
        assert pkg.version == ""
        assert pkg.description == ""
        assert pkg.long_description == ""
        assert pkg.long_description_content_type == ""
        assert pkg.author == ""
        assert pkg.license == ""
        assert pkg.homepage == ""
        assert pkg.repository == ""
        assert pkg.keywords == []
        assert pkg.dependencies == []
        assert pkg.python_requires == ""
        assert pkg.last_updated is None

    def test_package_info_full(self):
        """Test PackageInfo with all fields."""
        deps = [Dependency(name="urllib3", version_spec=">=1.21")]
        last_updated = datetime(2023, 1, 1, tzinfo=timezone.utc)
        
        pkg = PackageInfo(
            name="requests",
            version="2.25.0",
            description="HTTP library for Python",
            long_description="# Requests\n\nA simple HTTP library",
            long_description_content_type="text/markdown",
            author="Kenneth Reitz",
            license="Apache 2.0",
            homepage="https://requests.readthedocs.io",
            repository="https://github.com/psf/requests",
            keywords=["http", "requests", "web"],
            dependencies=deps,
            python_requires=">=3.7",
            last_updated=last_updated
        )
        
        assert pkg.name == "requests"
        assert pkg.version == "2.25.0"
        assert pkg.description == "HTTP library for Python"
        assert pkg.long_description == "# Requests\n\nA simple HTTP library"
        assert pkg.long_description_content_type == "text/markdown"
        assert pkg.author == "Kenneth Reitz"
        assert pkg.license == "Apache 2.0"
        assert pkg.homepage == "https://requests.readthedocs.io"
        assert pkg.repository == "https://github.com/psf/requests"
        assert pkg.keywords == ["http", "requests", "web"]
        assert len(pkg.dependencies) == 1
        assert pkg.dependencies[0].name == "urllib3"
        assert pkg.python_requires == ">=3.7"
        assert pkg.last_updated == last_updated


class TestPackageSearchResult:
    """Test the PackageSearchResult model."""

    def test_package_search_result_defaults(self):
        """Test PackageSearchResult with minimal fields."""
        result = PackageSearchResult(name="requests")
        assert result.name == "requests"
        assert result.description == ""
        assert result.version == ""
        assert result.author == ""

    def test_package_search_result_full(self):
        """Test PackageSearchResult with all fields."""
        result = PackageSearchResult(
            name="requests",
            description="HTTP library",
            version="2.25.0",
            author="Kenneth Reitz"
        )
        assert result.name == "requests"
        assert result.description == "HTTP library"
        assert result.version == "2.25.0"
        assert result.author == "Kenneth Reitz"


class TestProjectInfo:
    """Test the ProjectInfo model."""

    def test_project_info_defaults(self):
        """Test ProjectInfo with minimal fields."""
        proj = ProjectInfo(project_path="/tmp")
        assert proj.project_path == "/tmp"
        assert proj.dependency_files == []
        assert proj.dependencies == []

    def test_project_info_full(self):
        """Test ProjectInfo with all fields."""
        deps = [
            Dependency(name="requests", version_spec=">=2.0"),
            Dependency(name="httpx", version_spec=">=0.27", is_dev_dependency=True)
        ]
        files = ["requirements.txt", "requirements-dev.txt"]
        
        proj = ProjectInfo(
            project_path="/home/user/project",
            dependency_files=files,
            dependencies=deps
        )
        
        assert proj.project_path == "/home/user/project"
        assert proj.dependency_files == files
        assert len(proj.dependencies) == 2
        assert proj.dependencies[0].name == "requests"
        assert proj.dependencies[1].is_dev_dependency is True

    def test_project_info_dependency_filtering(self):
        """Test filtering dependencies by type."""
        deps = [
            Dependency(name="requests", version_spec=">=2.0", is_dev_dependency=False),
            Dependency(name="pytest", version_spec=">=7.0", is_dev_dependency=True),
            Dependency(name="httpx", version_spec=">=0.27", is_dev_dependency=False)
        ]
        
        proj = ProjectInfo(project_path="/test", dependencies=deps)
        
        # Filter production dependencies
        prod_deps = [d for d in proj.dependencies if not d.is_dev_dependency]
        assert len(prod_deps) == 2
        assert {d.name for d in prod_deps} == {"requests", "httpx"}
        
        # Filter dev dependencies
        dev_deps = [d for d in proj.dependencies if d.is_dev_dependency]
        assert len(dev_deps) == 1
        assert dev_deps[0].name == "pytest"
