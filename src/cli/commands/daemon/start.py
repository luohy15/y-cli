import click
import os
import sys
import subprocess
from pathlib import Path
from typing import Optional

from .utils import (
    get_default_socket_path,
    get_daemon_log_file,
    is_daemon_running,
    write_pid_file,
    console
)

@click.command('start')
@click.option('--socket', help='Socket path for IPC')
@click.option('--log', help='Log file path')
@click.option('--foreground', '-f', is_flag=True, help='Run in foreground (don\'t daemonize)')
def start_daemon(socket: Optional[str], log: Optional[str], foreground: bool):
    """Start the MCP daemon process."""
    # Check if daemon is already running
    if is_daemon_running():
        console.print("[yellow]MCP daemon is already running[/yellow]")
        return
    
    # Get daemon script path
    daemon_script = Path(__file__).parent.parent.parent.parent / "mcp_daemon" / "main.py"
    
    # Get socket and log paths
    socket_path = socket or get_default_socket_path()
    log_file = log or get_daemon_log_file()
    
    # Ensure log directory exists
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    if foreground:
        # Run in foreground
        console.print(f"[green]Starting MCP daemon in foreground[/green]")
        console.print(f"Socket: {socket_path}")
        console.print(f"Log file: {log_file}")
        
        cmd = [
            sys.executable,
            str(daemon_script),
            "--socket", socket_path,
            "--log", log_file
        ]
        
        try:
            # Use subprocess with inherit_stderr=True to see logs in terminal
            subprocess.run(cmd)
        except KeyboardInterrupt:
            console.print("[yellow]MCP daemon stopped[/yellow]")
    else:
        # Run as daemon (background process)
        console.print(f"[green]Starting MCP daemon in background[/green]")
        console.print(f"Socket: {socket_path}")
        console.print(f"Log file: {log_file}")
        
        cmd = [
            sys.executable,
            str(daemon_script),
            "--socket", socket_path,
            "--log", log_file
        ]
        
        try:
            # Use subprocess with start_new_session=True to run in background
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            
            # Write PID to file
            write_pid_file(process.pid)
            
            console.print(f"[green]MCP daemon started with PID {process.pid}[/green]")
        except Exception as e:
            console.print(f"[red]Error starting MCP daemon: {str(e)}[/red]")
