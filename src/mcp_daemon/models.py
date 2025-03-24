from typing import Dict, Optional, Any
from mcp import ClientSession

class MCPResponse:
    """Standard response format for MCP operations"""
    def __init__(self, status: str, content: Optional[str] = None, error: Optional[str] = None):
        self.status = status
        self.content = content
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        response = {"status": self.status}
        if self.content is not None:
            response["content"] = self.content
        if self.error is not None:
            response["error"] = self.error
        return response

class ServerSession:
    """Wrapper for MCP server sessions"""
    def __init__(self, session: ClientSession, server_type: str):
        self.session = session
        self.server_type = server_type  # 'sse' or 'stdio'
        
    async def close(self):
        """Close the session"""
        # Note: The actual closing of session happens in AsyncExitStack.aclose()
        # This method exists for consistency and potential future expansion
        pass
