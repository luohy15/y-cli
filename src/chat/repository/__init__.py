from abc import ABC, abstractmethod
from typing import List, Optional
from chat.models import Chat

class ChatRepository(ABC):
    """
    Abstract base class for chat repository implementations.
    Defines the interface for storing and retrieving chat data.
    """
    
    @abstractmethod
    async def list_chats(self, keyword: Optional[str] = None, 
                        model: Optional[str] = None,
                        provider: Optional[str] = None, 
                        limit: int = 10) -> List[Chat]:
        """
        List chats with optional filtering
        
        Args:
            keyword: Optional text to filter messages by content
            model: Optional model name to filter by
            provider: Optional provider name to filter by
            limit: Maximum number of chats to return (default: 10)
            
        Returns:
            List[Chat] or Dict: Filtered list of chats or dictionary with chats
        """
        pass
    
    @abstractmethod
    async def get_chat(self, chat_id: str) -> Optional[Chat]:
        """
        Get a specific chat by ID
        
        Args:
            chat_id: The ID of the chat to retrieve
            
        Returns:
            Optional[Chat]: The chat if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def add_chat(self, chat: Chat) -> Chat:
        """
        Add a new chat
        
        Args:
            chat: The chat to add
            
        Returns:
            Chat: The added chat
        """
        pass
    
    @abstractmethod
    async def update_chat(self, chat: Chat) -> Chat:
        """
        Update an existing chat
        
        Args:
            chat: The chat with updated data
            
        Returns:
            Chat: The updated chat
            
        Raises:
            ValueError: If the chat with the given ID doesn't exist
        """
        pass
    
    @abstractmethod
    async def delete_chat(self, chat_id: str) -> bool:
        """
        Delete a chat by ID
        
        Args:
            chat_id: The ID of the chat to delete
            
        Returns:
            bool: True if the chat was deleted, False if it wasn't found
        """
        pass
    
    @abstractmethod
    async def _read_chats(self) -> List[Chat]:
        """
        Read all chats from the storage
        
        Returns:
            List[Chat]: All chats in storage
        """
        pass
    
    @abstractmethod
    async def _write_chats(self, chats: List[Chat]) -> None:
        """
        Write all chats to the storage
        
        Args:
            chats: The chats to write
        """
        pass
