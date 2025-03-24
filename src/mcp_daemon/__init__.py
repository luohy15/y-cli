"""
MCP Daemon Server Package

This package provides a daemon server that maintains persistent connections to MCP servers
and provides an IPC interface for chat sessions to interact with them.

The daemon server supports both SSE and stdio-based MCP servers, handling connection
management, request processing, and event handling.
"""

from .server import MCPDaemonServer
from .models import ServerSession, MCPResponse

__all__ = ['MCPDaemonServer', 'ServerSession', 'MCPResponse']
