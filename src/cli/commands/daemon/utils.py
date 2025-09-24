import os
import sys
import asyncio
from pathlib import Path
from typing import Optional, Tuple

from rich.console import Console
from rich.table import Table

# Import client factory instead of direct client
from src.client_factory import get_client, is_daemon_running as check_daemon_running

console = Console()

def get_default_socket_path() -> str:
    """Get the default socket path based on platform"""
    app_name = "y-cli"
    if sys.platform == "darwin":  # macOS
        base_dir = os.path.expanduser(f"~/Library/Application Support/{app_name}")
    else:  # Linux and others
        base_dir = os.path.expanduser(f"~/.local/share/{app_name}")
    
    return os.path.join(base_dir, "mcp_daemon.sock")

def get_default_tcp_host() -> str:
    """Get the default TCP host"""
    # Check environment variable first
    env_host = os.environ.get('Y_CLI_MCP_DAEMON_HOST')
    return env_host or "127.0.0.1"  # Default to localhost

def get_default_tcp_port() -> int:
    """Get the default TCP port"""
    # Check environment variable first
    env_port = os.environ.get('Y_CLI_MCP_DAEMON_PORT')
    return int(env_port) if env_port else 8765  # Default port

def get_daemon_pid_file() -> str:
    """Get the daemon PID file path based on platform"""
    app_name = "y-cli"
    if sys.platform == "darwin":  # macOS
        base_dir = os.path.expanduser(f"~/Library/Application Support/{app_name}")
    elif sys.platform == "win32":  # Windows
        # Use AppData/Local for Windows
        base_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), app_name)
    else:  # Linux and others
        base_dir = os.path.expanduser(f"~/.local/share/{app_name}")
    
    # Ensure directory exists
    try:
        os.makedirs(base_dir, exist_ok=True)
    except Exception as e:
        print(f"Error creating PID directory: {str(e)}")
    
    return os.path.join(base_dir, "mcp_daemon.pid")

def get_daemon_log_file() -> str:
    """Get the daemon log file path based on platform"""
    app_name = "y-cli"
    if sys.platform == "darwin":  # macOS
        log_dir = os.path.expanduser(f"~/Library/Logs/{app_name}")
    elif sys.platform == "win32":  # Windows
        # Use AppData/Local for Windows
        log_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), app_name, 'logs')
    else:  # Linux and others
        log_dir = os.path.expanduser(f"~/.local/share/{app_name}/logs")
    
    # Create directory if it doesn't exist
    try:
        os.makedirs(log_dir, exist_ok=True)
        print(f"Log directory: {log_dir}")
    except Exception as e:
        print(f"Error creating log directory: {str(e)}")
    
    return os.path.join(log_dir, "mcp_daemon.log")

def is_daemon_running() -> bool:
    """
    Check if the daemon is running using the appropriate method based on platform.
    
    On Windows, checks TCP connection.
    On other platforms, checks socket file and PID file.
    """
    # On Windows, use TCP check
    if sys.platform == 'win32':
        # We need to run this in an event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # If no event loop exists, create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Run the async check in the event loop
        return loop.run_until_complete(
            check_daemon_running(use_tcp=True, host=get_default_tcp_host(), port=get_default_tcp_port())
        )
    
    # On other platforms, check socket file and PID file
    socket_path = get_default_socket_path()
    pid_file = get_daemon_pid_file()
    
    # Check if socket file exists
    if not os.path.exists(socket_path):
        return False
    
    # Check if PID file exists
    if not os.path.exists(pid_file):
        return False
    
    # Check if process is running
    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        
        # Try to send signal 0 to process to check if it's running
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, ValueError, FileNotFoundError):
        # Process not running or PID file invalid
        return False
    except PermissionError:
        # Process is running but we don't have permission to send signal
        # This is likely the daemon process, so we consider it running
        return True

def write_pid_file(pid: int):
    """Write PID to file"""
    pid_file = get_daemon_pid_file()
    os.makedirs(os.path.dirname(pid_file), exist_ok=True)
    
    with open(pid_file, 'w') as f:
        f.write(str(pid))

async def get_daemon_status() -> dict:
    """Get daemon status including connected servers"""
    # Determine connection type based on platform
    use_tcp = sys.platform == 'win32'
    
    status = {
        "running": False,
        "pid": None,
        "connection_type": "TCP/IP" if use_tcp else "Unix socket",
        "log_file": get_daemon_log_file(),
        "servers": []
    }
    
    # Add connection details based on type
    if use_tcp:
        status["host"] = get_default_tcp_host()
        status["port"] = get_default_tcp_port()
    else:
        status["socket"] = get_default_socket_path()
    
    # Check if daemon is running - for Windows, we need to do this differently
    daemon_running = False
    if use_tcp:
        # For Windows, use the async check directly
        daemon_running = await check_daemon_running(
            use_tcp=True, 
            host=get_default_tcp_host(), 
            port=get_default_tcp_port()
        )
    else:
        # For Unix platforms, use the synchronous check
        daemon_running = is_daemon_running()
    
    if daemon_running:
        status["running"] = True
        
        # Get PID from file (if not on Windows)
        if not use_tcp:
            pid_file = get_daemon_pid_file()
            try:
                with open(pid_file, 'r') as f:
                    status["pid"] = int(f.read().strip())
            except (ValueError, FileNotFoundError):
                pass
        
        # Get connected servers using the appropriate client
        try:
            client = get_client(use_tcp=use_tcp)
            connected = await client.connect()
            if connected:
                status["servers"] = await client.list_servers()
                await client.disconnect()
        except Exception as e:
            status["error"] = str(e)
    
    return status
