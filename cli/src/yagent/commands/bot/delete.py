import click
from storage.service import bot_config as bot_service

@click.command('delete')
@click.argument('name')
def bot_delete(name):
    """Delete a bot configuration."""
    if bot_service.delete_config(name):
        click.echo(f"Bot '{name}' deleted successfully")
    else:
        if name == "default":
            click.echo("Cannot delete default bot configuration")
        else:
            click.echo(f"Bot '{name}' not found")
