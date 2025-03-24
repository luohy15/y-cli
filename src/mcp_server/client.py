import asyncio
import json
import os
import sys
from typing import Dict, List, Optional, Tuple, Any

from loguru import logger

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
    
    async def _send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a request to the daemon server and get the response.
        
        Args:
            request (Dict[str, Any]): Request data to send.
            
        Returns:
            Dict[str, Any]: Response from the daemon server.
        """
        if not self.writer or not self.reader:
            connected = await self.connect()
            if not connected:
                return {"status": "error", "error": "Not connected to MCP daemon"}
        
        try:
            # Send request
            self.writer.write(json.dumps(request).encode() + b'\n')
            await self.writer.drain()
            
            # Get response
            data = await self.reader.readline()
            if not data:
                return {"status": "error", "error": "No response from MCP daemon"}
            
            response = json.loads(data.decode())
            return response
        except Exception as e:
            logger.error(f"Error communicating with MCP daemon: {str(e)}")
            return {"status": "error", "error": f"Communication error: {str(e)}"}
    
    async def execute_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an MCP tool via the daemon.
        
        Args:
            server_name (str): Name of the MCP server.
            tool_name (str): Name of the tool to execute.
            arguments (Dict[str, Any]): Arguments for the tool.
            
        Returns:
            Dict[str, Any]: Response from the daemon server.
        """
        request = {
            "type": "execute_tool",
            "server_name": server_name,
            "tool_name": tool_name,
            "arguments": arguments
        }
        
        return await self._send_request(request)
    
    async def extract_tool_use(self, content: str) -> Dict[str, Any]:
        """
        Extract MCP tool use details from content.
        
        Args:
            content (str): Content to extract tool use from.
            
        Returns:
            Dict[str, Any]: Response with extracted tool details or error.
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
        if response.get("status") == "success":
            return response.get("servers", [])
        return []
        
    async def list_server_tools(self, server_name: str) -> Dict[str, Any]:
        """
        Get a list of tools for a specific MCP server.
        
        Args:
            server_name (str): Name of the MCP server.
            
        Returns:
            Dict[str, Any]: Response with tools information or error.
        """
        request = {
            "type": "list_server_tools",
            "server_name": server_name
        }
        
        return await self._send_request(request)
    
    async def list_server_resource_templates(self, server_name: str) -> Dict[str, Any]:
        """
        Get a list of resource templates for a specific MCP server.
        
        Args:
            server_name (str): Name of the MCP server.
            
        Returns:
            Dict[str, Any]: Response with resource templates information or error.
        """
        request = {
            "type": "list_server_resource_templates",
            "server_name": server_name
        }
        
        return await self._send_request(request)
    
    async def list_server_resources(self, server_name: str) -> Dict[str, Any]:
        """
        Get a list of direct resources for a specific MCP server.
        
        Args:
            server_name (str): Name of the MCP server.
            
        Returns:
            Dict[str, Any]: Response with resources information or error.
        """
        request = {
            "type": "list_server_resources",
            "server_name": server_name
        }
        
        return await self._send_request(request)
    
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
