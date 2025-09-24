import os
import json
import signal
import asyncio
import sys
from typing import Dict, Optional, Union, Tuple
from contextlib import AsyncExitStack
from loguru import logger

# Fix imports to work when run directly
try:
    from mcp import ClientSession
    from config import mcp_service
    from .models import ServerSession
    from .handlers import RequestHandler
    from .sse import SSEManager
    from .stdio import StdioManager
except (ImportError, ValueError):
    # When run directly, use absolute imports
    from src.mcp import ClientSession
    from src.config import mcp_service
    from src.mcp_daemon.models import ServerSession
    from src.mcp_daemon.handlers import RequestHandler
    from src.mcp_daemon.sse import SSEManager
    from src.mcp_daemon.stdio import StdioManager

class MCPDaemonServer:
    """
    Daemon server that maintains persistent connections to MCP servers and
    provides an interface for chat sessions to interact with them.
    Supports both Unix socket (IPC) and TCP/IP connections.
    """
    def __init__(self, connection_info: Union[str, Tuple[str, int]], log_file: Optional[str] = None, use_tcp: bool = False):
        self.use_tcp = use_tcp
        self.sessions: Dict[str, ServerSession] = {}
        self.server = None
        self.exit_stack = AsyncExitStack()
        self.running = False
        
        # Store connection info based on type
        if use_tcp:
            self.host, self.port = connection_info  # type: ignore
            self.socket_path = None
        else:
            self.socket_path = connection_info  # type: ignore
            self.host = self.port = None
        
        # Set up logging
        if log_file:
            logger.add(log_file, rotation="10 MB")
            
        # Initialize managers
        self.sse_manager = SSEManager(self.exit_stack)
        self.stdio_manager = StdioManager(self.exit_stack)
        self.request_handler = RequestHandler(self.sessions)
        
    async def connect_to_all_servers(self):
        """Connect to all configured MCP servers"""
        server_configs = mcp_service.get_all_configs()
        
        for config in server_configs:
            if config.url:  # SSE server
                logger.info(f"Connecting to SSE server '{config.name}'")
                session = await self.sse_manager.connect(
                    config.name,
                    config.url,
                    config.token
                )
                if session:
                    self.sessions[config.name] = session
            else:  # stdio server
                logger.info(f"Connecting to stdio server '{config.name}'")
                session = await self.stdio_manager.connect(
                    config.name,
                    config.command,
                    config.args,
                    config.env
                )
                if session:
                    self.sessions[config.name] = session
                    
            await asyncio.sleep(1)  # Delay to avoid overwhelming the system

    async def handle_client(self, reader, writer):
        """Handle client connections and process requests"""
        addr = writer.get_extra_info('peername')
        logger.info(f"Client connected: {addr}")
        
        try:
            while True:
                data = await reader.readline()
                if not data:
                    break
                
                message = data.decode().strip()
                response = await self.request_handler.handle_request(message)
                
                writer.write(json.dumps(response).encode() + b'\n')
                await writer.drain()
        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
        finally:
            writer.close()
            await writer.wait_closed()
            logger.info(f"Client disconnected: {addr}")
            
    async def start_server(self):
        """Start the server using either Unix socket or TCP/IP"""
        try:
            # Start server based on connection type
            if self.use_tcp:
                # TCP/IP server
                self.server = await asyncio.start_server(
                    self.handle_client,
                    self.host,
                    self.port
                )
                connection_info = f"{self.host}:{self.port}"
            else:
                # Unix socket server
                # Remove socket file if it exists
                if os.path.exists(self.socket_path):
                    os.unlink(self.socket_path)
                    
                self.server = await asyncio.start_unix_server(
                    self.handle_client, 
                    self.socket_path
                )
                
                # Set socket permissions
                os.chmod(self.socket_path, 0o777)
                connection_info = self.socket_path
            
            # Enter server context
            async with self.server:
                connection_type = "TCP/IP" if self.use_tcp else "Unix socket"
                logger.info(f"MCP daemon server started using {connection_type} at {connection_info}")
                self.running = True
                
                # Set up signal handlers (if platform supports it)
                if sys.platform != 'win32':
                    for sig in (signal.SIGINT, signal.SIGTERM):
                        asyncio.get_event_loop().add_signal_handler(
                            sig, lambda: asyncio.create_task(self.stop_server())
                        )
                
                # Connect to all MCP servers
                await self.connect_to_all_servers()
                
                # Serve until stopped
                await self.server.serve_forever()
                
            return True
            
        except Exception as e:
            logger.error(f"Error starting server: {str(e)}")
            return False
            
    async def stop_server(self):
        """Stop the server and disconnect from all MCP servers"""
        if not self.running:
            return
            
        connection_type = "TCP/IP" if self.use_tcp else "Unix socket"
        logger.info(f"Stopping MCP daemon server ({connection_type})...")
        
        # Stop server
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
        
        # Close all MCP sessions
        await self.exit_stack.aclose()
        self.sessions.clear()
        
        # Remove socket file if using Unix socket
        if not self.use_tcp and self.socket_path:
            try:
                if os.path.exists(self.socket_path):
                    os.unlink(self.socket_path)
            except OSError as e:
                logger.error(f"Error removing socket file: {str(e)}")
        
        self.running = False
        logger.info("MCP daemon server stopped")
