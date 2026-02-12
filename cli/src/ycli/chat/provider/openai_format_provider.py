from typing import List, Dict, Optional, Tuple
from .base_provider import BaseProvider
from .display_manager_mixin import DisplayManagerMixin
import json
from loguru import logger
from types import SimpleNamespace
import httpx
from storage.entity.dto import Message, Chat, BotConfig
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

    async def call_chat_completions(
        self,
        messages: List[Message],
        chat: Optional[Chat] = None,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Tuple[Message, Optional[str]]:
        """Get a streaming chat response from OpenRouter with smart routing.

        Args:
            messages: List of Message objects
            chat: Optional chat object
            system_prompt: Optional system prompt to add at the start
            **kwargs: Additional arguments including decision (RoutingDecision)

        Returns:
            Message: The assistant's response message

        Raises:
            Exception: If API call fails
        """
        # Extract decision from kwargs
        decision = kwargs.get('decision', None)

        # Determine model name based on routing decision
        model_name = self.bot_config.model
        if decision and decision.use_web_search:
            model_name = f"{model_name}:online"

        # Prepare messages with cache_control and system message
        prepared_messages = self.prepare_messages_for_completion(messages, system_prompt)
        body = {
            "model": model_name,  # May include :online suffix
            "messages": prepared_messages,
            "stream": True
        }

        # Add reasoning parameter if think mode (from routing decision)
        if decision and decision.use_think_model:
            body["reasoning"] = {
                "enabled": True,
                "effort": decision.reasoning_effort
            }

        if "deepseek-r1" in self.bot_config.model:
            body["include_reasoning"] = True
        if self.bot_config.openrouter_config and "provider" in self.bot_config.openrouter_config:
            body["provider"] = self.bot_config.openrouter_config["provider"]
        if self.bot_config.max_tokens:
            body["max_tokens"] = self.bot_config.max_tokens
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
                    links = []

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
                                    if provider and "perplexity" in provider.lower():
                                        if data.get("links"):
                                            links = data["links"]
                                        elif data.get("citations"):
                                            links = data["citations"]
                                        elif data.get("references"):
                                            links = data["references"]

                                    # Extract URLs from OpenRouter annotations (standardized format)
                                    if data.get("choices"):
                                        choice = data["choices"][0]
                                        delta = choice.get("delta", {})
                                        # Check for annotations in the delta
                                        if delta.get("annotations"):
                                            for annotation in delta["annotations"]:
                                                if annotation.get("type") == "url_citation":
                                                    url_citation = annotation.get("url_citation", {})
                                                    url = url_citation.get("url")
                                                    title = url_citation.get("title")
                                                    if url:
                                                        # Use "title|url" format when both are available
                                                        link_entry = f"{title}|{url}" if title else url
                                                        if link_entry not in links:
                                                            links.append(link_entry)
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
                        reasoning_effort=decision.reasoning_effort if decision and decision.use_think_model else None,
                        links=links if links else None
                    )
                    return assistant_message, None

        except httpx.HTTPError as e:
            raise Exception(f"HTTP error getting chat response: {str(e)}")
        except Exception as e:
            raise Exception(f"Error getting chat response: {str(e)}")

    async def call_chat_completions_non_stream(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
    ) -> str:
        """Get a non-streaming chat response, returning only the content text."""
        prepared_messages = self.prepare_messages_for_completion(messages, system_prompt)
        body = {
            "model": self.bot_config.model,
            "messages": prepared_messages,
            "stream": False,
        }
        if self.bot_config.max_tokens:
            body["max_tokens"] = self.bot_config.max_tokens

        try:
            async with httpx.AsyncClient(base_url=self.bot_config.base_url) as client:
                response = await client.post(
                    self.bot_config.custom_api_path if self.bot_config.custom_api_path else "/chat/completions",
                    headers={
                        "HTTP-Referer": "https://luohy15.com",
                        "X-Title": "y-cli",
                        "Authorization": f"Bearer {self.bot_config.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                    timeout=60.0,
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except httpx.HTTPError as e:
            raise Exception(f"HTTP error getting chat response: {str(e)}")
        except Exception as e:
            raise Exception(f"Error getting chat response: {str(e)}")
