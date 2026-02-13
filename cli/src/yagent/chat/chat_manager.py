from typing import List, Optional

from storage.entity.dto import Chat, Message, BotConfig
from storage.service import chat as chat_service
from yagent.display_manager import DisplayManager
from yagent.input_manager import InputManager

from storage.util import generate_id, generate_message_id
from .utils.message_utils import create_message
from .provider.base_provider import BaseProvider
from loguru import logger

class ChatManager:
    def __init__(
        self,
        display_manager: DisplayManager,
        input_manager: InputManager,
        provider: BaseProvider,
        bot_config: BotConfig,
        chat_id: Optional[str] = None,
        verbose: bool = False
    ):
        self.bot_config = bot_config
        self.model = bot_config.model
        self.display_manager = display_manager
        self.input_manager = input_manager
        self.provider = provider
        self.verbose = verbose

        # Initialize chat state
        self.current_chat: Optional[Chat] = None
        self.external_id: Optional[str] = None
        self.messages: List[Message] = []
        self.chat_id: Optional[str] = None
        self.continue_exist = False

        # Generate new chat ID immediately
        if chat_id:
            self.chat_id = chat_id
            self.continue_exist = True
        else:
            self.chat_id = generate_id()

    def _build_system_prompt(self) -> str:
        """Build system prompt with current skills metadata."""
        from agent.skills import discover_skills, skills_to_prompt

        prompt = ""
        skills_block = skills_to_prompt(discover_skills())
        if skills_block:
            prompt += "\n" + skills_block
        return prompt

    async def _load_chat(self, chat_id: str):
        """Load an existing chat by ID"""
        existing_chat = await chat_service.get_chat(chat_id)
        if not existing_chat:
            self.display_manager.print_error(f"Chat {chat_id} not found")
            raise ValueError(f"Chat {chat_id} not found")

        self.messages = existing_chat.messages
        self.current_chat = existing_chat

        if self.verbose:
            logger.info(f"Loaded {len(self.messages)} messages from chat {chat_id}")

    async def persist_chat(self):
        """Persist current chat state"""
        if not self.current_chat:
            # Create new chat with pre-generated ID
            self.current_chat = await chat_service.create_chat(self.messages, self.external_id, self.chat_id)
        else:
            # Update existing chat - external_id will be preserved automatically
            self.current_chat = await chat_service.update_chat(self.current_chat.id, self.messages, self.external_id)

    async def run(self, prompt: Optional[str] = None):
        """Run the chat session with agent loop."""
        from agent.loop import run_agent_loop
        from agent.tools import get_tools_map, get_openai_tools

        tools_map = get_tools_map()
        openai_tools = get_openai_tools()

        # Load existing chat if continuing
        if self.continue_exist:
            await self._load_chat(self.chat_id)

        # Process initial prompt if provided
        if prompt:
            user_message = create_message("user", prompt, id=generate_message_id())
            self.messages.append(user_message)

            await run_agent_loop(
                provider=self.provider,
                messages=self.messages,
                system_prompt=self._build_system_prompt(),
                tools_map=tools_map,
                openai_tools=openai_tools,
                display_callback=self.display_manager.display_message_panel,
            )
            await self.persist_chat()

        # Continue with follow-up rounds
        while True:
            try:
                user_input, is_multiline, num_lines = self.input_manager.get_input()
            except (KeyboardInterrupt, EOFError):
                break

            if self.input_manager.is_exit_command(user_input):
                break

            if not user_input:
                continue

            # Clear input lines and redisplay user input in a panel
            # For multi-line: <<EOF line + content lines + EOF line = num_lines + 2
            # For single-line: Enter: prompt = 1 line
            clear_lines = num_lines + 2 if is_multiline else 1
            import sys
            sys.stdout.write("\033[A\033[2K" * clear_lines)
            sys.stdout.flush()
            user_message = create_message("user", user_input)
            self.display_manager.display_message_panel(user_message)
            self.messages.append(user_message)

            await run_agent_loop(
                provider=self.provider,
                messages=self.messages,
                system_prompt=self._build_system_prompt(),
                tools_map=tools_map,
                openai_tools=openai_tools,
                display_callback=self.display_manager.display_message_panel,
            )
            await self.persist_chat()
