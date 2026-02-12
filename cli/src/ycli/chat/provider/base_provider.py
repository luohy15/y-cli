from abc import ABC, abstractmethod
from typing import List, Optional

from storage.entity.dto import Message

class BaseProvider(ABC):
    @abstractmethod
    async def call_chat_completions_non_stream(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
        tools: Optional[list] = None,
    ) -> dict:
        """Get a non-streaming chat response.

        Args:
            messages: List of Message objects
            system_prompt: Optional system prompt to add at the start
            tools: Optional list of tool definitions in OpenAI format

        Returns:
            dict: Raw message dict with content, tool_calls, provider, model
        """
        pass
