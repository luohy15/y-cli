import asyncio
import json
import os
import sys
import socket
from typing import Dict, List, Optional, Tuple, Any, Union, AsyncGenerator
from contextlib import asynccontextmanager

from loguru import logger
from .models import DaemonResponse
from .connection_pool import ConnectionPool

class MCPDaemonClient:
    """
    Client for communicating with the MCP daemon server.
    Provides interface to execute MCP tools and other operations.
    Uses TCP/IP sockets for cross-platform compatibility.
    """
    def __init__(self, host: Optional[str] = None, port: Optional[int] = None, 
                 pool_size: Optional[int] = None, buffer_size: Optional[int] = None):
        """
        Initialize the client with host and port.
        
        Args:
            host (Optional[str]): Hostname or IP address of the daemon server.
                                 If None, uses default (localhost).
            port (Optional[int]): Port number of the daemon server.
                                 If None, uses default (8765).
            pool_size (Optional[int]): Size of the connection pool.
                                      If None, uses environment variable or default.
            buffer_size (Optional[int]): Buffer size for reading responses in bytes.
                                        If None, uses environment variable or default (1MB).
        """
        self.host, self.port = self._get_default_host_port(host, port)
        
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
            
        self.connection_pool = ConnectionPool(self.host, self.port, pool_size)
        
    def _get_default_host_port(self, host: Optional[str], port: Optional[int]) -> Tuple[str, int]:
        """
        Get the default host and port
        
        Args:
            host (Optional[str]): Host provided by the user, or None
            port (Optional[int]): Port provided by the user, or None
            
        Returns:
            Tuple[str, int]: Default host and port
        """
        # Use provided values or defaults
        default_host = "127.0.0.1"  # localhost
        default_port = 8765  # Default port for MCP daemon
        
        # Check environment variables
        env_host = os.environ.get('Y_CLI_MCP_DAEMON_HOST')
        env_port = os.environ.get('Y_CLI_MCP_DAEMON_PORT')
        
        # Determine final values
        final_host = host or env_host or default_host
        final_port = port or (int(env_port) if env_port else default_port)
        
        return final_host, final_port
    
    async def connect(self) -> bool:
        """
        Initialize the connection pool and check if the daemon is running.
        
        Returns:
            bool: True if daemon is running, False otherwise.
        """
        try:
            # Check if the server is reachable
            is_running = await self.is_daemon_running(self.host, self.port)
            if not is_running:
                logger.error(f"MCP daemon not running at {self.host}:{self.port}. "
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
                
        except ConnectionRefusedError:
            logger.error(f"Connection refused to MCP daemon at {self.host}:{self.port}")
            return DaemonResponse(
                status="error", 
                error=f"Connection refused to MCP daemon at {self.host}:{self.port}"
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
    async def is_daemon_running(host: Optional[str] = None, port: Optional[int] = None) -> bool:
        """
        Check if the MCP daemon is running.
        
        Args:
            host (Optional[str]): Hostname or IP address of the daemon server.
                                 If None, uses default (localhost).
            port (Optional[int]): Port number of the daemon server.
                                 If None, uses default (8765).
        
        Returns:
            bool: True if daemon is running, False otherwise.
        """
        if host is None or port is None:
            client = MCPDaemonClient()
            host = host or client.host
            port = port or client.port

        # Try to connect
        try:
            reader, writer = await asyncio.open_connection(host, port)
            writer.close()
            await writer.wait_closed()
            return True
        except (ConnectionRefusedError, OSError):
            return False
