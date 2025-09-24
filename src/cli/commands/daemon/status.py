import click
import asyncio
import sys

from .utils import (
    get_daemon_status,
    console
)

from rich.table import Table

@click.command('status')
def status_daemon():
    """Check the status of the MCP daemon process."""
    # Run the async function safely
    try:
        # Try to get the current event loop
        loop = asyncio.get_event_loop()
        # Check if the loop is already running
        if loop.is_running():
            # Create a new loop for this function
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            status = new_loop.run_until_complete(get_daemon_status())
            new_loop.close()
        else:
            # Use the existing loop
            status = loop.run_until_complete(get_daemon_status())
    except RuntimeError:
        # No event loop exists, create one
        status = asyncio.run(get_daemon_status())
    
    # Display status information
    if status["running"]:
        console.print(f"[green]MCP daemon is running[/green]")
        
        # Display connection type and details
        connection_type = status.get("connection_type", "Unknown")
        console.print(f"Connection type: {connection_type}")
        
        # Show appropriate connection details based on type
        if "socket" in status:
            console.print(f"Socket: {status['socket']}")
        if "host" in status and "port" in status:
            console.print(f"Host: {status['host']}")
            console.print(f"Port: {status['port']}")
            
        # Show PID if available
        if status.get("pid"):
            console.print(f"PID: {status['pid']}")
            
        console.print(f"Log file: {status['log_file']}")
        
        if status.get("error"):
            console.print(f"[yellow]Warning: {status['error']}[/yellow]")
        
        if status["servers"]:
            # Create a table for connected servers
            table = Table(title="Connected MCP Servers")
            table.add_column("Server Name")
            
            for server in status["servers"]:
                table.add_row(server)
            
            console.print(table)
        else:
            console.print("[yellow]No MCP servers connected[/yellow]")
    else:
        console.print("[yellow]MCP daemon is not running[/yellow]")
