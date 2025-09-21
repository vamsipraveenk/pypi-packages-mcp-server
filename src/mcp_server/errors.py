class MCPServerError(Exception):
    pass

class NetworkError(MCPServerError):
    pass

class FileSystemError(MCPServerError):
    pass

class ParsingError(MCPServerError):
    pass
