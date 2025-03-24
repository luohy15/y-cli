import click
from typing import Optional
import time

from .stop import stop_daemon
from .start import start_daemon
from .utils import is_daemon_running

@click.command('restart')
@click.option('--socket', help='Socket path for IPC')
@click.option('--log', help='Log file path')
@click.option('--foreground', '-f', is_flag=True, help='Run in foreground (don\'t daemonize)')
def restart_daemon(socket: Optional[str], log: Optional[str], foreground: bool):
    """Restart the MCP daemon process."""
    # Stop daemon if running
    if is_daemon_running():
        stop_daemon.callback()
        # Wait a bit for cleanup
        time.sleep(1)
    
    # Start daemon
    start_daemon.callback(socket, log, foreground)
