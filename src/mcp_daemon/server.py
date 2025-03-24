import os
import json
import signal
import asyncio
from typing import Dict, Optional
from contextlib import AsyncExitStack
from loguru import logger

from mcp import ClientSession
from config import mcp_service

from .models import ServerSession
from .handlers import RequestHandler
from .sse import SSEManager
from .stdio import StdioManager

class MCPDaemonServer:
    """
    Daemon server that maintains persistent connections to MCP servers and
    provides an IPC interface for chat sessions to interact with them.
    """
    def __init__(self, socket_path: str, log_file: Optional[str] = None):
        self.socket_path = socket_path
        self.sessions: Dict[str, ServerSession] = {}
        self.server = None
        self.exit_stack = AsyncExitStack()
        self.running = False
        
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
        """Start the IPC server"""
        try:
            # Remove socket file if it exists
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)
                
            # Start server
            self.server = await asyncio.start_unix_server(
                self.handle_client, 
                self.socket_path
            )
            
            # Set socket permissions
            os.chmod(self.socket_path, 0o777)
            
            # Enter server context
            async with self.server:
                logger.info(f"MCP daemon server started at {self.socket_path}")
                self.running = True
                
                # Set up signal handlers
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
        """Stop the IPC server and disconnect from all MCP servers"""
        if not self.running:
            return
            
        logger.info("Stopping MCP daemon server...")
        
        # Stop server
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
        
        # Close all MCP sessions
        await self.exit_stack.aclose()
        self.sessions.clear()
        
        # Remove socket file
        try:
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)
        except OSError as e:
            logger.error(f"Error removing socket file: {str(e)}")
        
        self.running = False
        logger.info("MCP daemon server stopped")
