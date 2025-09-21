"""Tests for package manager functionality."""

import json
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

import pytest
import httpx
from packaging.version import Version
from packaging.specifiers import SpecifierSet

from mcp_server.package_manager import (
    LocalMetadataExtractor, 
    PyPIClient, 
    PackageManager,
    PYPI_JSON,
    PYPI_SEARCH_HTML
)
from mcp_server.models import Dependency, PackageInfo, PackageSearchResult
from mcp_server.errors import NetworkError


class TestLocalMetadataExtractor:
    """Test the LocalMetadataExtractor class."""

    def setup_method(self):
        self.extractor = LocalMetadataExtractor()

    @patch('importlib.metadata.version')
    def test_is_package_installed_true(self, mock_version):
        """Test is_package_installed returns True for installed package."""
        mock_version.return_value = "2.25.0"
        
        result = self.extractor.is_package_installed("requests")
        
        assert result is True
        mock_version.assert_called_once_with("requests")

    @patch('importlib.metadata.version')
    def test_is_package_installed_false(self, mock_version):
        """Test is_package_installed returns False for missing package."""
        from importlib.metadata import PackageNotFoundError
        mock_version.side_effect = PackageNotFoundError()
        
        result = self.extractor.is_package_installed("nonexistent")
        
        assert result is False

    @patch('importlib.metadata.version')
    @patch('importlib.metadata.metadata')
    def test_get_local_package_info_basic(self, mock_metadata, mock_version):
        """Test getting basic local package info."""
        mock_version.return_value = "2.25.0"
        
        # Mock metadata object
        mock_md = Mock()
        mock_md.get.side_effect = lambda key, default="": {
            "Name": "requests",
            "Summary": "HTTP library",
            "Author": "Kenneth Reitz",
            "License": "Apache 2.0",
            "Home-page": "https://requests.readthedocs.io"
        }.get(key, default)
        mock_md.get_all.return_value = ["urllib3>=1.21.1"]
        mock_md.get_payload.return_value = "Long description content"
        mock_metadata.return_value = mock_md
        
        info = self.extractor.get_local_package_info("requests")
        
        assert isinstance(info, PackageInfo)
        assert info.name == "requests"
        assert info.version == "2.25.0"
        assert info.description == "HTTP library"
        assert info.author == "Kenneth Reitz"
        assert info.license == "Apache 2.0"
        assert info.homepage == "https://requests.readthedocs.io"
        assert info.long_description == "Long description content"

    @patch('importlib.metadata.version')
    def test_get_local_package_info_not_found(self, mock_version):
        """Test handling of package not found error."""
        from importlib.metadata import PackageNotFoundError
        mock_version.side_effect = PackageNotFoundError()
        
        with pytest.raises(NetworkError, match="Package not installed"):
            self.extractor.get_local_package_info("nonexistent")

    @patch('importlib.metadata.version')
    @patch('importlib.metadata.metadata')
    def test_get_local_package_info_with_dependencies(self, mock_metadata, mock_version):
        """Test getting package info with dependencies."""
        mock_version.return_value = "2.25.0"
        
        mock_md = Mock()
        mock_md.get.return_value = ""
        mock_md.get_all.return_value = [
            "urllib3>=1.21.1,<1.27",
            "certifi>=2017.4.17"
        ]
        mock_md.get_payload.return_value = ""
        mock_metadata.return_value = mock_md
        
        info = self.extractor.get_local_package_info("requests")
        
        assert len(info.dependencies) == 2
        assert info.dependencies[0].name == "urllib3"
        assert info.dependencies[0].version_spec in [">=1.21.1,<1.27", "<1.27,>=1.21.1"]
        assert info.dependencies[1].name == "certifi"


class TestPyPIClient:
    """Test the PyPIClient class."""

    def setup_method(self):
        self.client = PyPIClient(timeout=5.0)

    def test_init_with_custom_timeout(self):
        """Test client initialization with custom timeout."""
        client = PyPIClient(timeout=30.0)
        # httpx.Timeout object has individual timeout properties
        assert client._client.timeout.connect == 30.0
        assert client._client.timeout.read == 30.0

    @patch('httpx.Client.get')
    def test_get_json_success(self, mock_get):
        """Test successful JSON response."""
        mock_response = Mock()
        mock_response.json.return_value = {"name": "requests", "version": "2.25.0"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.client._get_json("https://pypi.org/pypi/requests/json")
        
        assert result == {"name": "requests", "version": "2.25.0"}
        mock_response.raise_for_status.assert_called_once()

    @patch('httpx.Client.get')
    def test_get_json_http_error(self, mock_get):
        """Test handling of HTTP errors."""
        mock_get.side_effect = httpx.HTTPStatusError("404 Not Found", request=Mock(), response=Mock())
        
        with pytest.raises(NetworkError, match="PyPI request failed"):
            self.client._get_json("https://pypi.org/pypi/nonexistent/json")

    @patch('httpx.Client.get')
    def test_get_json_network_error(self, mock_get):
        """Test handling of network errors."""
        mock_get.side_effect = httpx.ConnectError("Connection failed")
        
        with pytest.raises(NetworkError, match="PyPI request failed"):
            self.client._get_json("https://pypi.org/pypi/requests/json")

    def test_get_project(self):
        """Test get_project method."""
        with patch.object(self.client, '_get_json') as mock_get_json:
            mock_get_json.return_value = {"info": {"name": "requests"}}
            
            result = self.client.get_project("requests")
            
            assert result == {"info": {"name": "requests"}}
            mock_get_json.assert_called_once_with(PYPI_JSON.format(name="requests"))

    def test_get_release(self):
        """Test get_release method."""
        with patch.object(self.client, '_get_json') as mock_get_json:
            mock_get_json.return_value = {"info": {"name": "requests", "version": "2.25.0"}}
            
            result = self.client.get_release("requests", "2.25.0")
            
            assert result == {"info": {"name": "requests", "version": "2.25.0"}}
            expected_url = "https://pypi.org/pypi/requests/2.25.0/json"
            mock_get_json.assert_called_once_with(expected_url)

    @patch('httpx.Client.get')
    def test_search_success(self, mock_get):
        """Test successful package search."""
        html_content = '''
        <html>
            <a class="package-snippet" href="/project/requests/">requests</a>
            <a class="package-snippet" href="/project/httpx/">httpx</a>
        </html>
        '''
        
        mock_response = Mock()
        mock_response.text = html_content
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        results = self.client.search("http client", limit=5)
        
        assert results == ["requests", "httpx"]
        mock_get.assert_called_once_with(PYPI_SEARCH_HTML, params={"q": "http client"})

    @patch('httpx.Client.get')
    def test_search_with_limit(self, mock_get):
        """Test search respects limit parameter."""
        html_content = '''
        <html>
            <a class="package-snippet" href="/project/pkg1/">pkg1</a>
            <a class="package-snippet" href="/project/pkg2/">pkg2</a>
            <a class="package-snippet" href="/project/pkg3/">pkg3</a>
        </html>
        '''
        
        mock_response = Mock()
        mock_response.text = html_content
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        results = self.client.search("test", limit=2)
        
        assert len(results) == 2
        assert results == ["pkg1", "pkg2"]

    @patch('httpx.Client.get')
    def test_search_network_error(self, mock_get):
        """Test search handling network errors."""
        mock_get.side_effect = httpx.ConnectError("Connection failed")
        
        with pytest.raises(NetworkError, match="PyPI search failed"):
            self.client.search("test")


class TestPackageManager:
    """Test the PackageManager class."""

    def setup_method(self):
        self.mock_client = Mock(spec=PyPIClient)
        self.mock_local = Mock(spec=LocalMetadataExtractor)
        self.manager = PackageManager(client=self.mock_client, local=self.mock_local)

    def test_init_with_defaults(self):
        """Test PackageManager initialization with default dependencies."""
        manager = PackageManager()
        assert manager.client is not None
        assert manager.local is not None

    def test_choose_version_latest_non_yanked(self):
        """Test _choose_version selects latest non-yanked version."""
        releases = {
            "1.0.0": [{"yanked": False}],
            "2.0.0": [{"yanked": False}],
            "1.5.0": [{"yanked": True}]
        }
        
        result = self.manager._choose_version(releases, None)
        
        assert result == "2.0.0"

    def test_choose_version_with_spec(self):
        """Test _choose_version respects version specifier."""
        releases = {
            "1.0.0": [{"yanked": False}],
            "2.0.0": [{"yanked": False}],
            "3.0.0": [{"yanked": False}]
        }
        spec = SpecifierSet(">=1.0,<2.0")
        
        result = self.manager._choose_version(releases, spec)
        
        assert result == "1.0.0"

    def test_parse_requires_dist(self):
        """Test _parse_requires_dist method."""
        requires = [
            "urllib3>=1.21.1,<1.27",
            "certifi>=2017.4.17",
            "invalid requirement with spaces"  # Should be skipped
        ]
        
        deps = self.manager._parse_requires_dist(requires)
        
        assert len(deps) == 2
        assert deps[0].name == "urllib3"
        # packaging library may reorder specifiers
        assert deps[0].version_spec in [">=1.21.1,<1.27", "<1.27,>=1.21.1"]
        assert deps[1].name == "certifi"

    def test_get_package_info_local_first(self):
        """Test get_package_info prefers local installation."""
        # Setup local package
        local_info = PackageInfo(
            name="requests",
            version="2.25.0",
            description="Local install"
        )
        self.mock_local.is_package_installed.return_value = True
        self.mock_local.get_local_package_info.return_value = local_info
        
        result = self.manager.get_package_info("requests")
        
        assert result == local_info
        self.mock_local.is_package_installed.assert_called_once_with("requests")
        self.mock_client.get_project.assert_not_called()

    def test_get_package_info_pypi_fallback(self):
        """Test get_package_info falls back to PyPI."""
        # No local package
        self.mock_local.is_package_installed.return_value = False
        
        # Mock PyPI response
        pypi_data = {
            "info": {
                "name": "requests",
                "version": "2.25.0",
                "summary": "HTTP library",
                "author": "Kenneth Reitz"
            },
            "releases": {
                "2.25.0": [{"yanked": False, "upload_time_iso_8601": "2021-01-01T00:00:00Z"}]
            }
        }
        self.mock_client.get_project.return_value = pypi_data
        self.mock_client.get_release.return_value = {"info": pypi_data["info"]}
        
        result = self.manager.get_package_info("requests")
        
        assert result.name == "requests"
        assert result.version == "2.25.0"
        assert result.description == "HTTP library"
        assert result.author == "Kenneth Reitz"

    def test_get_package_info_with_version_spec(self):
        """Test get_package_info with version specifier."""
        # Local version doesn't match spec
        local_info = PackageInfo(name="requests", version="1.0.0")
        self.mock_local.is_package_installed.return_value = True
        self.mock_local.get_local_package_info.return_value = local_info
        
        # PyPI has matching version
        pypi_data = {
            "info": {"name": "requests", "version": "2.25.0"},
            "releases": {"2.25.0": [{"yanked": False}]}
        }
        self.mock_client.get_project.return_value = pypi_data
        self.mock_client.get_release.return_value = {"info": pypi_data["info"]}
        
        result = self.manager.get_package_info("requests", version_spec=">=2.0")
        
        assert result.version == "2.25.0"

    def test_search_packages(self):
        """Test search_packages method."""
        # Mock search results
        self.mock_client.search.return_value = ["requests", "httpx"]
        
        # Mock package info for each result
        def mock_get_project(name):
            return {
                "info": {
                    "name": name,
                    "summary": f"{name} description",
                    "version": "1.0.0",
                    "author": "Test Author"
                }
            }
        
        self.mock_client.get_project.side_effect = mock_get_project
        
        results = self.manager.search_packages("http client", limit=5)
        
        assert len(results) == 2
        assert results[0].name == "requests"
        assert results[0].description == "requests description"
        assert results[1].name == "httpx"

    def test_search_packages_with_errors(self):
        """Test search_packages handles individual package errors."""
        self.mock_client.search.return_value = ["requests", "broken-pkg"]
        
        def mock_get_project(name):
            if name == "broken-pkg":
                raise NetworkError("Package not found")
            return {"info": {"name": name, "summary": "Description"}}
        
        self.mock_client.get_project.side_effect = mock_get_project
        
        results = self.manager.search_packages("test")
        
        # Should only return successful results
        assert len(results) == 1
        assert results[0].name == "requests"

    def test_check_compatibility_no_conflicts(self):
        """Test check_compatibility with no conflicts."""
        existing = [
            Dependency(name="requests", version_spec=">=2.0"),
            Dependency(name="urllib3", version_spec=">=1.21")
        ]
        
        # Mock PyPI responses showing compatible versions exist
        def mock_get_project(name):
            return {
                "releases": {
                    "2.25.0": [{"yanked": False}],
                    "1.26.0": [{"yanked": False}]
                }
            }
        
        self.mock_client.get_project.side_effect = mock_get_project
        
        result = self.manager.check_compatibility(existing, "httpx", ">=0.27")
        
        assert result["conflicts"] == []

    def test_check_compatibility_with_conflicts(self):
        """Test check_compatibility detects conflicts."""
        existing = [Dependency(name="requests", version_spec=">=3.0")]
        
        # Mock PyPI response showing no version >= 3.0 exists
        self.mock_client.get_project.return_value = {
            "releases": {
                "2.25.0": [{"yanked": False}],
                "2.26.0": [{"yanked": False}]
            }
        }
        
        result = self.manager.check_compatibility(existing, "requests", ">=3.0")
        
        assert len(result["conflicts"]) == 1
        assert result["conflicts"][0]["package"] == "requests"

    def test_get_latest_version(self):
        """Test get_latest_version method."""
        pypi_data = {
            "info": {"name": "requests", "version": "2.25.0"},
            "releases": {
                "2.24.0": [{"yanked": False}],
                "2.25.0": [{"yanked": False}],
                "2.26.0rc1": [{"yanked": False}]  # prerelease
            }
        }
        self.mock_client.get_project.return_value = pypi_data
        
        result = self.manager.get_latest_version("requests")
        
        assert result["name"] == "requests"
        assert result["version"] == "2.25.0"
        assert result["is_prerelease"] is False
        assert result["source"] == "pypi"

    def test_get_latest_version_with_prerelease(self):
        """Test get_latest_version including prereleases."""
        pypi_data = {
            "info": {"name": "requests"},
            "releases": {
                "2.25.0": [{"yanked": False}],
                "2.26.0rc1": [{"yanked": False}]
            }
        }
        self.mock_client.get_project.return_value = pypi_data
        
        result = self.manager.get_latest_version("requests", allow_prerelease=True)
        
        assert result["version"] == "2.26.0rc1"
        assert result["is_prerelease"] is True

    def test_get_latest_version_all_yanked(self):
        """Test get_latest_version when all versions are yanked."""
        pypi_data = {
            "info": {"name": "requests", "version": "2.25.0"},
            "releases": {
                "2.25.0": [{"yanked": True}]
            }
        }
        self.mock_client.get_project.return_value = pypi_data
        
        result = self.manager.get_latest_version("requests")
        
        # Should fall back to info version
        assert result["version"] == "2.25.0"