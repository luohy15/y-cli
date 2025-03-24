import os
import asyncio
import click
from typing import Optional
from rich.console import Console

from chat.app import ChatApp
from cli.display_manager import custom_theme
from config import bot_service
from loguru import logger

@click.command()
@click.option('--chat-id', '-c', help='Continue from an existing chat')
@click.option('--latest', '-l', is_flag=True, help='Continue from the latest chat')
@click.option('--model', '-m', help='OpenRouter model to use')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed usage instructions')
@click.option('--bot', '-b', help='Use specific bot name')
def chat(chat_id: Optional[str], latest: bool, model: Optional[str], verbose: bool = False, bot: Optional[str] = None):
    """Start a new chat conversation or continue an existing one.

    Use --latest/-l to continue from your most recent chat.
    Use --chat-id/-c to continue from a specific chat ID.
    If neither option is provided, starts a new chat.
    Use --bot/-b to use a specific bot name.
    """
    if verbose:
        logger.info("Starting chat command")

    # Get bot config
    bot_config = bot_service.get_config(bot or "default")
    
    # Use command line model if specified, otherwise use bot config model
    bot_config.model = model or bot_config.model

    # Create a single ChatApp instance for all operations
    chat_app = ChatApp(bot_config=bot_config, verbose=verbose)

    # Handle --latest flag
    if latest:
        chats = asyncio.run(chat_app.chat_manager.service.list_chats(limit=1))
        if not chats:
            click.echo("Error: No existing chats found")
            raise click.Abort()
        chat_id = chats[0].id
        # Reinitialize ChatApp with the found chat_id
        chat_app = ChatApp(bot_config=bot_config, chat_id=chat_id, verbose=verbose)

    # Handle --chat-id flag
    elif chat_id:
        # Reinitialize ChatApp with the specified chat_id
        chat_app = ChatApp(bot_config=bot_config, chat_id=chat_id, verbose=verbose)

    if verbose:
        logger.info(f"Using OpenRouter API Base URL: {bot_config.base_url}")
        if bot:
            logger.info(f"Using bot: {bot}")
        if chat_id:
            logger.info(f"Continuing from chat {chat_id}")
        else:
            logger.info("Starting new chat")

    asyncio.run(chat_app.chat())
