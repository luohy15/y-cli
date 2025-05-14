from typing import Any, List, Dict, Optional, Tuple
from .base_provider import BaseProvider
from .display_manager_mixin import DisplayManagerMixin
import json
import os
import time
from types import SimpleNamespace
import httpx
from chat.models import Message, Chat
from bot.models import BotConfig
from ..utils.message_utils import create_message
from config import config

class TopiaOrchProvider(BaseProvider, DisplayManagerMixin):
    def __init__(self, bot_config: BotConfig):
        """Initialize Topia settings.

        Args:
            bot_config: Bot configuration containing API settings
        """
        DisplayManagerMixin.__init__(self)
        self.bot_config = bot_config
        self.base_url = self.bot_config.base_url
        self.chat_endpoint = "/orchChat/sendChat"

    def _parse_credentials(self):
        """Parse app_id and app_secret from api_key"""
        app_id, app_secret = self.bot_config.api_key.split('|')
        return app_id, app_secret

    def _get_token_file_path(self):
        """Get path to token cache file"""
        return os.path.join(config.get("tmp_dir"), '.topia_token')

    async def _get_cached_token(self):
        """Get token from cache file if valid"""
        try:
            if os.path.exists(self._get_token_file_path()):
                with open(self._get_token_file_path(), 'r') as f:
                    data = json.load(f)
                    if data['expires_at'] > time.time():
                        return data['access_token']
        except:
            pass
        return None

    async def _refresh_and_cache_token(self):
        """Get new token and save to cache"""
        app_id, app_secret = self._parse_credentials()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/login",
                json={"appId": app_id, "appSecret": app_secret}
            )
            data = response.json()['data']

            # Save to cache file
            cache_data = {
                'access_token': data['access_token'],
                'expires_at': time.time() + data['expires_in']
            }
            with open(self._get_token_file_path(), 'w') as f:
                json.dump(cache_data, f)

            return data['access_token']

    async def _get_valid_token(self):
        """Get a valid token, refresh if needed"""
        token = await self._get_cached_token()
        if not token:
            token = await self._refresh_and_cache_token()
        return token

    async def _prepare_headers(self) -> Dict[str, str]:
        """Prepare headers for API request."""
        token = await self._get_valid_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    def _prepare_request_body(self, messages: List[Message], chat_id: str, chat: Optional[Chat] = None) -> Dict[str, Any]:
        """Prepare request body for Topia API."""
        # Get the last user message as content
        user_messages = [msg for msg in messages if msg.role == "user"]
        if not user_messages:
            raise ValueError("No user messages found")

        last_user_msg = user_messages[-1]
        content = last_user_msg.content if isinstance(last_user_msg.content, str) else " ".join(part.text for part in last_user_msg.content)

        # Use chat ID as appUserId if available, otherwise use a default
        app_user_id = chat_id

        body = {
            "appUserId": app_user_id,
            "content": content,
            "orchId": int(self.bot_config.model),  # Use model field as orchId
            "isStream": True  # Always use streaming mode
        }

        return body

    async def call_chat_completions(self, messages: List[Message], chat_id: str, chat: Optional[Chat] = None, system_prompt: Optional[str] = None) -> Tuple[Message, Optional[str]]:
        """Get a chat response from Topia.

        Args:
            messages: List of Message objects
            chat: Optional Chat object to maintain conversation context
            system_prompt: Optional system prompt (not used in Topia)

        Returns:
            Message: The assistant's response message
            external_id: Optional external ID for the chat

        Raises:
            Exception: If API call fails
        """
        if not self.display_manager:
            raise Exception("Display manager not set for streaming response")

        try:
            headers = await self._prepare_headers()
            body = self._prepare_request_body(messages, chat_id, chat)

            async with httpx.AsyncClient(
                base_url=self.base_url,
            ) as client:
                async with client.stream(
                    "POST",
                    self.chat_endpoint,
                    headers=headers,
                    json=body,
                    timeout=60.0
                ) as response:
                    response.raise_for_status()

                    message_id = None
                    content_full = ""

                    async def generate_chunks():
                        nonlocal message_id, content_full
                        current_content = ""  # Track current content

                        async for line in response.aiter_lines():
                            if line.startswith("data:"):
                                try:
                                    data = json.loads(line[5:])

                                    # Handle final message with full details
                                    if "id" in data:
                                        message_id = data.get("id")
                                        # Skip yielding as this is the final message
                                        continue

                                    # Handle streaming content
                                    content = data.get("content", "")
                                    if not content:
                                        current_content = ""  # Reset if empty
                                    else:
                                        # Use difference as delta
                                        delta = content[len(current_content):]
                                        current_content = content  # Update tracking

                                        if delta:  # Only yield if there's new content
                                            chunk_data = SimpleNamespace(
                                                choices=[SimpleNamespace(
                                                    delta=SimpleNamespace(
                                                        content=delta,
                                                        reasoning_content=None
                                                    )
                                                )],
                                                model=self.bot_config.model,
                                                provider="topia"
                                            )
                                            yield chunk_data

                                except json.JSONDecodeError:
                                    continue

                    content_full, _ = await self.display_manager.stream_response(generate_chunks())

                    return create_message(
                        "assistant",
                        content_full,
                        id=message_id,
                        provider="topia",
                        model=self.bot_config.model
                    ), None  # Topia doesn't use external_id

        except httpx.HTTPError as e:
            raise Exception(f"HTTP error getting chat response: {str(e)}")
        except Exception as e:
            raise Exception(f"Error calling Topia API: {str(e)}")
