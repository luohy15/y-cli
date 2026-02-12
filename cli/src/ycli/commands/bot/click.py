import click

from .add import bot_add
from .list import bot_list
from .delete import bot_delete

@click.group('bot')
def bot_group():
    """Manage bot configurations."""
    pass

# Register bot subcommands
bot_group.add_command(bot_add)
bot_group.add_command(bot_list)
bot_group.add_command(bot_delete)
