# Python Package MCP Server

A Model Context Protocol (MCP) server that provides AI coding agents with comprehensive awareness of Python package ecosystems. It enables:

- **Project Analysis**: Extract and analyze dependencies from `requirements.txt`, `pyproject.toml`, `Pipfile`, and basic `setup.py` files
- **Package Metadata**: Retrieve comprehensive package information from local installations (via `importlib.metadata`) or PyPI (fallback)
- **Package Discovery**: Search PyPI for packages by functionality and keywords (best-effort HTML scraping)
- **Compatibility Checking**: Verify if new packages are compatible with existing project dependencies
- **Version Management**: Get latest package versions with prerelease support

## Features

- **Local-First Strategy**: Checks local installations before hitting PyPI API
- **Comprehensive Error Handling**: Graceful degradation when services are unavailable
- **Structured Logging**: Performance metrics and health monitoring
- **Async Operations**: All I/O operations use async/await for better performance
- **Rich Metadata**: Includes README content, author info, licenses, and more

## Quick Start

### Prerequisites
- Python 3.10 or higher
- Git (for cloning the repository)

### Installation

1. **Clone and navigate to the repository**:
```bash
git clone <repository-url>
cd pypi-mcp-server
```

2. **Create and activate virtual environment**:

**Windows (PowerShell)**:
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Windows (Command Prompt)**:
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

**Mac/Linux**:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. **Install the package in development mode**:
```bash
pip install -e .
```

### Running the Server

**Option 1: Using the convenience scripts**
```bash
# Windows
.\run-mcp.bat

# Mac/Linux
./run-mcp.sh
```

**Option 2: Direct Python execution**
```bash
python -m mcp_server.server stdio
```

**Option 3: Using MCP CLI** (if you have mcp installed globally)
```bash
mcp run -m mcp_server.server
```

### Running Tests

**Windows**:
```cmd
.\run-tests.bat
```

**Manual test execution**:
```bash
# Activate virtual environment first
python -m pytest tests/ -v
```

## MCP Client Configuration

To use this server with an MCP client (like Claude Desktop), add the following configuration:

### For Kiro IDE or other MCP clients

**Windows** (`mcp.json`):
```json
{
  "servers": {
    "pypi-mcp-server": {
      "command": "C:\\path\\to\\your\\pypi-mcp-server\\run-mcp.bat",
      "args": [],
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

**Mac/Linux** (`mcp.json`):
```json
{
  "servers": {
    "pypi-mcp-server": {
      "command": "/path/to/your/pypi-mcp-server/run-mcp.sh",
      "args": [],
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

### For Claude Desktop

**Windows** (`claude_desktop_config.json`):
```json
{
  "servers": {
    "pypi-mcp-server": {
      "command": "D:\\path\\to\\your\\pypi-mcp-server\\run-mcp.bat",
      "args": []
    }
  }
}
```

**Mac/Linux** (`claude_desktop_config.json`):
```json
{
  "servers": {
    "pypi-mcp-server": {
      "command": "/path/to/your/pypi-mcp-server/run-mcp.sh",
      "args": []
    }
  }
}
```

## Available MCP Tools

The server provides the following MCP tools:

### 1. `analyze_project_dependencies`
Analyzes dependency files in a project directory.
- **Parameters**: `project_path` (optional, defaults to current directory)
- **Returns**: Project information with all discovered dependencies
- **Supported files**: `requirements.txt`, `pyproject.toml`, `Pipfile`, `setup.py`

### 2. `get_package_metadata`
Retrieves comprehensive metadata for a Python package.
- **Parameters**: `package_name` (required), `version_spec` (optional)
- **Returns**: Package info including description, author, license, dependencies, README content
- **Strategy**: Checks local installation first, falls back to PyPI

### 3. `search_packages`
Searches PyPI for packages by keywords.
- **Parameters**: `query` (required), `limit` (optional, default 10), `python_version` (optional)
- **Returns**: List of matching packages with names, descriptions, versions, authors
- **Method**: HTML scraping of PyPI search results

### 4. `check_package_compatibility`
Checks if a new package would conflict with existing dependencies.
- **Parameters**: `new_package` (required), `version_spec` (optional), `project_path` (optional)
- **Returns**: Compatibility report with any conflicts found
- **Analysis**: Version constraint intersection checking

### 5. `get_latest_version`
Gets the latest available version of a package from PyPI.
- **Parameters**: `package_name` (required), `allow_prerelease` (optional, default false)
- **Returns**: Latest version info with prerelease flag
- **Filtering**: Excludes yanked releases and prereleases by default

## Usage Examples

Once configured with an MCP client, you can use the tools like this:

```python
# Analyze current project dependencies
analyze_project_dependencies()

# Get metadata for a specific package
get_package_metadata("requests")

# Search for HTTP client packages
search_packages("http client", limit=5)

# Check if adding fastapi would cause conflicts
check_package_compatibility("fastapi", ">=0.100.0")

# Get the latest version of a package
get_latest_version("django")
```

The tools return structured data that AI assistants can use to understand your Python environment and make informed recommendations about package management.

## Development

### Project Structure
```
src/mcp_server/
├── server.py              # Main MCP server implementation
├── package_manager.py     # PyPI client and local metadata extraction
├── project_analyzer.py    # Dependency file parsing
├── models.py             # Data structures
├── utils.py              # Utility functions
└── errors.py             # Custom exceptions
```

### Technical Guidelines
- **Local-First**: Always check local installations before PyPI API calls
- **Async-First**: Use async/await for all I/O operations
- **Error Handling**: Implement comprehensive exception hierarchy
- **Testing**: Use pytest with async support and mock external dependencies

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `python -m pytest tests/ -v`
5. Submit a pull request

## Troubleshooting

### Common Issues

**Import errors**: Make sure you've activated the virtual environment and installed the package with `pip install -e .`

**Permission errors on Windows**: Run PowerShell as Administrator or use Command Prompt

**Tests failing**: Ensure all dependencies are installed and you're in the project root directory

**Server not responding**: The server runs in stdio mode and waits for MCP protocol messages. This is normal behavior.

### Getting Help

If you encounter issues:
1. Check that Python 3.10+ is installed
2. Verify the virtual environment is activated
3. Ensure all dependencies are installed with `pip install -e .`
4. Run tests to verify the installation: `python -m pytest tests/ -v`

## License

MIT License - see LICENSE file for details.
