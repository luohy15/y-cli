import os
import sys
import asyncio
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table

from daemon_client.main import MCPDaemonClient

console = Console()

def get_default_socket_path() -> str:
    """Get the default socket path based on platform"""
    app_name = "y-cli"
    if sys.platform == "darwin":  # macOS
        base_dir = os.path.expanduser(f"~/Library/Application Support/{app_name}")
    else:  # Linux and others
        base_dir = os.path.expanduser(f"~/.local/share/{app_name}")
    
    return os.path.join(base_dir, "mcp_daemon.sock")

def get_daemon_pid_file() -> str:
    """Get the daemon PID file path based on platform"""
    app_name = "y-cli"
    if sys.platform == "darwin":  # macOS
        base_dir = os.path.expanduser(f"~/Library/Application Support/{app_name}")
    else:  # Linux and others
        base_dir = os.path.expanduser(f"~/.local/share/{app_name}")
    
    return os.path.join(base_dir, "mcp_daemon.pid")

def get_daemon_log_file() -> str:
    """Get the daemon log file path based on platform"""
    app_name = "y-cli"
    if sys.platform == "darwin":  # macOS
        log_dir = os.path.expanduser(f"~/Library/Logs/{app_name}")
    else:  # Linux and others
        log_dir = os.path.expanduser(f"~/.local/share/{app_name}/logs")
    
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "mcp_daemon.log")

def is_daemon_running() -> bool:
    """Check if the daemon is running by checking socket file and PID file"""
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
    status = {
        "running": False,
        "pid": None,
        "socket": get_default_socket_path(),
        "log_file": get_daemon_log_file(),
        "servers": []
    }
    
    # Check if daemon is running
    if is_daemon_running():
        status["running"] = True
        
        # Get PID from file
        pid_file = get_daemon_pid_file()
        try:
            with open(pid_file, 'r') as f:
                status["pid"] = int(f.read().strip())
        except (ValueError, FileNotFoundError):
            pass
        
        # Get connected servers
        try:
            client = MCPDaemonClient()
            connected = await client.connect()
            if connected:
                status["servers"] = await client.list_servers()
                await client.disconnect()
        except Exception:
            pass
    
    return status
