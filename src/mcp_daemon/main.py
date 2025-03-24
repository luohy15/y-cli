import os
import sys
import asyncio
import argparse
from typing import Optional

from mcp_daemon.server import MCPDaemonServer

async def run_daemon(socket_path: str, log_file: Optional[str] = None):
    """Run the MCP daemon server"""
    daemon = MCPDaemonServer(socket_path, log_file)
    await daemon.start_server()

def main():
    """Main entry point for the daemon server"""
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
