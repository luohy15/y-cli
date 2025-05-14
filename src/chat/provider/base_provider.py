from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from chat.models import Message, Chat

class BaseProvider(ABC):
    @abstractmethod
    async def call_chat_completions(self, messages: List[Message], chat_id: str, chat: Optional[Chat] = None, system_prompt: Optional[str] = None) -> Tuple[Message, Optional[str]]:
        """Get a chat response from the provider.
        
        Args:
            messages: List of Message objects
            system_prompt: Optional system prompt to add at the start
            
        Returns:
            Message: The assistant's response message
            external_id: Optional external ID for the chat
            
        Raises:
            Exception: If API call fails
        """
        pass
