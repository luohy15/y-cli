import click
import os
import sys
import subprocess
from pathlib import Path
from typing import Optional

from .utils import (
    get_default_socket_path,
    get_default_tcp_host,
    get_default_tcp_port,
    get_daemon_log_file,
    is_daemon_running,
    write_pid_file,
    console
)

@click.command('start')
@click.option('--socket', help='Socket path for IPC (Unix platforms)')
@click.option('--host', help='TCP host address (Windows)')
@click.option('--port', type=int, help='TCP port (Windows)')
@click.option('--log', help='Log file path')
@click.option('--foreground', '-f', is_flag=True, help='Run in foreground (don\'t daemonize)')
@click.option('--use-tcp', is_flag=True, help='Force TCP/IP mode even on Unix platforms')
def start_daemon(socket: Optional[str], host: Optional[str], port: Optional[int], 
                 log: Optional[str], foreground: bool, use_tcp: bool):
    """Start the MCP daemon process."""
    # Check if daemon is already running
    if is_daemon_running():
        console.print("[yellow]MCP daemon is already running[/yellow]")
        return
    
    # Get daemon script path
    daemon_script = Path(__file__).parent.parent.parent.parent / "mcp_daemon" / "main.py"
    
    # Determine connection type based on platform or explicit choice
    use_tcp_mode = use_tcp or sys.platform == 'win32'
    
    # Get connection and log paths
    log_file = log or get_daemon_log_file()
    
    # Ensure log directory exists
    log_dir = os.path.dirname(log_file)
    if log_dir:  # Check if there's a directory component
        os.makedirs(log_dir, exist_ok=True)
        print(f"Created log directory: {log_dir}")
    
    # Build command based on connection type
    cmd = [
        sys.executable,
        str(daemon_script),
        "--log", log_file
    ]
    
    if use_tcp_mode:
        # TCP/IP mode
        tcp_host = host or get_default_tcp_host()
        tcp_port = port or get_default_tcp_port()
        cmd.extend(["--host", tcp_host, "--port", str(tcp_port)])
        connection_info = f"TCP {tcp_host}:{tcp_port}"
    else:
        # Unix socket mode
        socket_path = socket or get_default_socket_path()
        cmd.extend(["--socket", socket_path])
        connection_info = f"Socket: {socket_path}"
    
    if foreground:
        # Run in foreground
        console.print(f"[green]Starting MCP daemon in foreground[/green]")
        console.print(connection_info)
        console.print(f"Log file: {log_file}")
        
        try:
            # Use subprocess with inherit_stderr=True to see logs in terminal
            subprocess.run(cmd)
        except KeyboardInterrupt:
            console.print("[yellow]MCP daemon stopped[/yellow]")
    else:
        # Run as daemon (background process)
        console.print(f"[green]Starting MCP daemon in background[/green]")
        console.print(connection_info)
        console.print(f"Log file: {log_file}")
        
        try:
            # Use subprocess with start_new_session=True to run in background
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            
            # Write PID file (not needed for Windows TCP mode, but harmless)
            write_pid_file(process.pid)
            
            console.print(f"[green]MCP daemon started with PID {process.pid}[/green]")
        except Exception as e:
            console.print(f"[red]Error starting MCP daemon: {str(e)}[/red]")
