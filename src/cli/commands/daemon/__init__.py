import click

from .start import start_daemon
from .stop import stop_daemon
from .status import status_daemon
from .log import show_log
from .restart import restart_daemon

@click.group(name='daemon')
def daemon_group():
    """Manage the MCP daemon process."""
    pass

# Register daemon subcommands
daemon_group.add_command(start_daemon)
daemon_group.add_command(stop_daemon)
daemon_group.add_command(status_daemon)
daemon_group.add_command(show_log)
daemon_group.add_command(restart_daemon)
