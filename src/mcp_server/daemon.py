import asyncio
import json
import os
import signal
import socket
import sys
from typing import Dict, List, Optional, Tuple, Any
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from loguru import logger
from config import mcp_service


class MCPDaemonServer:
    """
    Daemon server that maintains persistent connections to MCP servers and
    provides an IPC interface for chat sessions to interact with them.
    """
    def __init__(self, socket_path: str, log_file: Optional[str] = None):
        self.socket_path = socket_path
        self.sessions: Dict[str, ClientSession] = {}
        self.server = None
        self.exit_stack = AsyncExitStack()
        self.running = False
        
        # Set up logging
        if log_file:
            logger.add(log_file, rotation="10 MB")
        
    async def connect_to_stdio_server(self, server_name: str):
        """Connect to an MCP server using configuration from service"""
        try:
            server_config = mcp_service.get_config(server_name)
            if not server_config:
                logger.error(f"Error: No configuration found for server '{server_name}'")
                return

            # Merge current environment with server config env
            env = dict(os.environ)
            env.update(server_config.env)

            server_params = StdioServerParameters(
                command=server_config.command,
                args=server_config.args,
                env=env
            )

            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            stdio, write = stdio_transport
            session = await self.exit_stack.enter_async_context(ClientSession(stdio, write))

            await session.initialize()

            self.sessions[server_name] = session
            logger.info(f"Connected to server '{server_name}'")

        except Exception as e:
            logger.error(f"Error connecting to server '{server_name}': {str(e)}")
            if hasattr(e, '__traceback__'):
                import traceback
                logger.error(f"Detailed error:\n{''.join(traceback.format_tb(e.__traceback__))}")

    async def connect_to_all_servers(self):
        """Connect to all configured MCP servers"""
        # Get all server configs
        server_configs = mcp_service.get_all_configs()
        
        for config in server_configs:
            if config.name == 'git':
                logger.info(f"Skipping server '{config.name}'")
                continue

            await self.connect_to_stdio_server(config.name)
            await asyncio.sleep(1)  # Delay to avoid overwhelming the system

    async def execute_tool(self, server_name: str, tool_name: str, arguments: dict) -> Dict[str, Any]:
        """Execute an MCP tool and return the results"""
        if server_name not in self.sessions:
            return {
                "status": "error",
                "error": f"MCP server '{server_name}' not found or not connected"
            }

        try:
            logger.info(f"Executing MCP tool '{tool_name}' on server '{server_name}'")
            result = await self.sessions[server_name].call_tool(tool_name, arguments)

            text_contents = []
            for item in result.content:
                if hasattr(item, 'type') and item.type == 'text':
                    text_contents.append(item.text)

            return {
                "status": "success",
                "content": '\n'.join(text_contents) if text_contents else "No text content found in result"
            }
        except Exception as e:
            logger.error(f"Error executing MCP tool: {str(e)}")
            return {
                "status": "error",
                "error": f"Error executing MCP tool: {str(e)}"
            }

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
                
                try:
                    request = json.loads(message)
                    request_type = request.get("type")
                    
                    if request_type == "execute_tool":
                        server_name = request.get("server_name")
                        tool_name = request.get("tool_name")
                        arguments = request.get("arguments", {})
                        
                        if not all([server_name, tool_name]):
                            response = {
                                "status": "error",
                                "error": "Missing required fields (server_name, tool_name)"
                            }
                        else:
                            response = await self.execute_tool(server_name, tool_name, arguments)
                    
                    elif request_type == "extract_tool_use":
                        content = request.get("content", "")
                        result = self.extract_mcp_tool_use(content)
                        
                        if result:
                            server_name, tool_name, arguments = result
                            response = {
                                "status": "success",
                                "server_name": server_name,
                                "tool_name": tool_name,
                                "arguments": arguments
                            }
                        else:
                            response = {
                                "status": "error",
                                "error": "No MCP tool use found in content"
                            }
                    
                    elif request_type == "list_servers":
                        response = {
                            "status": "success",
                            "servers": list(self.sessions.keys())
                        }
                    
                    elif request_type == "list_server_tools":
                        server_name = request.get("server_name")
                        if not server_name:
                            response = {
                                "status": "error",
                                "error": "Missing server_name parameter"
                            }
                        elif server_name not in self.sessions:
                            response = {
                                "status": "error",
                                "error": f"Server '{server_name}' not found or not connected"
                            }
                        else:
                            try:
                                tools_response = await self.sessions[server_name].list_tools()
                                response = {
                                    "status": "success",
                                    "tools": [
                                        {
                                            "name": tool.name,
                                            "description": tool.description,
                                            "inputSchema": tool.inputSchema
                                        }
                                        for tool in tools_response.tools
                                    ] if tools_response.tools else []
                                }
                            except Exception as e:
                                response = {
                                    "status": "error",
                                    "error": f"Error listing tools: {str(e)}"
                                }
                    
                    elif request_type == "list_server_resource_templates":
                        server_name = request.get("server_name")
                        if not server_name:
                            response = {
                                "status": "error",
                                "error": "Missing server_name parameter"
                            }
                        elif server_name not in self.sessions:
                            response = {
                                "status": "error",
                                "error": f"Server '{server_name}' not found or not connected"
                            }
                        else:
                            try:
                                templates_response = await self.sessions[server_name].list_resource_templates()
                                response = {
                                    "status": "success",
                                    "resource_templates": [
                                        {
                                            "uriTemplate": template.uriTemplate,
                                            "name": template.name,
                                            "description": template.description,
                                            "mimeType": template.mimeType
                                        }
                                        for template in templates_response.resourceTemplates
                                    ] if templates_response.resourceTemplates else []
                                }
                            except Exception as e:
                                response = {
                                    "status": "error",
                                    "error": f"Error listing resource templates: {str(e)}"
                                }
                    
                    elif request_type == "list_server_resources":
                        server_name = request.get("server_name")
                        if not server_name:
                            response = {
                                "status": "error",
                                "error": "Missing server_name parameter"
                            }
                        elif server_name not in self.sessions:
                            response = {
                                "status": "error",
                                "error": f"Server '{server_name}' not found or not connected"
                            }
                        else:
                            try:
                                resources_response = await self.sessions[server_name].list_resources()
                                response = {
                                    "status": "success",
                                    "resources": [
                                        {
                                            "uri": resource.uri,
                                            "name": resource.name,
                                            "description": resource.description,
                                            "mimeType": resource.mimeType
                                        }
                                        for resource in resources_response.resources
                                    ] if resources_response.resources else []
                                }
                            except Exception as e:
                                response = {
                                    "status": "error",
                                    "error": f"Error listing resources: {str(e)}"
                                }
                    
                    else:
                        response = {
                            "status": "error",
                            "error": f"Unknown request type: {request_type}"
                        }
                
                except json.JSONDecodeError:
                    response = {
                        "status": "error",
                        "error": "Invalid JSON"
                    }
                except Exception as e:
                    logger.error(f"Error processing request: {str(e)}")
                    response = {
                        "status": "error",
                        "error": f"Error processing request: {str(e)}"
                    }
                
                # Send response
                writer.write(json.dumps(response).encode() + b'\n')
                await writer.drain()
        
        except (ConnectionResetError, BrokenPipeError) as e:
            logger.error(f"Connection error: {str(e)}")
        finally:
            writer.close()
            await writer.wait_closed()
            logger.info(f"Client disconnected: {addr}")

    def extract_mcp_tool_use(self, content: str) -> Optional[Tuple[str, str, dict]]:
        """Extract MCP tool use details from content if present"""
        import re

        match = re.search(r'<use_mcp_tool>(.*?)</use_mcp_tool>', content, re.DOTALL)
        if not match:
            return None

        tool_content = match.group(1)

        server_match = re.search(r'<server_name>(.*?)</server_name>', tool_content)
        if not server_match:
            return None
        server_name = server_match.group(1).strip()

        tool_match = re.search(r'<tool_name>(.*?)</tool_name>', tool_content)
        if not tool_match:
            return None
        tool_name = tool_match.group(1).strip()

        args_match = re.search(r'<arguments>\s*(\{.*?\})\s*</arguments>', tool_content, re.DOTALL)
        if not args_match:
            return None

        try:
            arguments = json.loads(args_match.group(1))
        except json.JSONDecodeError:
            return None

        return (server_name, tool_name, arguments)
        
    async def start_server(self):
        """Start the IPC server"""
        # Remove socket file if it exists
        try:
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)
        except OSError as e:
            logger.error(f"Error removing socket file: {str(e)}")
            return False
            
        try:
            # Start server
            self.server = await asyncio.start_unix_server(
                self.handle_client, 
                self.socket_path
            )
            
            # Set socket permissions to allow all users to connect
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
        
        
async def run_daemon(socket_path: str, log_file: Optional[str] = None):
    """Run the MCP daemon server"""
    # Create and start daemon server
    daemon = MCPDaemonServer(socket_path, log_file)
    await daemon.start_server()


def main():
    """Main entry point for the daemon server"""
    import argparse
    
    parser = argparse.ArgumentParser(description="MCP Daemon Server")
    parser.add_argument("--socket", default=None, help="Socket path for IPC")
    parser.add_argument("--log", default=None, help="Log file path")
    
    args = parser.parse_args()
    
    # Determine socket path
    socket_path = args.socket
    if not socket_path:
        app_name = "y-cli"
        if sys.platform == "darwin":  # macOS
            base_dir = os.path.expanduser(f"~/Library/Application Support/{app_name}")
        else:  # Linux and others
            base_dir = os.path.expanduser(f"~/.local/share/{app_name}")
        
        socket_path = os.path.join(base_dir, "mcp_daemon.sock")
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(socket_path), exist_ok=True)
    
    # Determine log file path
    log_file = args.log
    if not log_file:
        app_name = "y-cli"
        if sys.platform == "darwin":  # macOS
            log_dir = os.path.expanduser(f"~/Library/Logs/{app_name}")
        else:  # Linux and others
            log_dir = os.path.expanduser(f"~/.local/share/{app_name}/logs")
        
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "mcp_daemon.log")
    
    # Run daemon
    asyncio.run(run_daemon(socket_path, log_file))


if __name__ == "__main__":
    main()
