from typing import List, Dict, Optional
from contextlib import AsyncExitStack
from types import SimpleNamespace

from chat.models import Chat, Message
from .repository import ChatRepository
from .service import ChatService
from cli.display_manager import DisplayManager
from cli.input_manager import InputManager
from mcp_server.mcp_manager import MCPManager
from prompt.preset import time_prompt
from util import generate_id
from .utils.tool_utils import contains_tool_use, split_content
from .utils.message_utils import create_message
from .provider.base_provider import BaseProvider
from bot import BotConfig
from config import prompt_service, mcp_service
from config import config
from loguru import logger

class ChatManager:
    def __init__(
        self,
        repository: ChatRepository,
        display_manager: DisplayManager,
        input_manager: InputManager,
        mcp_manager: MCPManager,
        provider: BaseProvider,
        bot_config: BotConfig,
        chat_id: Optional[str] = None,
        verbose: bool = False
    ):
        """Initialize chat manager with required components.

        Args:
            repository: Repository for chat persistence
            display_manager: Manager for display and UI
            input_manager: Manager for user input
            mcp_manager: Manager for MCP operations
            provider: Chat provider for interactions
            bot_config: Bot configuration
            chat_id: Optional ID of existing chat to load
            verbose: Whether to show verbose output
        """
        self.service = ChatService(repository)
        self.bot_config = bot_config
        self.model = bot_config.model
        self.display_manager = display_manager
        self.input_manager = input_manager
        self.mcp_manager = mcp_manager
        self.provider = provider
        self.verbose = verbose

        # Set up cross-manager references
        self.provider.set_display_manager(display_manager)

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

    async def _load_chat(self, chat_id: str):
        """Load an existing chat by ID"""
        existing_chat = await self.service.get_chat(chat_id)
        if not existing_chat:
            self.display_manager.print_error(f"Chat {chat_id} not found")
            raise ValueError(f"Chat {chat_id} not found")

        self.messages = existing_chat.messages
        self.current_chat = existing_chat

        if self.verbose:
            logger.info(f"Loaded {len(self.messages)} messages from chat {chat_id}")

    def get_user_confirmation(self, content: str, server_name: str = None, tool_name: str = None) -> bool:
        """Get user confirmation before executing tool use

        Args:
            content: The tool use content
            server_name: The MCP server name
            tool_name: The tool name being executed

        Returns:
            bool: True if confirmed, False otherwise
        """
        # Check if auto_confirm is enabled for this tool
        if server_name and tool_name and self.bot_config.mcp_servers:
            server_config = mcp_service.get_config(server_name)
            if server_config and hasattr(server_config, 'auto_confirm') and tool_name in server_config.auto_confirm:
                if self.verbose:
                    logger.info(f"Auto-confirming tool use for {server_name}/{tool_name}")
                return True

        # Otherwise proceed with normal confirmation
        self.display_manager.console.print("\n[yellow]Tool use detected in response:[/yellow]")
        while True:
            response = input("\nWould you like to proceed with tool execution? (y/n): ").strip().lower()
            if response in ['y', 'yes']:
                return True
            elif response in ['n', 'no']:
                return False
            self.display_manager.console.print("[yellow]Please answer 'y' or 'n'[/yellow]")

    async def process_user_message(self, user_message: Message):
        self.messages.append(user_message)
        self.display_manager.display_message_panel(user_message, index=len(self.messages) - 1)

        assistant_message, external_id = await self.provider.call_chat_completions(self.messages, self.current_chat, self.system_prompt)
        if external_id:
            self.external_id = external_id
        await self.process_assistant_message(assistant_message)
        await self.persist_chat()

    async def process_assistant_message(self, assistant_message: Message):
        """Process assistant response and handle tool use recursively"""
        # Extract content and metadata based on response type
        content = assistant_message.content

        if not contains_tool_use(content):
            self.messages.append(assistant_message)
            self.display_manager.display_message_panel(assistant_message, index=len(self.messages) - 1)
            return

        # Handle response with tool use
        plain_content, tool_content = split_content(content)

        # Extract MCP tool info before updating content
        mcp_tool = self.mcp_manager.extract_mcp_tool_use(tool_content)
        if not mcp_tool:
            return
        server_name, tool_name, arguments = mcp_tool
        # Add server, tool, and arguments info to assistant message
        assistant_message.server = server_name
        assistant_message.tool = tool_name
        assistant_message.arguments = arguments

        # Update last assistant message with plain content
        assistant_message.content = plain_content
        self.messages.append(assistant_message)
        self.display_manager.display_message_panel(assistant_message, index=len(self.messages) - 1)

        # Get user confirmation for tool execution
        if not self.get_user_confirmation(tool_content, server_name, tool_name):
            no_exec_msg = "Tool execution cancelled by user."
            self.display_manager.console.print(f"\n[yellow]{no_exec_msg}[/yellow]")
            user_message = create_message("user", no_exec_msg)
            self.messages.append(user_message)
            return

        # Execute tool and get results
        tool_results = await self.mcp_manager.execute_tool(server_name, tool_name, arguments)

        # Create user message with tool results and include tool info
        user_message = create_message("user", tool_results, server=server_name, tool=tool_name, arguments=arguments)

        # Process user message and assistant response recursively
        await self.process_user_message(user_message)

    async def persist_chat(self):
        """Persist current chat state"""
        if not self.current_chat:
            # Create new chat with pre-generated ID
            self.current_chat = await self.service.create_chat(self.messages, self.external_id, self.chat_id)
        else:
            # Update existing chat - external_id will be preserved automatically
            self.current_chat = await self.service.update_chat(self.current_chat.id, self.messages, self.external_id)

    async def run(self):
        """Run the chat session"""
        async with AsyncExitStack() as exit_stack:
            try:
                if self.verbose:
                    logger.info("Starting chat session...")
                # if cloudflare repository, sync
                storage_type = config.get('storage_type', 'file')
                if storage_type == 'cloudflare':
                    await self.service.repository._sync_from_r2_if_needed()
                # Load chat if chat_id was provided and not already loaded
                if self.continue_exist:
                    await self._load_chat(self.chat_id)
                else:
                    pass
                    # await self.service.repository.get_chat(None)
                if self.verbose:
                    logger.info("Chat loaded successfully")

                # Init basic system prompt
                self.system_prompt = time_prompt + "\n"

                # Initialize MCP and system prompt if MCP server settings exist
                if self.bot_config.mcp_servers:
                    await self.mcp_manager.connect_to_servers(self.bot_config.mcp_servers)
                    self.system_prompt += await self.mcp_manager.get_mcp_prompt(self.bot_config.mcp_servers, prompt_service) + "\n"

                # Add additional prompts to system prompt
                if self.bot_config.prompts:
                    for prompt in self.bot_config.prompts:
                        if prompt not in ["mcp"]:
                            prompt_config = prompt_service.get_prompt(prompt)
                            if prompt_config:
                                self.system_prompt += prompt_config.content + "\n"

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
            finally:
                # Clear sessions on exit
                self.mcp_manager.clear_sessions()
