import os
import sys
import asyncio
import argparse
from typing import Optional, Union, Tuple

# Fix imports to work when run directly
try:
    from server import MCPDaemonServer
except ImportError:
    # When run directly, use absolute imports
    from src.mcp_daemon.server import MCPDaemonServer

async def run_daemon(connection_info: Union[str, Tuple[str, int]], log_file: Optional[str] = None, use_tcp: bool = False):
    """
    Run the MCP daemon server
    
    Args:
        connection_info: Either a socket path (str) or a (host, port) tuple
        log_file: Path to log file
        use_tcp: Whether to use TCP/IP mode
    """
    daemon = MCPDaemonServer(connection_info, log_file, use_tcp)
    await daemon.start_server()

def main():
    """Main entry point for the daemon server"""
    parser = argparse.ArgumentParser(description="MCP Daemon Server")
    # Connection options
    parser.add_argument("--socket", default=None, help="Socket path for IPC (Unix platforms)")
    parser.add_argument("--host", default=None, help="TCP host address (Windows)")
    parser.add_argument("--port", type=int, default=None, help="TCP port (Windows)")
    parser.add_argument("--log", default=None, help="Log file path")
    
    args = parser.parse_args()
    
    # Determine connection type and info
    use_tcp = False
    connection_info = None
    
    # Check if TCP parameters are provided or if we're on Windows
    if args.host or args.port or sys.platform == 'win32':
        use_tcp = True
        # Get host and port
        host = args.host or "127.0.0.1"  # Default to localhost
        port = args.port or 8765  # Default port
        connection_info = (host, port)
    else:
        # Unix socket mode
        socket_path = args.socket
        if not socket_path:
            app_name = "y-cli"
            if sys.platform == "darwin":  # macOS
                base_dir = os.path.expanduser(f"~/Library/Application Support/{app_name}")
            else:  # Linux and others
                base_dir = os.path.expanduser(f"~/.local/share/{app_name}")
            
            socket_path = os.path.join(base_dir, "mcp_daemon.sock")
        
        # Ensure directory exists for socket
        os.makedirs(os.path.dirname(socket_path), exist_ok=True)
        connection_info = socket_path
    
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
    
    # Run daemon with appropriate connection info
    asyncio.run(run_daemon(connection_info, log_file, use_tcp))

if __name__ == "__main__":
    main()
