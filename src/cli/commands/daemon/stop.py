import click
import os
import signal
import time
import sys
import asyncio

from .utils import (
    get_default_socket_path,
    get_daemon_pid_file,
    get_default_tcp_host,
    get_default_tcp_port,
    is_daemon_running,
    console
)

from src.client_factory import get_client

async def stop_tcp_daemon():
    """Stop the daemon running in TCP mode"""
    pid_file = get_daemon_pid_file()
    try:
        # Create a TCP client
        client = get_client(use_tcp=True)
        
        # Try to connect
        connected = await client.connect()
        if not connected:
            console.print("[red]Could not connect to TCP daemon[/red]")
            return False
        
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        
        # Send SIGTERM to process
        os.kill(pid, signal.SIGTERM)
        console.print(f"[green]Sent SIGTERM to MCP daemon process with PID {pid}[/green]")
        # For now, we don't have a proper shutdown command
        # Just inform the user that the daemon is running
        # console.print("[yellow]TCP daemon is running, but cannot be stopped automatically.[/yellow]")
        # console.print("[yellow]Please manually terminate the process running the daemon.[/yellow]")
        
        # Disconnect
        await client.disconnect()
        return True
    except Exception as e:
        console.print(f"[red]Error communicating with TCP daemon: {str(e)}[/red]")
        return False

def stop_unix_daemon():
    """Stop the daemon running in Unix socket mode"""
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
            return False
        except ProcessLookupError:
            # Process terminated
            console.print(f"[green]MCP daemon process terminated[/green]")
            
            # Remove PID file
            os.unlink(pid_file)
            
            # Remove socket file
            socket_path = get_default_socket_path()
            if os.path.exists(socket_path):
                os.unlink(socket_path)
            
            return True
    
    except (ValueError, FileNotFoundError) as e:
        console.print(f"[red]Error reading PID file: {str(e)}[/red]")
        return False
    except ProcessLookupError:
        console.print(f"[yellow]Process with PID {pid} not found. "
                     f"Daemon may have crashed or been killed.[/yellow]")
        
        # Remove PID file
        try:
            os.unlink(pid_file)
        except:
            pass
        
        # Remove socket file
        socket_path = get_default_socket_path()
        if os.path.exists(socket_path):
            try:
                os.unlink(socket_path)
            except:
                pass
        
        return False
    except PermissionError:
        console.print(f"[red]Permission denied when trying to kill process with PID {pid}[/red]")
        return False

@click.command('stop')
def stop_daemon():
    """Stop the MCP daemon process."""
    # Check if daemon is running
    if not is_daemon_running():
        console.print("[yellow]MCP daemon is not running[/yellow]")
        return
    
    # Determine if we're using TCP or Unix socket
    use_tcp = sys.platform == 'win32'
    
    if use_tcp:
        # For TCP mode, we need to run the async function
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # If no event loop exists, create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Run the async function
        loop.run_until_complete(stop_tcp_daemon())
    else:
        # For Unix socket mode, use the synchronous function
        stop_unix_daemon()
