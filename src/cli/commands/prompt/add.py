import click
from typing import Optional
from prompt import PromptConfig
from config import prompt_service

@click.command('add')
def prompt_add():
    """Add a new prompt configuration."""
    name = click.prompt("Prompt name")
    
    # Check if prompt already exists
    existing_prompts = prompt_service.list_prompts()
    if any(prompt.name == name for prompt in existing_prompts):
        if not click.confirm(f"Prompt '{name}' already exists. Do you want to overwrite it?"):
            click.echo("Operation cancelled")
            return
    
    # Proceed with collecting remaining details
    content = click.prompt("Prompt content")
    description = click.prompt("Description (optional)", default="")

    prompt_config = PromptConfig(name=name, content=content, description=description)
    prompt_service.add_prompt(prompt_config)
    click.echo(f"Prompt '{name}' added successfully")
