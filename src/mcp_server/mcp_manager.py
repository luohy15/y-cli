import json
import asyncio
import os
import sys
from typing import Dict, List, Optional, Tuple, Any
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from rich.console import Console
from contextlib import AsyncExitStack
from .client import MCPDaemonClient
from config import mcp_service
from loguru import logger

class MCPManager:
    def __init__(self, console: Console):
        self.sessions: Dict[str, ClientSession] = {}
        self.console = console
        self.client = MCPDaemonClient()
        self.use_daemon = False  # Will be set after checking if daemon is running
        self.connected_to_daemon = False

    async def check_daemon_running(self) -> bool:
        """Check if the MCP daemon is running and we should use it"""
        try:
            # Check if daemon is running
            self.use_daemon = await MCPDaemonClient.is_daemon_running()
            if self.use_daemon:
                # Connect to daemon
                self.connected_to_daemon = await self.client.connect()
                if self.connected_to_daemon:
                    self.console.print("[green]Connected to MCP daemon[/green]")
                    return True
                else:
                    self.console.print("[yellow]MCP daemon is running but connection failed[/yellow]")
                    self.use_daemon = False
            else:
                self.console.print("[yellow]MCP daemon is not running[/yellow]")
                return False
        except Exception as e:
            logger.error(f"Error checking daemon status: {str(e)}")
            self.use_daemon = False
            return False

    async def connect_to_stdio_server(self, server_name: str, exit_stack: AsyncExitStack):
        """Connect to an MCP server using configuration from service"""
        # If using daemon, no need to connect directly
        if self.use_daemon:
            return
            
        try:
            server_config = mcp_service.get_config(server_name)
            if not server_config:
                self.console.print(f"[red]Error: No configuration found for server '{server_name}'[/red]")
                return

            # Merge current environment with server config env
            env = dict(os.environ)
            env.update(server_config.env)

            server_params = StdioServerParameters(
                command=server_config.command,
                args=server_config.args,
                env=env
            )

            stdio_transport = await exit_stack.enter_async_context(stdio_client(server_params))
            stdio, write = stdio_transport
            session = await exit_stack.enter_async_context(ClientSession(stdio, write))

            await session.initialize()

            self.sessions[server_name] = session
            self.console.print(f"[green]Connected to server '{server_name}'[/green]")

        except Exception as e:
            self.console.print(f"[red]Error connecting to server '{server_name}': {str(e)}[/red]")
            if hasattr(e, '__traceback__'):
                import traceback
                self.console.print(f"[red]Detailed error:\n{''.join(traceback.format_tb(e.__traceback__))}[/red]")

    async def connect_to_stdio_servers(self, servers: List[str], exit_stack: AsyncExitStack):
        """Connect to specified MCP servers"""
        # First check if daemon is running
        daemon_running = await self.check_daemon_running()
        
        if daemon_running:
            # Just print which servers are available via daemon
            if servers:
                daemon_servers = await self.client.list_servers()
                all_connected = True
                for server_name in servers:
                    if server_name in daemon_servers:
                        self.console.print(f"[green]Server '{server_name}' available via daemon[/green]")
                    else:
                        self.console.print(f"[yellow]Warning: Server '{server_name}' not connected in daemon[/yellow]")
                        all_connected = False
                
                if not all_connected:
                    self.console.print("[yellow]Some servers are not available. Try restarting the MCP daemon.[/yellow]")

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

    async def execute_tool(self, server_name: str, tool_name: str, arguments: dict) -> str:
        """Execute an MCP tool and return the results"""
        try:
            self.console.print(f"[cyan]Executing MCP tool '{tool_name}' on server '{server_name}' via daemon[/cyan]")
            response = await self.client.execute_tool(server_name, tool_name, arguments)
            
            if response.get("status") == "success":
                return response.get("content", "No content returned from daemon")
            else:
                error_msg = response.get("error", "Unknown error")
                self.console.print(f"[red]Error from daemon: {error_msg}[/red]")
                return f"Error executing MCP tool: {error_msg}"
        except Exception as e:
            error_msg = str(e)
            self.console.print(f"[red]Error communicating with daemon: {error_msg}[/red]")
            return f"Error communicating with daemon: {error_msg}"

    def clear_sessions(self):
        """Clear all MCP sessions"""
        # Disconnect from daemon if connected
        if self.connected_to_daemon:
            asyncio.create_task(self.client.disconnect())
            self.connected_to_daemon = False
            
        # Clear direct sessions
        self.sessions.clear()

    async def format_server_info(self, servers) -> str:
        """
        Format MCP server information for the system prompt.
        Works with both direct connections and daemon-based connections.
        
        Returns:
            Formatted server information string
        """
        # Get server list from daemon
        server_names = await self.client.list_servers()
        if not server_names:
            return "(No MCP servers currently connected via daemon)"
            
        # Format server information from daemon
        server_sections = []
        
        for server_name in servers:
            # Get server information
            tools_section = ""
            templates_section = ""
            resources_section = ""
            
            try:
                # Get and format tools section
                tools_response = await self.client.list_server_tools(server_name)
                if tools_response.get("status") == "success" and tools_response.get("tools"):
                    tools = []
                    for tool in tools_response.get("tools", []):
                        schema_str = ""
                        if tool.get("inputSchema"):
                            schema_json = json.dumps(tool.get("inputSchema"), indent=2)
                            schema_lines = schema_json.split("\n")
                            schema_str = "\n    Input Schema:\n    " + "\n    ".join(schema_lines)
                            
                        tools.append(f"- {tool.get('name')}: {tool.get('description')}{schema_str}")
                    
                    tools_section = "\n\n### Available Tools\n" + "\n\n".join(tools)
            except Exception as e:
                logger.error(f"Error listing tools for {server_name} via daemon: {str(e)}")
            
            try:
                # Get and format resource templates section
                templates_response = await self.client.list_server_resource_templates(server_name)
                if templates_response.get("status") == "success" and templates_response.get("resource_templates"):
                    templates = []
                    for template in templates_response.get("resource_templates", []):
                        templates.append(
                            f"- {template.get('uriTemplate')} ({template.get('name')}): {template.get('description')}"
                        )
                    
                    templates_section = "\n\n### Resource Templates\n" + "\n".join(templates)
            except Exception as e:
                logger.debug(f"Error listing resource templates for {server_name} via daemon: {str(e)}")
            
            try:
                # Get and format direct resources section
                resources_response = await self.client.list_server_resources(server_name)
                if resources_response.get("status") == "success" and resources_response.get("resources"):
                    resources = []
                    for resource in resources_response.get("resources", []):
                        resources.append(
                            f"- {resource.get('uri')} ({resource.get('name')}): {resource.get('description')}"
                        )
                    
                    resources_section = "\n\n### Direct Resources\n" + "\n".join(resources)
            except Exception as e:
                logger.debug(f"Error listing resources for {server_name} via daemon: {str(e)}")
            
            # Combine all sections
            server_section = (
                f"## {server_name}"
                f"{tools_section}"
                f"{templates_section}"
                f"{resources_section}"
            )
            server_sections.append(server_section)
        
        return "\n\n".join(server_sections)
    
    async def get_mcp_prompt(self, servers, prompt_service) -> str:
        """Generate the complete system prompt including MCP server information
        
        Args:
            prompt_service: Prompt service instance for retrieving the MCP prompt template
            
        Returns:
            Formatted MCP prompt string or None if no servers connected
        """
        # Get formatted server information
        server_info = await self.format_server_info(servers)
        if server_info:
            mcp_prompt = prompt_service.get_prompt("mcp")
            if mcp_prompt:
                return mcp_prompt.content + server_info
            else:
                return server_info

        return None
