"""Pytest configuration and fixtures."""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest
from mcp_server.models import Dependency, PackageInfo, ProjectInfo


@pytest.fixture
def temp_project_dir():
    """Create a temporary directory for testing project analysis."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_requirements_txt(temp_project_dir):
    """Create a sample requirements.txt file."""
    content = """
# Production dependencies
requests>=2.25.0
httpx==0.27.0
packaging>=21.0

# Comments and empty lines should be ignored

beautifulsoup4>=4.9.0
    """
    req_file = temp_project_dir / "requirements.txt"
    req_file.write_text(content)
    return req_file


@pytest.fixture
def sample_pyproject_toml(temp_project_dir):
    """Create a sample pyproject.toml file."""
    content = """
[project]
name = "test-project"
version = "1.0.0"
dependencies = [
    "requests>=2.25.0",
    "httpx>=0.27.0"
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "black>=22.0"
]
test = [
    "coverage>=6.0"
]
    """
    toml_file = temp_project_dir / "pyproject.toml"
    toml_file.write_text(content)
    return toml_file


@pytest.fixture
def sample_pipfile(temp_project_dir):
    """Create a sample Pipfile."""
    content = """
[packages]
requests = ">=2.25.0"
httpx = "*"

[dev-packages]
pytest = ">=7.0"
black = "*"
    """
    pipfile = temp_project_dir / "Pipfile"
    pipfile.write_text(content)
    return pipfile


@pytest.fixture
def sample_setup_py(temp_project_dir):
    """Create a sample setup.py file."""
    content = '''
from setuptools import setup, find_packages

setup(
    name="test-package",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "requests>=2.25.0",
        "httpx>=0.27.0",
        "packaging>=21.0"
    ],
    extras_require={
        "dev": ["pytest>=7.0", "black>=22.0"]
    }
)
    '''
    setup_file = temp_project_dir / "setup.py"
    setup_file.write_text(content)
    return setup_file


@pytest.fixture
def sample_dependency():
    """Create a sample Dependency object."""
    return Dependency(
        name="requests",
        version_spec=">=2.25.0",
        extras=["security"],
        source_file="requirements.txt",
        is_dev_dependency=False
    )


@pytest.fixture
def sample_package_info():
    """Create a sample PackageInfo object."""
    return PackageInfo(
        name="requests",
        version="2.25.0",
        description="HTTP library for Python",
        long_description="# Requests\n\nA simple HTTP library for Python",
        long_description_content_type="text/markdown",
        author="Kenneth Reitz",
        license="Apache 2.0",
        homepage="https://requests.readthedocs.io",
        repository="https://github.com/psf/requests",
        keywords=["http", "requests", "web"],
        dependencies=[
            Dependency(name="urllib3", version_spec=">=1.21.1,<1.27"),
            Dependency(name="certifi", version_spec=">=2017.4.17")
        ],
        python_requires=">=3.7"
    )


@pytest.fixture
def sample_project_info(temp_project_dir):
    """Create a sample ProjectInfo object."""
    return ProjectInfo(
        project_path=str(temp_project_dir),
        dependency_files=[str(temp_project_dir / "requirements.txt")],
        dependencies=[
            Dependency(name="requests", version_spec=">=2.25.0"),
            Dependency(name="pytest", version_spec=">=7.0", is_dev_dependency=True)
        ]
    )


@pytest.fixture
def mock_pypi_response():
    """Create a mock PyPI API response."""
    return {
        "info": {
            "name": "requests",
            "version": "2.25.0",
            "summary": "Python HTTP for Humans.",
            "description": "# Requests\n\nA simple HTTP library for Python",
            "description_content_type": "text/markdown",
            "author": "Kenneth Reitz",
            "license": "Apache 2.0",
            "home_page": "https://requests.readthedocs.io",
            "project_urls": {
                "Homepage": "https://requests.readthedocs.io",
                "Repository": "https://github.com/psf/requests"
            },
            "keywords": "http,requests,web",
            "requires_dist": [
                "urllib3>=1.21.1,<1.27",
                "certifi>=2017.4.17"
            ],
            "requires_python": ">=3.7"
        },
        "releases": {
            "2.24.0": [{"yanked": False, "upload_time_iso_8601": "2020-06-17T10:00:00Z"}],
            "2.25.0": [{"yanked": False, "upload_time_iso_8601": "2020-11-11T15:30:00Z"}]
        },
        "urls": [
            {"upload_time_iso_8601": "2020-11-11T15:30:00Z"}
        ]
    }


@pytest.fixture
def mock_search_html():
    """Create mock HTML search results."""
    return '''
    <html>
        <body>
            <a class="package-snippet" href="/project/requests/">
                <span class="package-snippet__name">requests</span>
            </a>
            <a class="package-snippet" href="/project/httpx/">
                <span class="package-snippet__name">httpx</span>
            </a>
            <a class="package-snippet" href="/project/urllib3/">
                <span class="package-snippet__name">urllib3</span>
            </a>
        </body>
    </html>
    '''