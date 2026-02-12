from typing import List, Dict, Optional
from contextlib import AsyncExitStack
from types import SimpleNamespace
import os

from storage.entity.dto import Chat, Message, BotConfig
from storage.service import chat as chat_service
from ycli.display_manager import DisplayManager
from ycli.input_manager import InputManager

from storage.util import generate_id
from .utils.message_utils import create_message
from .provider.base_provider import BaseProvider
from ycli.config import config
from loguru import logger
from .intent_analyzer import IntentAnalyzer

class ChatManager:
    def __init__(
        self,
        repository,
        display_manager: DisplayManager,
        input_manager: InputManager,
        provider: BaseProvider,
        bot_config: BotConfig,
        chat_id: Optional[str] = None,
        verbose: bool = False
    ):
        self.repository = repository
        self.bot_config = bot_config
        self.model = bot_config.model
        self.display_manager = display_manager
        self.input_manager = input_manager
        self.provider = provider
        self.verbose = verbose

        # Set up cross-manager references
        self.provider.set_display_manager(display_manager)

        # Initialize intent analyzer for smart routing
        self.analyzer = self._create_analyzer(bot_config)

        # Initialize chat state
        self.current_chat: Optional[Chat] = None
        self.external_id: Optional[str] = None
        self.messages: List[Message] = []
        self.system_prompt: Optional[str] = None
        self.chat_id: Optional[str] = None
        self.continue_exist = False

        # Generate new chat ID immediately
        if chat_id:
            self.chat_id = chat_id
            self.continue_exist = True
        else:
            self.chat_id = generate_id()

    def _create_analyzer(self, bot_config: BotConfig) -> Optional[IntentAnalyzer]:
        """Create an intent analyzer if not already an analyzer bot.

        Args:
            bot_config: Bot configuration

        Returns:
            IntentAnalyzer instance or None if this is already an analyzer
        """
        if bot_config.name == "analyzer":
            return None

        analyzer_model = os.getenv('ANALYZER_MODEL', 'google/gemini-2.5-flash')
        return IntentAnalyzer(
            base_url=bot_config.base_url,
            api_key=bot_config.api_key,
            model=analyzer_model
        )

    async def _load_chat(self, chat_id: str):
        """Load an existing chat by ID"""
        existing_chat = await chat_service.get_chat(self.repository, chat_id)
        if not existing_chat:
            self.display_manager.print_error(f"Chat {chat_id} not found")
            raise ValueError(f"Chat {chat_id} not found")

        self.messages = existing_chat.messages
        self.current_chat = existing_chat

        if self.verbose:
            logger.info(f"Loaded {len(self.messages)} messages from chat {chat_id}")

    async def process_user_message(self, user_message: Message):
        self.messages.append(user_message)
        self.display_manager.display_message_panel(user_message, index=len(self.messages) - 1)

        # Analyze intent for smart routing
        decision = None
        if self.analyzer:
            decision = await self.analyzer.analyze(user_message.content)
            if self.verbose:
                logger.info(f"Intent analysis: {decision.reason}")

        assistant_message, external_id = await self.provider.call_chat_completions(
            self.messages,
            self.current_chat,
            self.system_prompt,
            decision=decision
        )
        if external_id:
            self.external_id = external_id
        await self.process_assistant_message(assistant_message)
        await self.persist_chat()

    async def process_assistant_message(self, assistant_message: Message):
        """Process assistant response"""
        self.messages.append(assistant_message)
        self.display_manager.display_message_panel(assistant_message, index=len(self.messages) - 1)

    async def persist_chat(self):
        """Persist current chat state"""
        if not self.current_chat:
            # Create new chat with pre-generated ID
            self.current_chat = await chat_service.create_chat(self.repository, self.messages, self.external_id, self.chat_id)
        else:
            # Update existing chat - external_id will be preserved automatically
            self.current_chat = await chat_service.update_chat(self.repository, self.current_chat.id, self.messages, self.external_id)

    async def run_one_off(self, prompt: str):
        """Send a one-off query and exit (non-streaming, plain text output)"""
        # Init system prompt
        self.system_prompt = ""

        user_message = create_message("user", prompt)
        self.messages.append(user_message)

        content = await self.provider.call_chat_completions_non_stream(
            self.messages, self.system_prompt
        )
        print(content)

        assistant_message = create_message("assistant", content)
        self.messages.append(assistant_message)
        await self.persist_chat()

    async def run(self):
        """Run the chat session"""
        async with AsyncExitStack() as exit_stack:
            try:
                if self.verbose:
                    logger.info("Starting chat session...")
                # Load chat if chat_id was provided and not already loaded
                if self.continue_exist:
                    await self._load_chat(self.chat_id)
                else:
                    pass
                if self.verbose:
                    logger.info("Chat loaded successfully")

                # Init basic system prompt
                self.system_prompt = ""

                if self.verbose:
                    self.display_manager.display_help()

                # Display existing messages if continuing from a previous chat
                if self.messages:
                    self.display_manager.display_chat_history(self.messages)

                while True:
                    # Get user input, multi-line flag, and line count
                    user_input, is_multi_line, line_count = self.input_manager.get_input()

                    if self.input_manager.is_exit_command(user_input):
                        self.display_manager.console.print("\n[yellow]Goodbye![/yellow]")
                        break

                    if not user_input:
                        self.display_manager.console.print("[yellow]Please enter a message.[/yellow]")
                        continue

                    # Handle copy command
                    if user_input.lower().startswith('copy '):
                        if self.input_manager.handle_copy_command(user_input, self.messages):
                            continue

                    # Add user message to history
                    user_message = create_message("user", user_input)
                    if is_multi_line:
                        # clear <<EOF line and EOF line
                        self.display_manager.clear_lines(2)

                    self.display_manager.clear_lines(line_count)

                    await self.process_user_message(user_message)

            except (KeyboardInterrupt, EOFError):
                self.display_manager.console.print("\n[yellow]Chat interrupted. Exiting...[/yellow]")
