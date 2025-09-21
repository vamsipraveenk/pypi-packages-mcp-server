from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

@dataclass
class Dependency:
    name: str
    version_spec: str = ""
    extras: List[str] = field(default_factory=list)
    source_file: str = ""
    is_dev_dependency: bool = False

@dataclass
class PackageInfo:
    # Core
    name: str
    version: str = ""
    description: str = ""  # short summary
    # NEW: README / long description (entire body text)
    long_description: str = ""
    long_description_content_type: str = ""  # e.g., "text/markdown", "text/x-rst"

    # Metadata
    author: str = ""
    license: str = ""
    homepage: str = ""
    repository: str = ""
    keywords: List[str] = field(default_factory=list)

    # Relationships / constraints
    dependencies: List[Dependency] = field(default_factory=list)
    python_requires: str = ""

    # Timestamps
    last_updated: Optional[datetime] = None

@dataclass
class PackageSearchResult:
    name: str
    description: str = ""
    version: str = ""
    author: str = ""

@dataclass
class ProjectInfo:
    project_path: str
    dependency_files: List[str] = field(default_factory=list)
    dependencies: List[Dependency] = field(default_factory=list)