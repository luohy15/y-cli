from typing import Optional
from contextlib import AsyncExitStack
from loguru import logger
from mcp import ClientSession
from mcp.client.sse import sse_client

from .models import ServerSession

class SSEManager:
    """Manages SSE connections to MCP servers"""
    def __init__(self, exit_stack: AsyncExitStack):
        self.exit_stack = exit_stack

    async def connect(self, server_name: str, url: str, token: Optional[str] = None) -> Optional[ServerSession]:
        """Connect to an MCP server using SSE"""
        try:
            # Prepare headers
            headers = {
                'Accept': 'text/event-stream',
                'Cache-Control': 'no-cache'
            }
            if token:
                headers['Authorization'] = f'Bearer {token}'
            
            logger.info(f"Connecting to SSE server '{server_name}'")
            
            # Use sse_client from MCP SDK with the exit_stack
            streams = await self.exit_stack.enter_async_context(sse_client(url=url, headers=headers))
            
            # Create and initialize session using the exit_stack
            session = await self.exit_stack.enter_async_context(ClientSession(*streams))
            
            # Initialize
            await session.initialize()
            
            logger.info(f"Connected to SSE server '{server_name}'")
            return ServerSession(session, 'sse')

        except Exception as e:
            logger.error(f"Error connecting to SSE server '{server_name}': {str(e)}")
            if hasattr(e, '__traceback__'):
                import traceback
                logger.error(f"Detailed error:\n{''.join(traceback.format_tb(e.__traceback__))}")
            return None

    async def handle_events(self, server_name: str, session: ClientSession):
        """Handle events from an SSE server"""
        try:
            # The SSE client in the MCP SDK doesn't provide an events interface directly
            # Future: implement event handling if needed
            pass
        except Exception as e:
            logger.error(f"Error handling SSE events for '{server_name}': {str(e)}")
