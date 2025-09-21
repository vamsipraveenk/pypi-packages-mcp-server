# src/mcp_server/server.py
from __future__ import annotations

import argparse
import os
from typing import Optional, List, Dict, Any, Annotated

from mcp.server.fastmcp import FastMCP

from .project_analyzer import ProjectAnalyzer
from .package_manager import PackageManager
from .utils import to_serializable

# Server instance
mcp = FastMCP("Python Package MCP Server")

# Singletons for simple stateless server behavior
_analyzer = ProjectAnalyzer()
_pkg = PackageManager()


@mcp.tool(
    description=(
        "Scan a Python project for dependency files and return parsed dependencies. "
        "Understands requirements.txt, pyproject.toml (PEP 621 + optional-dependencies), "
        "Pipfile, and a basic install_requires[] in setup.py. Results auto-refresh when "
        "the files change (mtime-based)."
    )
)
def analyze_project_dependencies(
    project_path: Annotated[Optional[str], "Absolute/relative path to the project root. Defaults to current working directory."] = None,
) -> Dict[str, Any]:
    """
    Analyze a local Python project and extract declared dependencies.

    Args:
      project_path: Path to the project directory (default: CWD).

    Returns:
      ProjectInfo JSON:
      {
        "project_path": str,
        "dependency_files": [str, ...],
        "dependencies": [
          {"name": str, "version_spec": str, "extras": [str], "source_file": str, "is_dev_dependency": bool},
          ...
        ]
      }
    """
    path = project_path or os.getcwd()
    info = _analyzer.analyze_project(path)
    return to_serializable(info)


@mcp.tool(
    description=(
        "Get metadata for a package from the local environment (importlib.metadata) "
        "or fall back to PyPI JSON. Returns short summary plus README long_description "
        "and long_description_content_type when available. If a version specifier is "
        "supplied, the returned version will satisfy it when possible.  "
        "Use this tool to answer questions about a package's functionality, author, license, and more."
    )
)
def get_package_metadata(
    package_name: Annotated[str, "Package name on PyPI or installed locally (e.g., 'requests')."],
    version_spec: Annotated[Optional[str], "Optional PEP 440 specifier string, e.g., '>=2.0,<3'."] = None,
) -> Dict[str, Any]:
    """
    Retrieve package metadata (local-first, PyPI fallback).

    Returns:
      PackageInfo JSON + "install_hint"
    """
    info = _pkg.get_package_info(package_name, version_spec=version_spec)
    d = to_serializable(info)
    d["install_hint"] = f"pip install {package_name}{version_spec or ''}"
    return d


@mcp.tool(
    description=(
        "Search PyPI for packages by keywords or approximate names. "
        "Best-effort HTML search (no public PyPI JSON search API). "
        "Returns compact results (name, description, version, author). "
        "If zero results and the query looks like an exact name, it tries a direct metadata lookup."
    )
)
def search_packages(
    query: Annotated[str, "Free-text keywords or a package name (e.g., 'http client' or 'pytm')."],
    limit: Annotated[int, "Maximum number of results to return."] = 10,
    python_version: Annotated[Optional[str], "Optional Python version hint like '3.11'. Not strict."] = None,
) -> List[Dict[str, Any]]:
    """
    Search PyPI by functionality/keywords and return lightweight matches.

    Returns:
      [{"name": str, "description": str, "version": str, "author": str}, ...]
    """
    results = _pkg.search_packages(query, limit=limit, python_version=python_version)

    # Fallback: if search yields nothing, try an exact-name info fetch
    if not results and query and query.strip():
        q = query.strip()
        try:
            meta = _pkg.get_package_info(q)
            results = [  # type: ignore[assignment]
                {
                    "name": meta.name,
                    "description": meta.description,
                    "version": meta.version,
                    "author": meta.author,
                }
            ]
        except Exception:
            pass

    return [to_serializable(r) for r in results]


@mcp.tool(
    description=(
        "Check whether adding a new package (and optional version constraint) would "
        "conflict with the project's existing declared constraints. Reports any packages "
        "for which no single release satisfies all constraints."
    )
)
def check_package_compatibility(
    new_package: Annotated[str, "Package you want to add to the project (e.g., 'httpx')."],
    version_spec: Annotated[Optional[str], "Optional PEP 440 specifier for the candidate (e.g., '>=0.27')."] = None,
    project_path: Annotated[Optional[str], "Project root path. Defaults to current working directory."] = None,
) -> Dict[str, Any]:
    """
    Validate a candidate package/version against current project constraints.

    Returns:
      {"conflicts": [{"package": str, "reason": str, "constraints": [str, ...]}, ...]}
    """
    path = project_path or os.getcwd()
    info = _analyzer.analyze_project(path)
    out = _pkg.check_compatibility(info.dependencies, new_package, version_spec)
    return to_serializable(out)


@mcp.tool(
    description=(
        "Return the latest available version of a package on PyPI. "
        "By default prereleases are skipped; set allow_prerelease=True to include them."
    )
)
def get_latest_version(
    package_name: Annotated[str, "Package name on PyPI (e.g., 'pytm')."],
    allow_prerelease: Annotated[bool, "Include prerelease versions if True."] = False,
) -> Dict[str, Any]:
    """
    Get the latest (non-yanked) version string for a package from PyPI.

    Returns:
      {"name": str, "version": str, "is_prerelease": bool, "source": "pypi"}
    """
    latest = _pkg.get_latest_version(package_name, allow_prerelease=allow_prerelease)
    return to_serializable(latest)


def main():
    parser = argparse.ArgumentParser(description="Run the Python Package MCP Server")
    parser.add_argument(
        "transport",
        nargs="?",
        default="stdio",
        help="Transport to run (stdio or streamable-http)",
    )
    args = parser.parse_args()
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()