import click
import asyncio

from .utils import (
    get_daemon_status,
    console
)

from rich.table import Table

@click.command('status')
def status_daemon():
    """Check the status of the MCP daemon process."""
    status = asyncio.run(get_daemon_status())
    
    if status["running"]:
        console.print(f"[green]MCP daemon is running[/green]")
        console.print(f"PID: {status['pid']}")
        console.print(f"Socket: {status['socket']}")
        console.print(f"Log file: {status['log_file']}")
        
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
