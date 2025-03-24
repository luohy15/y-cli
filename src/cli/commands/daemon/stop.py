import click
import os
import signal
import time

from .utils import (
    get_default_socket_path,
    get_daemon_pid_file,
    is_daemon_running,
    console
)

@click.command('stop')
def stop_daemon():
    """Stop the MCP daemon process."""
    # Check if daemon is running
    if not is_daemon_running():
        console.print("[yellow]MCP daemon is not running[/yellow]")
        return
    
    # Get PID from file
    pid_file = get_daemon_pid_file()
    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        
        # Send SIGTERM to process
        os.kill(pid, signal.SIGTERM)
        console.print(f"[green]Sent SIGTERM to MCP daemon process with PID {pid}[/green]")
        
        # Wait for process to terminate
        max_wait = 5  # seconds
        for _ in range(max_wait):
            try:
                os.kill(pid, 0)
                # Process still running, wait
                console.print(f"[yellow]Waiting for process to terminate...[/yellow]")
                time.sleep(1)
            except ProcessLookupError:
                # Process terminated
                break
        
        # Check if process is still running
        try:
            os.kill(pid, 0)
            console.print(f"[red]Process did not terminate after {max_wait} seconds. "
                        f"You may need to kill it manually with 'kill -9 {pid}'[/red]")
        except ProcessLookupError:
            # Process terminated
            console.print(f"[green]MCP daemon process terminated[/green]")
            
            # Remove PID file
            os.unlink(pid_file)
            
            # Remove socket file
            socket_path = get_default_socket_path()
            if os.path.exists(socket_path):
                os.unlink(socket_path)
    
    except (ValueError, FileNotFoundError) as e:
        console.print(f"[red]Error reading PID file: {str(e)}[/red]")
    except ProcessLookupError:
        console.print(f"[yellow]Process with PID {pid} not found. "
                     f"Daemon may have crashed or been killed.[/yellow]")
        
        # Remove PID file
        os.unlink(pid_file)
        
        # Remove socket file
        socket_path = get_default_socket_path()
        if os.path.exists(socket_path):
            os.unlink(socket_path)
    except PermissionError:
        console.print(f"[red]Permission denied when trying to kill process with PID {pid}[/red]")
