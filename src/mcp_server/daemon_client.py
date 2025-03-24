import asyncio
import json
import os
import sys
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass

from loguru import logger

@dataclass
class DaemonResponse:
    """Structured response from the MCP daemon server"""
    status: str  # 'success' or 'error'
    content: Optional[Any] = None
    error: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DaemonResponse':
        """
        Create a DaemonResponse instance from the raw dictionary returned by daemon server
        
        Args:
            data (Dict[str, Any]): Response dictionary from daemon server
            
        Returns:
            DaemonResponse: Structured response object
        """
        return cls(
            status=data.get("status", "error"),
            content=data.get("content"),
            error=data.get("error")
        )
        
    def is_success(self) -> bool:
        """
        Check if the response indicates success
        
        Returns:
            bool: True if status is 'success', False otherwise
        """
        return self.status == 'success'
        
    def get_parsed_content(self) -> Any:
        """
        Parse string content as JSON if possible
        
        Returns:
            Any: Parsed JSON content or original content if not JSON
        """
        if not self.content:
            return None
            
        if isinstance(self.content, str):
            try:
                return json.loads(self.content)
            except json.JSONDecodeError:
                return self.content
                
        return self.content
        
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert response to a dictionary (for backward compatibility)
        
        Returns:
            Dict[str, Any]: Dictionary representation of the response
        """
        result = {"status": self.status}
        if self.content is not None:
            result["content"] = self.content
        if self.error is not None:
            result["error"] = self.error
        return result

class MCPDaemonClient:
    """
    Client for communicating with the MCP daemon server.
    Provides interface to execute MCP tools and other operations.
    """
    def __init__(self, socket_path: Optional[str] = None):
        """
        Initialize the client with a socket path.
        
        Args:
            socket_path (Optional[str]): Path to the Unix socket for IPC.
                                        If None, uses default location.
        """
        self.socket_path = socket_path or self._get_default_socket_path()
        self.reader = None
        self.writer = None
        
    def _get_default_socket_path(self) -> str:
        """Get the default socket path based on platform"""
        app_name = "y-cli"
        if sys.platform == "darwin":  # macOS
            base_dir = os.path.expanduser(f"~/Library/Application Support/{app_name}")
        else:  # Linux and others
            base_dir = os.path.expanduser(f"~/.local/share/{app_name}")
        
        return os.path.join(base_dir, "mcp_daemon.sock")
    
    async def connect(self) -> bool:
        """
        Connect to the daemon server.
        
        Returns:
            bool: True if connection successful, False otherwise.
        """
        try:
            if not os.path.exists(self.socket_path):
                logger.error(f"Socket file {self.socket_path} does not exist. "
                          f"Make sure the MCP daemon is running.")
                return False
                
            self.reader, self.writer = await asyncio.open_unix_connection(self.socket_path)
            return True
        except (ConnectionRefusedError, FileNotFoundError) as e:
            logger.error(f"Failed to connect to MCP daemon: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to MCP daemon: {str(e)}")
            return False
    
    async def disconnect(self):
        """Disconnect from the daemon server."""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
            self.writer = None
            self.reader = None
    
    async def _send_request(self, request: Dict[str, Any]) -> DaemonResponse:
        """
        Send a request to the daemon server and get the response.
        
        Args:
            request (Dict[str, Any]): Request data to send.
            
        Returns:
            DaemonResponse: Structured response from the daemon server.
        """
        if not self.writer or not self.reader:
            connected = await self.connect()
            if not connected:
                return DaemonResponse(
                    status="error", 
                    error="Not connected to MCP daemon"
                )
        
        try:
            # Send request
            self.writer.write(json.dumps(request).encode() + b'\n')
            await self.writer.drain()
            
            # Get response
            data = await self.reader.readline()
            if not data:
                return DaemonResponse(
                    status="error", 
                    error="No response from MCP daemon"
                )
            
            # Parse response JSON
            raw_response = json.loads(data.decode())
            return DaemonResponse.from_dict(raw_response)
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from MCP daemon: {str(e)}")
            return DaemonResponse(
                status="error", 
                error=f"Invalid JSON response: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Error communicating with MCP daemon: {str(e)}")
            return DaemonResponse(
                status="error", 
                error=f"Communication error: {str(e)}"
            )
    
    async def execute_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Union[Dict[str, Any], DaemonResponse]:
        """
        Execute an MCP tool via the daemon.
        
        Args:
            server_name (str): Name of the MCP server.
            tool_name (str): Name of the tool to execute.
            arguments (Dict[str, Any]): Arguments for the tool.
            
        Returns:
            Union[Dict[str, Any], DaemonResponse]: Response from the daemon server.
                  Returns DaemonResponse for structured access or Dict for backward compatibility.
        """
        request = {
            "type": "execute_tool",
            "server_name": server_name,
            "tool_name": tool_name,
            "arguments": arguments
        }
        
        response = await self._send_request(request)
        # For backward compatibility, return dict
        return response.to_dict()
    
    async def execute_tool_structured(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> DaemonResponse:
        """
        Execute an MCP tool via the daemon with structured response.
        
        Args:
            server_name (str): Name of the MCP server.
            tool_name (str): Name of the tool to execute.
            arguments (Dict[str, Any]): Arguments for the tool.
            
        Returns:
            DaemonResponse: Structured response from the daemon server.
        """
        request = {
            "type": "execute_tool",
            "server_name": server_name,
            "tool_name": tool_name,
            "arguments": arguments
        }
        
        return await self._send_request(request)
    
    async def extract_tool_use(self, content: str) -> Union[Dict[str, Any], DaemonResponse]:
        """
        Extract MCP tool use details from content.
        
        Args:
            content (str): Content to extract tool use from.
            
        Returns:
            Union[Dict[str, Any], DaemonResponse]: Response with extracted tool details or error.
        """
        request = {
            "type": "extract_tool_use",
            "content": content
        }
        
        response = await self._send_request(request)
        # For backward compatibility
        return response.to_dict()
    
    async def extract_tool_use_structured(self, content: str) -> DaemonResponse:
        """
        Extract MCP tool use details from content with structured response.
        
        Args:
            content (str): Content to extract tool use from.
            
        Returns:
            DaemonResponse: Structured response with extracted tool details or error.
        """
        request = {
            "type": "extract_tool_use",
            "content": content
        }
        
        return await self._send_request(request)
    
    async def list_servers(self) -> List[str]:
        """
        Get a list of connected MCP servers.
        
        Returns:
            List[str]: List of server names.
        """
        request = {
            "type": "list_servers"
        }
        
        response = await self._send_request(request)
        return response.get_parsed_content() if response.is_success() else []
        
    async def list_server_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """
        Get a list of tools for a specific MCP server.
        
        Args:
            server_name (str): Name of the MCP server.
            
        Returns:
            List[Dict[str, Any]]: List of tool information dictionaries.
        """
        request = {
            "type": "list_server_tools",
            "server_name": server_name
        }
        
        response = await self._send_request(request)
        return response.get_parsed_content() if response.is_success() else []
    
    async def list_server_resource_templates(self, server_name: str) -> List[Dict[str, Any]]:
        """
        Get a list of resource templates for a specific MCP server.
        
        Args:
            server_name (str): Name of the MCP server.
            
        Returns:
            List[Dict[str, Any]]: List of resource template information dictionaries.
        """
        request = {
            "type": "list_server_resource_templates",
            "server_name": server_name
        }
        
        response = await self._send_request(request)
        return response.get_parsed_content() if response.is_success() else []
    
    async def list_server_resources(self, server_name: str) -> List[Dict[str, Any]]:
        """
        Get a list of direct resources for a specific MCP server.
        
        Args:
            server_name (str): Name of the MCP server.
            
        Returns:
            List[Dict[str, Any]]: List of resource information dictionaries.
        """
        request = {
            "type": "list_server_resources",
            "server_name": server_name
        }
        
        response = await self._send_request(request)
        return response.get_parsed_content() if response.is_success() else []
    
    @staticmethod
    async def is_daemon_running(socket_path: Optional[str] = None) -> bool:
        """
        Check if the MCP daemon is running.
        
        Args:
            socket_path (Optional[str]): Path to the Unix socket for IPC.
                                        If None, uses default location.
        
        Returns:
            bool: True if daemon is running, False otherwise.
        """
        client = MCPDaemonClient(socket_path)
        connected = await client.connect()
        if connected:
            await client.disconnect()
        return connected
