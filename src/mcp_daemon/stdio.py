import os
from typing import Optional, Dict, List
from contextlib import AsyncExitStack
from loguru import logger
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .models import ServerSession

class StdioManager:
    """Manages stdio connections to MCP servers"""
    def __init__(self, exit_stack: AsyncExitStack):
        self.exit_stack = exit_stack

    async def connect(self, server_name: str, command: str, args: Optional[List[str]] = None, env: Optional[Dict[str, str]] = None) -> Optional[ServerSession]:
        """Connect to an MCP server using stdio"""
        try:
            # Merge current environment with server config env
            result_env = dict(os.environ)
            result_env.update(env)

            server_params = StdioServerParameters(
                command=command,
                args=args or [],
                env=result_env
            )
            
            logger.info(f"Connecting to stdio server '{server_name}'")
            
            # Use stdio_client from MCP SDK with the exit_stack
            streams = await self.exit_stack.enter_async_context(stdio_client(server_params))
            
            # Create and initialize session using the exit_stack
            session = await self.exit_stack.enter_async_context(ClientSession(*streams))
            
            # Initialize
            await session.initialize()
            
            logger.info(f"Connected to stdio server '{server_name}'")
            return ServerSession(session, 'stdio')

        except Exception as e:
            logger.error(f"Error connecting to stdio server '{server_name}': {str(e)}")
            if hasattr(e, '__traceback__'):
                import traceback
                logger.error(f"Detailed error:\n{''.join(traceback.format_tb(e.__traceback__))}")
            return None
