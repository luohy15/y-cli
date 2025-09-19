import os
import sys
from typing import Optional, Union

# Import both client implementations
from daemon_client.main import MCPDaemonClient as UnixSocketClient
from tcp_client.main import MCPDaemonClient as TCPClient

def get_client(use_tcp: Optional[bool] = None, host: Optional[str] = None, 
               port: Optional[int] = None, socket_path: Optional[str] = None,
               pool_size: Optional[int] = None, buffer_size: Optional[int] = None) -> Union[UnixSocketClient, TCPClient]:
    """
    Factory function to create the appropriate client based on system or explicit choice.
    
    Args:
        use_tcp (Optional[bool]): If True, forces TCP client. If False, forces Unix socket client.
                                 If None, decides based on platform.
        host (Optional[str]): Host for TCP client (if used)
        port (Optional[int]): Port for TCP client (if used)
        socket_path (Optional[str]): Socket path for Unix socket client (if used)
        pool_size (Optional[int]): Connection pool size
        buffer_size (Optional[int]): Buffer size for reading responses
        
    Returns:
        Union[UnixSocketClient, TCPClient]: The appropriate client instance
    """
    # Determine whether to use TCP based on explicit choice or platform
    if use_tcp is None:
        # Auto-detect: Use TCP on Windows, Unix socket on others
        use_tcp = sys.platform == 'win32'
    
    # Create the appropriate client
    if use_tcp:
        return TCPClient(host=host, port=port, pool_size=pool_size, buffer_size=buffer_size)
    else:
        return UnixSocketClient(socket_path=socket_path, pool_size=pool_size, buffer_size=buffer_size)

async def is_daemon_running(use_tcp: Optional[bool] = None, host: Optional[str] = None, 
                           port: Optional[int] = None, socket_path: Optional[str] = None) -> bool:
    """
    Check if the MCP daemon is running using the appropriate method.
    
    Args:
        use_tcp (Optional[bool]): If True, checks TCP. If False, checks Unix socket.
                                 If None, decides based on platform.
        host (Optional[str]): Host for TCP check (if used)
        port (Optional[int]): Port for TCP check (if used)
        socket_path (Optional[str]): Socket path for Unix socket check (if used)
        
    Returns:
        bool: True if daemon is running, False otherwise
    """
    # Determine whether to use TCP based on explicit choice or platform
    if use_tcp is None:
        # Auto-detect: Use TCP on Windows, Unix socket on others
        use_tcp = sys.platform == 'win32'
    
    # Check using the appropriate method
    if use_tcp:
        return await TCPClient.is_daemon_running(host=host, port=port)
    else:
        return await UnixSocketClient.is_daemon_running(socket_path=socket_path)
