import click
import os
import sys
import subprocess

from .utils import (
    get_daemon_log_file,
    console
)

@click.command('log')
@click.option('--lines', '-n', default=20, help='Number of lines to show')
def show_log(lines: int):
    """Show the MCP daemon log."""
    log_file = get_daemon_log_file()
    
    if not os.path.exists(log_file):
        console.print(f"[yellow]Log file not found: {log_file}[/yellow]")
        return
    
    try:
        # Use tail to show last N lines
        if sys.platform == "win32":
            # Windows doesn't have tail, read file and show last N lines
            with open(log_file, 'r') as f:
                content = f.readlines()
            
            for line in content[-lines:]:
                click.echo(line.strip())
        else:
            # Use tail on Unix
            subprocess.run(["tail", f"-n{lines}", log_file])
    except Exception as e:
        console.print(f"[red]Error reading log file: {str(e)}[/red]")
