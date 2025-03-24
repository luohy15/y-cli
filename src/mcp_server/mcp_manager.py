import json
import asyncio
import os
from typing import Dict, List, Optional, Tuple
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from rich.console import Console
from contextlib import AsyncExitStack
from .service import McpServerConfigService
from config import mcp_service

class MCPManager:
    def __init__(self, console: Console):
        self.sessions: Dict[str, ClientSession] = {}
        self.console = console

    async def connect_to_stdio_server(self, server_name: str, exit_stack: AsyncExitStack):
        """Connect to an MCP server using configuration from service"""
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
        for server_name in servers:
            if server_name == 'git':
                self.console.print(f"[yellow]Skipping server '{server_name}'[/yellow]")
                continue

            await self.connect_to_stdio_server(server_name, exit_stack)
            await asyncio.sleep(1)

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
        if server_name not in self.sessions:
            return f"Error: MCP server '{server_name}' not found"

        try:
            self.console.print(f"[cyan]Executing MCP tool '{tool_name}' on server '{server_name}'[/cyan]")
            result = await self.sessions[server_name].call_tool(tool_name, arguments)

            text_contents = []
            for item in result.content:
                if hasattr(item, 'type') and item.type == 'text':
                    text_contents.append(item.text)

            return '\n'.join(text_contents) if text_contents else "No text content found in result"
        except Exception as e:
            return f"Error executing MCP tool: {str(e)}"

    def clear_sessions(self):
        """Clear all MCP sessions"""
        self.sessions.clear()
