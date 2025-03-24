import click
from typing import Optional
from bot import BotConfig
from config import bot_service, config

@click.command('add')
def bot_add():
    """Add a new bot configuration."""
    # Tip about direct file editing
    click.echo(f"TIP: For efficiency, you can directly edit the bot configuration file at: {config['bot_config_file']}")
    name = click.prompt("Bot name")
    
    # Check if bot already exists
    existing_configs = bot_service.list_configs()
    if any(config.name == name for config in existing_configs):
        if not click.confirm(f"Bot '{name}' already exists. Do you want to overwrite it?"):
            click.echo("Operation cancelled")
            return
    
    # Get default config for default values
    default_config = bot_service.default_config
            
    # Proceed with collecting remaining details
    api_key = click.prompt("API key")
    base_url = click.prompt("Base URL", default=default_config.base_url)
    model = click.prompt("Model", default=default_config.model)

    bot_config = BotConfig(name=name, api_key=api_key, base_url=base_url, model=model)
    bot_service.add_config(bot_config)
    click.echo(f"Bot '{name}' added successfully")
