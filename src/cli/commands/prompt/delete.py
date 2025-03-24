import click
from config import prompt_service

@click.command('delete')
@click.argument('name')
def prompt_delete(name):
    """Delete a prompt configuration."""
    if prompt_service.delete_prompt(name):
        click.echo(f"Prompt '{name}' deleted successfully")
    else:
        if name == "default":
            click.echo("Cannot delete default prompt configuration")
        else:
            click.echo(f"Prompt '{name}' not found")
