---
inclusion: always
---

# Project Structure & Architecture Guidelines

## Core Package Organization
The main source code lives in `src/mcp_server/` (not `python_package_mcp_server/` as shown in legacy docs). Key modules:

- `server.py` - Main MCP server implementation and tool handlers
- `analyzers/` - Project dependency analysis (requirements.txt, pyproject.toml)
- `models/` - Data structures for dependencies, packages, and project info
- `package_manager/` - PyPI client and local metadata extraction

## Code Style & Conventions
- Use async/await for all I/O operations (HTTP requests, file operations)
- Follow local-first strategy: check local installations before PyPI API calls
- Implement comprehensive error handling with custom exception hierarchy
- Use structured logging with performance metrics
- All MCP tools should return structured data models, not raw dictionaries

## Architecture Patterns
- **Modular Design**: Clear separation between analyzers, package managers, and MCP server logic
- **Dependency Injection**: Pass dependencies through constructors, avoid global state
- **Error Isolation**: Each module handles its own exceptions with graceful degradation
- **Health Monitoring**: Include performance logging and service availability checks

## File Modification Guidelines
- When adding new MCP tools, implement them in `server.py` following existing patterns
- New data models go in `models/` directory with proper type hints
- Dependency parsing logic belongs in `analyzers/` 
- PyPI interactions should use the existing `pypi_client.py`
- Always add corresponding tests in `tests/` directory

## Testing Requirements
- Use pytest with async support (`pytest-asyncio`)
- Mock external dependencies (PyPI API calls) in unit tests
- Include integration tests for MCP protocol compliance
- Test error scenarios and edge cases (missing files, network failures)

## Entry Points & Scripts
- Main server entry: `src/mcp_server/server.py` 
- Use `run-mcp.bat` or `run-mcp.sh` for development
- Virtual environment recommended: activate with `venv\Scripts\activate` (Windows)