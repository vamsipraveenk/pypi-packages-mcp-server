---
inclusion: always
---

# Python Package MCP Server - Technical Guidelines

## Project Structure
- Main source: `src/mcp_server/` (not `python_package_mcp_server/`)
- Core modules: `server.py`, `analyzers/`, `models/`, `package_manager/`
- Entry point: `src/mcp_server/server.py`
- Tests: `tests/` with pytest and async support

## Architecture Principles
- **Local-First Strategy**: Check local installations via `importlib.metadata` before PyPI API calls
- **Async-First**: Use async/await for all I/O operations (HTTP, file system)
- **Graceful Degradation**: Handle network failures, missing files, and API timeouts elegantly
- **Structured Data**: Return typed Pydantic models from MCP tools, never raw dictionaries
- **Modular Design**: Clear separation between analyzers, package managers, and MCP server logic

## Key Dependencies & Patterns
- **MCP Framework**: `mcp>=1.0.0` for server implementation
- **HTTP Client**: `httpx>=0.25.0` for async PyPI API interactions  
- **Data Models**: Pydantic models for all structured data
- **Error Handling**: Custom exception hierarchy with meaningful error messages
- **Testing**: `pytest` with `pytest-asyncio` for async test support

## Code Style Requirements
- Use comprehensive type hints for all functions (parameters and return values)
- Implement structured logging with performance metrics and timing data
- Mock external dependencies (PyPI API, file system) in unit tests
- Validate all input data and handle edge cases (missing files, network timeouts, malformed data)
- Follow async patterns consistently - no blocking I/O operations
- Use dependency injection pattern - pass dependencies through constructors

## MCP Tool Implementation
- All tools must return structured Pydantic models
- Include comprehensive error handling for each tool
- Log performance metrics (timing, cache hits/misses)
- Support both local metadata and PyPI fallback
- Handle version constraints and compatibility checking

## Development Workflow
```bash
# Setup (Windows)
python -m venv venv
venv\Scripts\activate
pip install -e .

# Testing
.\venv\Scripts\python -m pytest tests/ -v

# Running server
.\venv\Scripts\python -m mcp_server.server
```

## Error Handling Patterns
- Use custom exception hierarchy for different error types
- Always provide meaningful error messages with context
- Log errors with structured data for debugging
- Gracefully degrade when external services are unavailable
- Return partial results when possible rather than failing completely