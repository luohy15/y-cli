import os
import sys
import asyncio
from typing import Optional

from storage.repository import chat as chat_repo
from ycli.display_manager import DisplayManager
from ycli.input_manager import InputManager
from .provider.base_provider import BaseProvider
from .provider.openai_format_provider import OpenAIFormatProvider
from .provider.dify_provider import DifyProvider
from .provider.topia_orch_provider import TopiaOrchProvider
from .chat_manager import ChatManager
from storage.entity.dto import BotConfig
from storage.service import bot_config as bot_service

class ChatApp:
    def __init__(self, bot_config: Optional[BotConfig] = None, chat_id: Optional[str] = None, verbose: bool = False):
        """Initialize the chat application.

        Args:
            bot_config: Bot configuration to use
            chat_id: Optional ID of existing chat to load
            verbose: Whether to show verbose output
        """
        # Initialize repository
        repository = chat_repo

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

    async def one_off(self, prompt: str):
        """Send a one-off query and exit"""
        await self.chat_manager.run_one_off(prompt)

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
