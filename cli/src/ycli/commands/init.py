import os
import click
from ycli.config import config
from storage.entity.dto import BotConfig
from storage.service import bot_config as bot_service

# Default model choices with index mapping and descriptions
MODEL_CHOICES = {
    "1": {
        "name": "anthropic/claude-3.7-sonnet",
        "description": "Best code implementation & tool use"
    },
    "2": {
        "name": "google/gemini-2.0-flash-001",
        "description": "Fast & strong all-rounder"
    }
}

def print_config_info():
    """Print configuration information and available settings."""
    home = os.environ.get("Y_CLI_HOME", "~/.y-cli")
    click.echo(f"\n{click.style('Y_CLI_HOME:', fg='green')}\n{click.style(home, fg='cyan')}")
    click.echo(f"{click.style('Database:', fg='green')}\n{click.style(config['database_url'], fg='cyan')}")

    click.echo(f"\n{click.style('Optional settings that can be configured using `y-cli bot add`:', fg='green')}")
    click.echo(f"- {click.style('model:', fg='yellow')} The model to use for chat")
    click.echo(f"- {click.style('base_url:', fg='yellow')} OpenRouter API base URL")
    click.echo(f"- {click.style('description:', fg='yellow')} Bot configuration description")
    click.echo(f"- {click.style('openrouter_config:', fg='yellow')} OpenRouter configuration settings")
    click.echo(f"- {click.style('max_tokens:', fg='yellow')} Maximum number of tokens in response")
    click.echo(f"- {click.style('custom_api_path:', fg='yellow')} Custom path for chat completion API request")

    click.echo(f"\n{click.style('Proxy settings via env vars:', fg='magenta')}")
    click.echo(f"- {click.style('Y_CLI_PROXY_HOST / Y_CLI_PROXY_PORT:', fg='yellow')} Network proxy settings")

@click.command()
def init():
    """Initialize y-cli configuration with required settings.

    Creates a config file then prompts for required settings.
    """

    # Get existing default config or create new one
    default_config = bot_service.get_config()

    # If already initialized with API key, skip to echo
    if default_config and default_config.api_key:
        print_config_info()
        return

    # Prompt for OpenRouter API key if not initialized
    api_key = click.prompt(
        "Please enter your OpenRouter API key",
        type=str,
        default=default_config.api_key,
        show_default=False
    )

    # Display model choices with descriptions
    click.echo("\nSet default model:")
    for idx, model_info in MODEL_CHOICES.items():
        click.echo(f"{idx}. {click.style(model_info['name'], fg='cyan')} - {click.style(model_info['description'], fg='yellow')}")

    # Prompt for model selection by index
    model_idx = click.prompt(
        "\nSelect the model to use (1-2)",
        type=click.Choice(["1", "2"]),
        default="1"
    )

    # Get the selected model name
    model = MODEL_CHOICES[model_idx]["name"]

    # Create new config with updated API key and model
    new_config = BotConfig(
        name="default",
        api_key=api_key,
        base_url=default_config.base_url,
        model=model
    )

    # Update the default config
    bot_service.add_config(new_config)

    print_config_info()
