from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from entity.dto import Message, Chat

class BaseProvider(ABC):
    @abstractmethod
    async def call_chat_completions(
        self,
        messages: List[Message],
        chat: Optional[Chat] = None,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Tuple[Message, Optional[str]]:
        """Get a chat response from the provider.

        Args:
            messages: List of Message objects
            chat: Optional chat object
            system_prompt: Optional system prompt to add at the start
            **kwargs: Additional provider-specific arguments (e.g., decision for routing)

        Returns:
            Message: The assistant's response message
            external_id: Optional external ID for the chat

        Raises:
            Exception: If API call fails
        """
        pass

    @abstractmethod
    async def call_chat_completions_non_stream(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
    ) -> str:
        """Get a non-streaming chat response, returning only the content text.

        Args:
            messages: List of Message objects
            system_prompt: Optional system prompt to add at the start

        Returns:
            str: The assistant's response content
        """
        pass
