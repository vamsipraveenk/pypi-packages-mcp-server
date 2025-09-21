from __future__ import annotations
import ast
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from packaging.requirements import Requirement

from .models import Dependency, ProjectInfo
from .errors import FileSystemError, ParsingError

try:
    import tomllib  # py311+
except Exception:  # pragma: no cover
    import tomli as tomllib  # type: ignore

DEPENDENCY_FILE_NAMES = [
    "requirements.txt",
    "pyproject.toml",
    "Pipfile",
    "setup.py",
]

@dataclass
class _CacheEntry:
    mtimes: Dict[str, float] = field(default_factory=dict)
    dependencies: List[Dependency] = field(default_factory=list)
    files: List[str] = field(default_factory=list)

class DependencyParser:
    def parse_requirements_txt(self, file_path: str) -> List[Dependency]:
        deps: List[Dependency] = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    try:
                        req = Requirement(line)
                    except Exception as e:
                        raise ParsingError(f"Invalid requirement line '{line}': {e}") from e
                    deps.append(Dependency(
                        name=req.name,
                        version_spec=str(req.specifier) if req.specifier else "",
                        extras=sorted(list(req.extras)) if req.extras else [],
                        source_file=file_path,
                        is_dev_dependency=False,
                    ))
        except FileNotFoundError:
            raise FileSystemError(f"File not found: {file_path}")
        return deps

    def parse_pyproject_toml(self, file_path: str) -> List[Dependency]:
        path = Path(file_path)
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            raise ParsingError(f"Failed to parse pyproject.toml: {e}") from e

        deps: List[Dependency] = []
        proj = data.get("project", {})
        for entry in proj.get("dependencies", []) or []:
            req = Requirement(entry)
            deps.append(Dependency(
                name=req.name,
                version_spec=str(req.specifier) if req.specifier else "",
                extras=sorted(list(req.extras)) if req.extras else [],
                source_file=file_path,
                is_dev_dependency=False,
            ))

        opt = proj.get("optional-dependencies", {}) or {}
        for group, entries in opt.items():
            is_dev = group.lower() in {"dev", "test", "tests", "lint", "doc", "docs", "build"}
            for entry in entries or []:
                req = Requirement(entry)
                deps.append(Dependency(
                    name=req.name,
                    version_spec=str(req.specifier) if req.specifier else "",
                    extras=sorted(list(req.extras)) if req.extras else [],
                    source_file=file_path,
                    is_dev_dependency=is_dev,
                ))
        return deps

    def parse_pipfile(self, file_path: str) -> List[Dependency]:
        # Treat Pipfile as TOML and read [packages] and [dev-packages]
        path = Path(file_path)
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            raise ParsingError(f"Failed to parse Pipfile: {e}") from e

        deps: List[Dependency] = []
        for section, is_dev in [("packages", False), ("dev-packages", True)]:
            for name, spec in (data.get(section) or {}).items():
                version = ""
                if isinstance(spec, str):
                    version = "" if spec.strip() == "*" else spec
                elif isinstance(spec, dict):
                    version = spec.get("version", "")
                req_str = f"{name}{version}"
                try:
                    req = Requirement(req_str)
                except Exception:
                    req = Requirement(name)
                deps.append(Dependency(
                    name=req.name,
                    version_spec=str(req.specifier) if req.specifier else "",
                    extras=sorted(list(req.extras)) if req.extras else [],
                    source_file=file_path,
                    is_dev_dependency=is_dev,
                ))
        return deps

    def parse_setup_py(self, file_path: str) -> List[Dependency]:
        # Very basic static extraction of install_requires = [...] from setup.py
        try:
            text = Path(file_path).read_text(encoding="utf-8")
            tree = ast.parse(text, filename=file_path)
        except Exception as e:
            raise ParsingError(f"Failed to parse setup.py: {e}") from e

        install_requires: List[str] = []
        class Finder(ast.NodeVisitor):
            def visit_Call(self, node):  # look for setup(... install_requires=[...])
                try:
                    fn = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                    if isinstance(fn, str) and fn.lower() == "setup":
                        for kw in node.keywords or []:
                            if kw.arg == "install_requires" and hasattr(kw.value, "elts"):
                                for elt in kw.value.elts:
                                    if getattr(elt, "value", None) and isinstance(elt.value, str):
                                        install_requires.append(elt.value)
                except Exception:
                    pass
                self.generic_visit(node)
        Finder().visit(tree)

        deps: List[Dependency] = []
        for entry in install_requires:
            try:
                req = Requirement(entry)
            except Exception:
                continue
            deps.append(Dependency(
                name=req.name,
                version_spec=str(req.specifier) if req.specifier else "",
                extras=sorted(list(req.extras)) if req.extras else [],
                source_file=file_path,
                is_dev_dependency=False,
            ))
        return deps

class ProjectAnalyzer:
    def __init__(self):
        self._cache: Dict[str, _CacheEntry] = {}
        self._parser = DependencyParser()

    def _scan_files(self, project_path: str) -> List[str]:
        root = Path(project_path or ".").resolve()
        found = []
        for name in DEPENDENCY_FILE_NAMES:
            p = root / name
            if p.exists():
                found.append(str(p))
        return found

    def analyze_project(self, project_path: str) -> ProjectInfo:
        files = self._scan_files(project_path)
        key = str(Path(project_path or '.').resolve())
        cached = self._cache.get(key) or _CacheEntry()
        mtimes = {f: os.path.getmtime(f) for f in files}
        needs_refresh = (files != cached.files) or any(cached.mtimes.get(f) != mtimes.get(f) for f in set(files) | set(cached.mtimes.keys()))

        if needs_refresh:
            deps: List[Dependency] = []
            for f in files:
                try:
                    if f.endswith("requirements.txt"):
                        deps.extend(self._parser.parse_requirements_txt(f))
                    elif f.endswith("pyproject.toml"):
                        deps.extend(self._parser.parse_pyproject_toml(f))
                    elif f.endswith("Pipfile"):
                        deps.extend(self._parser.parse_pipfile(f))
                    elif f.endswith("setup.py"):
                        deps.extend(self._parser.parse_setup_py(f))
                except (FileSystemError, ParsingError) as e:
                    deps.append(Dependency(name="__parse_error__", version_spec=str(e), source_file=f))
            cached = _CacheEntry(mtimes=mtimes, dependencies=deps, files=files)
            self._cache[key] = cached

        return ProjectInfo(project_path=key, dependency_files=files, dependencies=self._cache[key].dependencies if key in self._cache else [])

    def get_dependencies(self) -> List[Dependency]:
        if not self._cache:
            return []
        last_key = list(self._cache.keys())[-1]
        return self._cache[last_key].dependencies
