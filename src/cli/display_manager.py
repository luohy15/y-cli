import re
import time
import asyncio
from typing import List, Tuple, Optional
from chat.models import Message
from config import config
from bot.models import BotConfig
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.theme import Theme
from rich.live import Live
from collections import deque
import sys

# Custom theme for role-based colors
custom_theme = Theme({
    "user": "green",
    "assistant": "cyan",
    'system': "yellow",
    "tool": "blue",
    "timestamp": "dim white",
})

class StreamBuffer:
    def __init__(self, max_chars_per_second: int):
        self.buffer = ""
        self.max_chars_per_second = max_chars_per_second
        self.last_update_time = time.time()
        self.last_position = 0

    def add_content(self, content: str):
        self.buffer += content

    def get_next_chunk(self) -> str:
        current_time = time.time()
        time_diff = current_time - self.last_update_time
        max_chars = int(self.max_chars_per_second * time_diff)

        if max_chars > 0:
            chunk = self.buffer[self.last_position:self.last_position + max_chars]
            self.last_position += len(chunk)
            self.last_update_time = current_time
            return chunk
        return ""

    @property
    def has_remaining(self) -> bool:
        return self.last_position < len(self.buffer)

class DisplayManager:
    def __init__(self, bot_config: Optional[BotConfig] = None):
        self.console = Console(theme=custom_theme)
        self.max_chars_per_second = bot_config.print_speed if bot_config and bot_config.print_speed else 1000

    def display_message_panel(self, message: Message, index: Optional[int] = None):
        """Display a message in a panel with role-colored borders.

        Args:
            message: The Message object containing role, content, and other attributes
            index: Optional index of the message in the chat history
        """
        timestamp = f"[timestamp]{message.timestamp}[/timestamp]"
        role = f"[{message.role}]{message.role.capitalize()}[/{message.role}]"
        index_str = f"[{index}] " if index is not None else ""

        # Add model/provider info if available
        model_info = ""
        if message.model:
            provider = f" @ {message.provider}" if message.provider else ""
            reasoning = f" (effort: {message.reasoning_effort})" if message.reasoning_effort else ""
            model_info = f" {message.model}{provider}{reasoning}"

        # Extract content text from structured content if needed
        content = message.content
        if isinstance(content, list):
            content = next((part.text for part in content if part.type == 'text'), '')

        # replace <thinking> and </thinking> with thinking emoji
        for tag in ['<thinking>', '</thinking>']:
            content = content.replace(tag, '🤔')

        # Construct display content with reasoning first
        display_content = ""
        if message.reasoning_content:
            display_content = f"```markdown\n{message.reasoning_content}\n```\n"
        display_content += content

        # Add MCP server/tool info if available
        if message.role == "assistant" and (message.server or message.tool):
            mcp_info = "```\n"
            if message.server:
                mcp_info += f"Server: {message.server}\n"
            if message.tool:
                mcp_info += f"Tool: {message.tool}\n"
            if message.arguments:
                import json
                mcp_info += f"Arguments: {json.dumps(message.arguments, indent=2, ensure_ascii=False)}\n"
            mcp_info += "```\n"
            display_content += f"\n{mcp_info}"

        # Add Perplexity reference links if available
        if message.role == "assistant" and message.links and message.provider and "perplexity" in message.provider.lower():
            links_info = "\n\n**References:**\n"
            for i, link in enumerate(message.links, 1):
                if isinstance(link, dict):
                    # Handle structured link objects
                    title = link.get('title', link.get('url', f'Reference {i}'))
                    url = link.get('url', link.get('link', ''))
                    links_info += f"{i}. [{title}]({url})\n"
                else:
                    # Handle simple string URLs
                    links_info += f"{i}. [{link}]({link})\n"
            display_content += links_info

        # Determine border style - change User to Assistant style if has MCP info
        border_style = message.role
        if message.role == "user" and (message.server or message.tool):
            role = f"[tool]Tool[tool]"
            border_style = "tool"  # Use Assistant color for User with MCP info
            model_info = f" {message.tool} @ {message.server}"  # Clear model info for User with MCP info

        self.console.print(Panel(
            Markdown(display_content),
            title=f"{index_str}{role} {timestamp}{model_info}",
            border_style=border_style
        ))

    async def _collect_stream_content(self, response_stream, stream_buffer: StreamBuffer) -> Tuple[str, str]:
        """Collect content from the response stream and add it to the buffer.

        Args:
            response_stream: The streaming response from OpenRouter API
            stream_buffer: The buffer to store content for rate-limited display

        Returns:
            Tuple[str, str]: A tuple containing (complete response text, reasoning text)
        """
        all_content = ""
        all_reasoning_content = ""
        collected_content = []
        collected_reasoning_content = []
        is_reasoning = False

        async for chunk in response_stream:
            delta = chunk.choices[0].delta
            content = delta.content
            reasoning_content = delta.reasoning_content
            new_content = ""

            if reasoning_content:
                if not is_reasoning:
                    is_reasoning = True
                    new_content += "> reasoning\n"
                new_content += reasoning_content
                all_reasoning_content += reasoning_content
                collected_reasoning_content.append(reasoning_content)

            if is_reasoning and not reasoning_content and content:
                new_content += "> summary\n"
                is_reasoning = False

            if content:
                new_content += content
                all_content += content
                collected_content.append(content)

            if new_content:
                stream_buffer.add_content(new_content)

        return "".join(collected_content), "".join(collected_reasoning_content)

    def _update_display_buffer(self, content_buffer: deque, new_content: str):
        """Update the display buffer with new content.

        Args:
            content_buffer: The deque buffer for display content
            new_content: New content to add to the buffer
        """
        first_part, *rest = new_content.split('\n')
        if not content_buffer:
            content_buffer.append(first_part)
        else:
            content_buffer[-1] += first_part
        content_buffer.extend(rest)

    async def stream_response(self, response_stream) -> Tuple[str, str]:
        """Stream and display the response in real-time with rate-limited updates.

        Args:
            response_stream: The streaming response from OpenRouter API

        Returns:
            Tuple[str, str]: A tuple containing (complete response text, reasoning text)
        """
        stream_buffer = StreamBuffer(max_chars_per_second=self.max_chars_per_second)
        max_lines = self.console.height
        content_buffer = deque(maxlen=max_lines)

        # Start content collection task
        collection_task = asyncio.create_task(
            self._collect_stream_content(response_stream, stream_buffer)
        )

        # Display task with rate limiting
        with Live(console=self.console, refresh_per_second=10) as live:
            while True:
                if collection_task.done():
                    live.update("")
                    break

                chunk = stream_buffer.get_next_chunk()
                if chunk:
                    self._update_display_buffer(content_buffer, chunk)
                    live.update("\n".join(content_buffer))
                else:
                    await asyncio.sleep(0.05)  # Small delay only when no content to display

        # Clear empty line
        self.clear_lines(1)

        return await collection_task

    def display_help(self):
        """Display help information about available commands and features"""
        help_content = """
[bold]Available Commands:[/bold]

• Enter 'exit' or 'quit' to end the conversation
• Enter your message and press Enter to send

[bold]Multi-line Input:[/bold]
1. Type <<EOF and press Enter
2. Type your multi-line message
3. Type EOF and press Enter to finish

[bold]Message Copying:[/bold]
• Messages are indexed starting from 0
• Use 'copy n' to copy message n (e.g., 'copy 0' for first message)
"""
        self.console.print(Panel(
            Markdown(help_content),
            title="[bold]Help Information[/bold]",
            border_style="yellow"
        ))

    def display_chat_history(self, messages: List[Message]):
        """Display the chat history, skipping system messages"""
        if messages:
            history_messages = [msg for msg in messages if msg.role != 'system']
            if history_messages:
                for i, message in enumerate(history_messages):
                    self.display_message_panel(message, index=i)
                self.console.print(Panel(
                    "[bold]Type your message to continue the conversation[/bold]",
                    border_style="yellow"
                ))

    def print_error(self, error: str, show_traceback: bool = False):
        """Display an error message with optional traceback in a panel"""
        error_content = f"[red]{error}[/red]"
        if show_traceback and hasattr(error, '__traceback__'):
            import traceback
            error_content += f"\n\n[red]Detailed error:\n{''.join(traceback.format_tb(error.__traceback__))}[/red]"

        self.console.print(Panel(
            Markdown(error_content),
            title="[red]Error[/red]",
            border_style="red"
        ))

    def clear_lines(self, lines: int):
        """Clear the specified number of lines using ANSI escape sequences

        Args:
            lines: Number of lines to clear
        """
        for _ in range(lines):
            sys.stdout.write("\033[F")   # Cursor up one line
