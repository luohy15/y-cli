import asyncio
import json
import os
import sys
from typing import Dict, List, Optional, Tuple, Any, Union, AsyncGenerator
from contextlib import asynccontextmanager

from loguru import logger
import os
from .models import DaemonResponse
from .connection_pool import ConnectionPool

class MCPDaemonClient:
    """
    Client for communicating with the MCP daemon server.
    Provides interface to execute MCP tools and other operations.
    """
    def __init__(self, socket_path: Optional[str] = None, pool_size: Optional[int] = None, 
                 buffer_size: Optional[int] = None):
        """
        Initialize the client with a socket path.
        
        Args:
            socket_path (Optional[str]): Path to the Unix socket for IPC.
                                        If None, uses default location.
            pool_size (Optional[int]): Size of the connection pool.
                                      If None, uses environment variable or default.
            buffer_size (Optional[int]): Buffer size for reading responses in bytes.
                                        If None, uses environment variable or default (1MB).
        """
        self.socket_path = socket_path or self._get_default_socket_path()
        
        # Get pool size from environment or use default
        if pool_size is None:
            env_pool_size = os.environ.get('Y_CLI_MCP_DAEMON_POOL_SIZE')
            pool_size = int(env_pool_size) if env_pool_size else 5
        
        # Get buffer size from environment or use default (1MB)
        if buffer_size is None:
            env_buffer_size = os.environ.get('Y_CLI_MCP_DAEMON_BUFFER_SIZE')
            self.buffer_size = int(env_buffer_size) if env_buffer_size else 1024 * 1024
        else:
            self.buffer_size = buffer_size
            
        self.connection_pool = ConnectionPool(self.socket_path, pool_size)
        
    def _get_default_socket_path(self) -> str:
        """
        Get the default socket path based on platform
        
        Returns:
            str: Path to the daemon socket file
        """
        app_name = "y-cli"
        if sys.platform == "darwin":  # macOS
            base_dir = os.path.expanduser(f"~/Library/Application Support/{app_name}")
        else:  # Linux and others
            base_dir = os.path.expanduser(f"~/.local/share/{app_name}")
        
        return os.path.join(base_dir, "mcp_daemon.sock")
    
    async def connect(self) -> bool:
        """
        Initialize the connection pool.
        
        Returns:
            bool: True if socket path exists, False otherwise.
        """
        try:
            if not os.path.exists(self.socket_path):
                logger.error(f"Socket file {self.socket_path} does not exist. "
                          f"Make sure the MCP daemon is running.")
                return False
                
            await self.connection_pool.initialize()
            return True
        except Exception as e:
            logger.error(f"Unexpected error initializing connection pool: {str(e)}")
            return False
    
    async def disconnect(self):
        """Close all connections in the pool."""
        await self.connection_pool.close_all()
        
    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[Tuple[asyncio.StreamReader, asyncio.StreamWriter], None]:
        """
        Get a connection from the pool and automatically release it when done.
        
        Yields:
            Tuple[asyncio.StreamReader, asyncio.StreamWriter]: Connection pair.
        """
        reader = writer = None
        try:
            reader, writer = await self.connection_pool.get_connection()
            yield reader, writer
        finally:
            if reader and writer:
                await self.connection_pool.release_connection(reader, writer)
    
    async def _send_request(self, request: Dict[str, Any]) -> DaemonResponse:
        """
        Send a request to the daemon server and get the response.
        
        Args:
            request (Dict[str, Any]): Request data to send.
            
        Returns:
            DaemonResponse: Structured response from the daemon server.
        """
        # Check if socket exists
        if not os.path.exists(self.socket_path):
            return DaemonResponse(
                status="error", 
                error="MCP daemon socket not found. Make sure the daemon is running."
            )
        
        try:
            async with self.get_connection() as (reader, writer):
                # Send request
                writer.write(json.dumps(request).encode() + b'\n')
                await writer.drain()
                
                # Get response - use a buffer-based approach for large responses
                buffer_size = self.buffer_size
                buffer = bytearray()
                
                # Read in chunks to handle large responses
                while True:
                    try:
                        # Set a reasonable timeout for each chunk
                        chunk = await asyncio.wait_for(reader.read(buffer_size), timeout=10.0)
                        if not chunk:  # EOF reached
                            break
                        buffer.extend(chunk)
                        
                        # Try to decode as JSON - if successful, we have a complete message
                        try:
                            raw_response = json.loads(buffer.decode())
                            return DaemonResponse.from_dict(raw_response)
                        except json.JSONDecodeError:
                            # Not a complete JSON message yet, continue reading
                            continue
                    except asyncio.TimeoutError:
                        # If we've read something but hit timeout, try to parse it
                        if buffer:
                            try:
                                raw_response = json.loads(buffer.decode())
                                return DaemonResponse.from_dict(raw_response)
                            except json.JSONDecodeError:
                                return DaemonResponse(
                                    status="error",
                                    error="Timeout waiting for complete response from MCP daemon"
                                )
                        else:
                            return DaemonResponse(
                                status="error",
                                error="Timeout waiting for response from MCP daemon"
                            )
                
                # If we exited the loop without returning, check if we have data
                if not buffer:
                    return DaemonResponse(
                        status="error", 
                        error="No response from MCP daemon"
                    )
                
                # Try to parse the complete buffer
                try:
                    raw_response = json.loads(buffer.decode())
                    return DaemonResponse.from_dict(raw_response)
                except json.JSONDecodeError as e:
                    # If we can't parse the JSON, log what we received
                    error_msg = f"Invalid JSON response: {str(e)}"
                    if len(buffer) > 1000:
                        logger.error(f"{error_msg} (response too large to display)")
                    else:
                        logger.error(f"{error_msg}, received: {buffer.decode(errors='replace')}")
                    
                    return DaemonResponse(
                        status="error", 
                        error=error_msg
                    )
                
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
        if socket_path is None:
            socket_path = MCPDaemonClient()._get_default_socket_path()

        # Try to connect
        try:
            reader, writer = await asyncio.open_unix_connection(socket_path)
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            return False
