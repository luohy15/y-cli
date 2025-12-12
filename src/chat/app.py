import os
import sys
import asyncio
from typing import Optional

from .repository.factory import get_chat_repository
from cli.display_manager import DisplayManager
from cli.input_manager import InputManager
from .provider.base_provider import BaseProvider
from .provider.openai_format_provider import OpenAIFormatProvider
from .provider.dify_provider import DifyProvider
from .provider.topia_orch_provider import TopiaOrchProvider
from .chat_manager import ChatManager
from bot.models import BotConfig
from config import bot_service

class ChatApp:
    def __init__(self, bot_config: Optional[BotConfig] = None, chat_id: Optional[str] = None, verbose: bool = False):
        """Initialize the chat application.

        Args:
            bot_config: Bot configuration to use
            chat_id: Optional ID of existing chat to load
            verbose: Whether to show verbose output
        """
        # Initialize repository based on configuration
        repository = get_chat_repository()

        # Use default bot config if not provided
        if not bot_config:
            bot_config = bot_service.get_config()

        # Initialize managers
        display_manager = DisplayManager(bot_config)
        input_manager = InputManager(display_manager.console)
        # Create provider based on api_type
        provider: BaseProvider
        if bot_config.api_type == "dify":
            provider = DifyProvider(bot_config)
        elif bot_config.api_type == "topia-orch":
            provider = TopiaOrchProvider(bot_config)
        else:  # default to openai format
            provider = OpenAIFormatProvider(bot_config)

        self.chat_manager = ChatManager(
            repository=repository,
            display_manager=display_manager,
            input_manager=input_manager,
            provider=provider,
            bot_config=bot_config,
            chat_id=chat_id,
            verbose=verbose
        )

    async def chat(self):
        """Start the chat session"""
        await self.chat_manager.run()

async def main():
    try:
        # Set binary mode for stdin/stdout on Windows
        if sys.platform == 'win32':
            import msvcrt
            msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
            msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

        app = ChatApp(bot_config=bot_service.get_config(), verbose=True)
        await app.chat()
    except KeyboardInterrupt:
        # Exit silently on Ctrl+C
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
