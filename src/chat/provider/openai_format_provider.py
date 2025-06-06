from typing import List, Dict, Optional, AsyncGenerator, Tuple
from .base_provider import BaseProvider
from .display_manager_mixin import DisplayManagerMixin
import json
from types import SimpleNamespace
import httpx
from chat.models import Message, Chat
from bot.models import BotConfig
from ..utils.message_utils import create_message

class OpenAIFormatProvider(BaseProvider, DisplayManagerMixin):
    def __init__(self, bot_config: BotConfig):
        """Initialize OpenRouter settings.

        Args:
            bot_config: Bot configuration containing API settings
        """
        DisplayManagerMixin.__init__(self)
        self.bot_config = bot_config

    def prepare_messages_for_completion(self, messages: List[Message], system_prompt: Optional[str] = None) -> List[Dict]:
        """Prepare messages for completion by adding system message and cache_control.

        Args:
            messages: Original list of Message objects
            system_prompt: Optional system message to add at the start

        Returns:
            List[Dict]: New message list with system message and cache_control added
        """
        # Create new list starting with system message if provided
        prepared_messages = []
        if system_prompt:
            system_message = create_message('system', system_prompt)
            system_message_dict = system_message.to_dict()
            if isinstance(system_message_dict["content"], str):
                system_message_dict["content"] = [{"type": "text", "text": system_message_dict["content"]}]
            # Remove timestamp fields, otherwise likely unsupported_country_region_territory
            system_message_dict.pop("timestamp", None)
            system_message_dict.pop("unix_timestamp", None)
            # add cache_control only to claude-3 series model
            if "claude-3" in self.bot_config.model:
                for part in system_message_dict["content"]:
                    if part.get("type") == "text":
                        part["cache_control"] = {"type": "ephemeral"}
            prepared_messages.append(system_message_dict)

        # Add original messages
        for msg in messages:
            msg_dict = msg.to_dict()
            if isinstance(msg_dict["content"], list):
                msg_dict["content"] = [dict(part) for part in msg_dict["content"]]
            # Remove timestamp fields, otherwise likely unsupported_country_region_territory
            msg_dict.pop("timestamp", None)
            msg_dict.pop("unix_timestamp", None)
            prepared_messages.append(msg_dict)

        # Find last user message
        if "claude-3" in self.bot_config.model:
            for msg in reversed(prepared_messages):
                if msg["role"] == "user":
                    if isinstance(msg["content"], str):
                        msg["content"] = [{"type": "text", "text": msg["content"]}]
                    # Add cache_control to last text part
                    text_parts = [part for part in msg["content"] if part.get("type") == "text"]
                    if text_parts:
                        last_text_part = text_parts[-1]
                    else:
                        last_text_part = {"type": "text", "text": "..."}
                        msg["content"].append(last_text_part)
                    last_text_part["cache_control"] = {"type": "ephemeral"}
                    break

        return prepared_messages

    async def call_chat_completions(self, messages: List[Message], chat: Optional[Chat] = None, system_prompt: Optional[str] = None) -> Tuple[Message, Optional[str]]:
        """Get a streaming chat response from OpenRouter.

        Args:
            messages: List of Message objects
            system_prompt: Optional system prompt to add at the start

        Returns:
            Message: The assistant's response message

        Raises:
            Exception: If API call fails
        """
        # Prepare messages with cache_control and system message
        prepared_messages = self.prepare_messages_for_completion(messages, system_prompt)
        body = {
            "model": self.bot_config.model,
            "messages": prepared_messages,
            "stream": True
        }
        if "deepseek-r1" in self.bot_config.model:
            body["include_reasoning"] = True
        if self.bot_config.openrouter_config and "provider" in self.bot_config.openrouter_config:
            body["provider"] = self.bot_config.openrouter_config["provider"]
        if self.bot_config.max_tokens:
            body["max_tokens"] = self.bot_config.max_tokens
        if self.bot_config.reasoning_effort:
            body["reasoning_effort"] = self.bot_config.reasoning_effort
        try:
            async with httpx.AsyncClient(
                base_url=self.bot_config.base_url,
            ) as client:
                async with client.stream(
                    "POST",
                    self.bot_config.custom_api_path if self.bot_config.custom_api_path else "/chat/completions",
                    headers={
                        "HTTP-Referer": "https://luohy15.com",
                        'X-Title': 'y-cli',
                        "Authorization": f"Bearer {self.bot_config.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                    timeout=60.0
                ) as response:
                    response.raise_for_status()

                    if not self.display_manager:
                        raise Exception("Display manager not set for streaming response")

                    # Store provider and model info from first response chunk
                    provider = None
                    model = None
                    links = None

                    async def generate_chunks():
                        nonlocal provider, model, links
                        async for chunk in response.aiter_lines():
                            if chunk.startswith("data: "):
                                try:
                                    data = json.loads(chunk[6:])
                                    # Extract provider and model from first chunk that has them
                                    if provider is None and data.get("provider"):
                                        provider = data["provider"]
                                    if model is None and data.get("model"):
                                        model = data["model"]
                                    
                                    # Extract Perplexity-specific links from response
                                    if links is None and provider and "perplexity" in provider.lower():
                                        if data.get("links"):
                                            links = data["links"]
                                        elif data.get("citations"):
                                            links = data["citations"]
                                        elif data.get("references"):
                                            links = data["references"]

                                    if data.get("choices"):
                                        delta = data["choices"][0].get("delta", {})
                                        content = delta.get("content")
                                        reasoning_content = delta.get("reasoning_content") if delta.get("reasoning_content") else delta.get("reasoning")
                                        if content is not None or reasoning_content is not None:
                                            chunk_data = SimpleNamespace(
                                                choices=[SimpleNamespace(
                                                    delta=SimpleNamespace(content=content, reasoning_content=reasoning_content)
                                                )],
                                                model=model,
                                                provider=provider
                                            )
                                            yield chunk_data
                                except json.JSONDecodeError:
                                    continue
                    content_full, reasoning_content_full = await self.display_manager.stream_response(generate_chunks())
                    # build assistant message
                    assistant_message = create_message(
                        "assistant",
                        content_full,
                        reasoning_content=reasoning_content_full,
                        provider=provider if provider is not None else self.bot_config.name,
                        model=model,
                        reasoning_effort=self.bot_config.reasoning_effort if self.bot_config.reasoning_effort else None,
                        links=links
                    )
                    return assistant_message, None

        except httpx.HTTPError as e:
            raise Exception(f"HTTP error getting chat response: {str(e)}")
        except Exception as e:
            raise Exception(f"Error getting chat response: {str(e)}")
