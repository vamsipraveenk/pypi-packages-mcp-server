from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import importlib.metadata as ilmd

import httpx
from packaging.requirements import Requirement
from packaging.version import Version, InvalidVersion
from packaging.specifiers import SpecifierSet
from bs4 import BeautifulSoup

from .models import Dependency, PackageInfo, PackageSearchResult
from .errors import NetworkError

# PyPI endpoints
PYPI_JSON = "https://pypi.org/pypi/{name}/json"
PYPI_JSON_RELEASE = "https://pypi.org/pypi/{name}/{version}/json"
# IMPORTANT: use the base search path and pass ?q= via httpx params
PYPI_SEARCH_HTML = "https://pypi.org/search/"


class LocalMetadataExtractor:
    """
    Local Python environment metadata reader using importlib.metadata.
    Used first (local-first) before hitting the PyPI network fallback.
    """

    def is_package_installed(self, package_name: str) -> bool:
        try:
            ilmd.version(package_name)
            return True
        except ilmd.PackageNotFoundError:
            return False

    def get_local_package_info(self, package_name: str) -> PackageInfo:
        """
        Return metadata for an installed package.
        Also extracts the long description from the METADATA payload body.
        """
        try:
            version = ilmd.version(package_name)
            md = ilmd.metadata(package_name)  # email.message.Message
        except ilmd.PackageNotFoundError as e:
            raise NetworkError(f"Package not installed: {package_name}") from e

        # Requires-Dist -> dependencies
        requires = (md.get_all("Requires-Dist") or []) if hasattr(md, "get_all") else []
        deps: List[Dependency] = []
        for r in requires:
            try:
                req = Requirement(r)
                deps.append(
                    Dependency(
                        name=req.name,
                        version_spec=str(req.specifier),
                        extras=sorted(list(req.extras)),
                    )
                )
            except Exception:
                continue

        # Short summary
        summary = md.get("Summary", "") or ""

        # Long description lives in the payload/body of the METADATA file
        # (PEP 566). importlib.metadata returns an email.message.Message.
        long_description = ""
        try:
            payload = md.get_payload()
            if isinstance(payload, list):
                long_description = "".join(str(p) for p in payload if p)
            elif isinstance(payload, (str, bytes)):
                long_description = payload.decode() if isinstance(payload, bytes) else payload
        except Exception:
            pass

        long_description_content_type = md.get("Description-Content-Type", "") or ""

        # Keywords
        keywords: List[str] = []
        if md.get("Keywords"):
            keywords = [k.strip() for k in md.get("Keywords", "").split(",") if k.strip()]

        return PackageInfo(
            name=md.get("Name", package_name),
            version=version,
            description=summary,
            long_description=long_description,
            long_description_content_type=long_description_content_type,
            author=md.get("Author", "") or md.get("Author-email", ""),
            license=md.get("License", ""),
            homepage=md.get("Home-page", ""),
            repository="",
            keywords=keywords,
            dependencies=deps,
            python_requires=md.get("Requires-Python", ""),
            last_updated=None,
        )


class PyPIClient:
    """Thin HTTP client for the PyPI JSON API and HTML search page."""

    def __init__(self, timeout: float = 10.0):
        self._client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": "pypi-mcp-server/0.1"},
        )

    def _get_json(self, url: str) -> Dict[str, Any]:
        try:
            r = self._client.get(url, follow_redirects=True)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            raise NetworkError(f"PyPI request failed: {e}") from e

    def get_project(self, name: str) -> Dict[str, Any]:
        return self._get_json(PYPI_JSON.format(name=name))

    def get_release(self, name: str, version: str) -> Dict[str, Any]:
        return self._get_json(PYPI_JSON_RELEASE.format(name=name, version=version))

    def search(self, query: str, limit: int = 10) -> List[str]:
        """
        Best-effort HTML search on pypi.org. Returns a list of package names.
        """
        try:
            r = self._client.get(PYPI_SEARCH_HTML, params={"q": (query or "").strip()})
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            names: List[str] = []
            for a in soup.select("a.package-snippet"):
                href = a.get("href") or ""
                m = re.search(r"/project/([^/]+)/", href)
                if m:
                    names.append(m.group(1))
                if len(names) >= limit:
                    break
            return names
        except Exception as e:
            raise NetworkError(f"PyPI search failed: {e}") from e


class PackageManager:
    """
    Main entry point for package operations: local metadata, PyPI JSON,
    best-effort search, compatibility checks, and latest version lookup.
    """

    def __init__(self, client: Optional[PyPIClient] = None, local: Optional[LocalMetadataExtractor] = None):
        self.client = client or PyPIClient()
        self.local = local or LocalMetadataExtractor()

    def _choose_version(self, releases: Dict[str, Any], spec: Optional[SpecifierSet]) -> str:
        """Choose the latest non-yanked version that satisfies `spec` (if any)."""
        versions: List[Version] = []
        for v in releases.keys():
            try:
                versions.append(Version(v))
            except InvalidVersion:
                continue

        versions.sort(reverse=True)

        for v in versions:
            vstr = str(v)
            if spec and v not in spec:
                continue
            files = releases.get(vstr, [])
            if any(not f.get("yanked", False) for f in files):
                return vstr

        return str(versions[0]) if versions else ""

    def _parse_requires_dist(self, requires: List[str]) -> List[Dependency]:
        deps: List[Dependency] = []
        for r in requires or []:
            try:
                req = Requirement(r)
                deps.append(
                    Dependency(name=req.name, version_spec=str(req.specifier), extras=sorted(list(req.extras)))
                )
            except Exception:
                # Skip invalid requirements instead of creating error dependencies
                continue
        return deps

    def get_package_info(self, package_name: str, version_spec: Optional[str] = None) -> PackageInfo:
        """
        Get metadata for a package, preferring local install; fall back to PyPI.

        If `version_spec` is provided, we ensure the selected version satisfies it,
        otherwise we pick an appropriate latest non-yanked release on PyPI.

        Returns PackageInfo including:
          - description (summary)
          - long_description (README body) + long_description_content_type
        """
        # Local-first
        if self.local.is_package_installed(package_name):
            info = self.local.get_local_package_info(package_name)
            if version_spec:
                try:
                    if Version(info.version) in SpecifierSet(version_spec):
                        return info
                except Exception:
                    # fall through to PyPI
                    pass
            else:
                # No version spec, return local info directly
                return info

        # PyPI fallback
        data = self.client.get_project(package_name)
        info = data.get("info", {}) or {}
        releases = data.get("releases", {}) or {}

        spec = SpecifierSet(version_spec) if version_spec else None
        chosen_version = self._choose_version(releases, spec)

        if chosen_version:
            rel = self.client.get_release(package_name, chosen_version)
            info = rel.get("info", info)
            urls = rel.get("urls", [])
        else:
            urls = data.get("urls", [])

        # newest file timestamp as last_updated
        last_up = None
        for f in urls:
            ts = f.get("upload_time_iso_8601") or f.get("upload_time")
            if ts:
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if not last_up or dt > last_up:
                        last_up = dt.astimezone(timezone.utc)
                except Exception:
                    pass

        deps = self._parse_requires_dist(info.get("requires_dist", []) or [])
        keywords: List[str] = []
        kw = info.get("keywords", "")
        if isinstance(kw, str) and kw:
            keywords = [k.strip() for k in kw.split(",") if k.strip()]

        # Try to extract a repository/source link
        repo = ""
        purls = info.get("project_urls") or {}
        for key in ("Source", "Repository", "Code", "Homepage"):
            if key in purls:
                repo = purls[key]
                break

        # Short vs long description from PyPI JSON
        summary = info.get("summary") or ""
        long_description = info.get("description") or ""
        long_description_ct = info.get("description_content_type") or ""

        return PackageInfo(
            name=info.get("name") or package_name,
            version=info.get("version") or chosen_version or "",
            description=summary,
            long_description=long_description,
            long_description_content_type=long_description_ct,
            author=info.get("author") or info.get("maintainer") or "",
            license=info.get("license") or "",
            homepage=purls.get("Homepage", info.get("home_page") or ""),
            repository=repo,
            keywords=keywords,
            dependencies=deps,
            python_requires=info.get("requires_python") or "",
            last_updated=last_up,
        )

    def search_packages(self, query: str, limit: int = 10, python_version: Optional[str] = None) -> List[PackageSearchResult]:
        """
        Search PyPI by functionality keywords. Returns lightweight results.
        NOTE: PyPI has no public JSON search API; this scrapes HTML and then
        enriches each name via the JSON API.
        """
        names = self.client.search(query, limit=limit)
        results: List[PackageSearchResult] = []
        for name in names:
            try:
                data = self.client.get_project(name)
                info = data.get("info", {}) or {}
                results.append(
                    PackageSearchResult(
                        name=info.get("name") or name,
                        description=info.get("summary") or "",
                        version=info.get("version") or "",
                        author=info.get("author") or info.get("maintainer") or "",
                    )
                )
            except Exception:
                continue
        return results

    def check_compatibility(
        self,
        existing: List[Dependency],
        new_name: str,
        new_spec: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Very basic constraint intersection: for each package, check if there exists
        any released version that satisfies all collected specifiers. If none exist,
        report a conflict entry with the constraints.
        """
        conflicts: List[Dict[str, Any]] = []

        # Gather all constraints per package (declared + candidate)
        all_specs: Dict[str, List[SpecifierSet]] = {}
        for d in existing:
            all_specs.setdefault(d.name, []).append(SpecifierSet(d.version_spec) if d.version_spec else SpecifierSet())
        all_specs.setdefault(new_name, []).append(SpecifierSet(new_spec) if new_spec else SpecifierSet())

        for name, specs in all_specs.items():
            try:
                data = self.client.get_project(name)
            except Exception:
                # Skip packages we can't fetch
                continue

            candidates: List[Version] = []
            for v in (data.get("releases") or {}).keys():
                try:
                    candidates.append(Version(v))
                except Exception:
                    continue
            candidates.sort(reverse=True)

            def ok(ver: Version) -> bool:
                return all(ver in s for s in specs if s)

            if candidates and not any(ok(v) for v in candidates):
                conflicts.append(
                    {
                        "package": name,
                        "reason": "No version satisfies all constraints",
                        "constraints": [str(s) for s in specs],
                    }
                )

        return {"conflicts": conflicts}

    def get_latest_version(self, package_name: str, allow_prerelease: bool = False) -> Dict[str, Any]:
        """
        Return the latest available non-yanked version from PyPI.
        Set allow_prerelease=True to consider prereleases (e.g., 2.0.0rc1).
        """
        data = self.client.get_project(package_name)
        info = data.get("info", {}) or {}
        releases = data.get("releases", {}) or {}

        versions: List[Version] = []
        for v, files in releases.items():
            try:
                ver = Version(v)
            except InvalidVersion:
                continue
            if not allow_prerelease and ver.is_prerelease:
                continue
            if files and not any(not f.get("yanked", False) for f in files):
                # all files yanked for this version
                continue
            versions.append(ver)

        versions.sort(reverse=True)
        latest_str = str(versions[0]) if versions else (info.get("version") or "")

        is_pre = False
        try:
            is_pre = Version(latest_str).is_prerelease
        except Exception:
            pass

        return {
            "name": info.get("name") or package_name,
            "version": latest_str,
            "is_prerelease": is_pre,
            "source": "pypi",
        }
