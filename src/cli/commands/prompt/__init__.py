import click

from .add import prompt_add
from .list import prompt_list
from .delete import prompt_delete

@click.group('prompt')
def prompt_group():
    """Manage prompt configurations."""
    pass

# Register prompt subcommands
prompt_group.add_command(prompt_add)
prompt_group.add_command(prompt_list)
prompt_group.add_command(prompt_delete)
