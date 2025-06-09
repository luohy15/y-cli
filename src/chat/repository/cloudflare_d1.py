import json
import os
from typing import List, Optional, Dict, Any
from datetime import datetime

from chat.models import Chat, Message
from config import config
from . import ChatRepository

class CloudflareD1Repository(ChatRepository):
    """
    Repository implementation for Cloudflare D1 database storage.
    """
    def __init__(self, user_prefix: Optional[str] = None):
        """
        Initialize the Cloudflare D1 repository.
        
        Args:
            user_prefix: Optional user prefix for isolating data (default: from config or 'default')
        """
        self.d1_config = config.get('cloudflare_d1', {})
        self.user_prefix = user_prefix or self.d1_config.get('user_prefix', 'default')
        self.db = self._get_d1_database()

    def _get_d1_database(self):
        """
        Get the D1 database connection.
        This is a placeholder for the actual implementation.
        
        In a real implementation, this would connect to the D1 database
        using the appropriate client library.
        """
        # This is a placeholder - actual implementation would depend on
        # how D1 database is accessed from Python (e.g., via a REST API client)
        from importlib import import_module
        
        try:
            # Import the cloudflare_d1_client module from the same package
            from . import cloudflare_d1_util
            return cloudflare_d1_util.D1Database(
                account_id=self.d1_config.get('account_id'),
                database_id=self.d1_config.get('database_id'),
                api_token=self.d1_config.get('api_token')
            )
        except ImportError:
            # For development/testing, we'll provide a mock implementation
            from unittest.mock import MagicMock
            return MagicMock()

    async def _ensure_schema_exists(self) -> None:
        """
        Initialize the database schema if it doesn't exist.
        """
        # CREATE TABLE IF NOT EXISTS would typically be used here
        await self.db.exec("""
            CREATE TABLE IF NOT EXISTS chat (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                user_prefix TEXT NOT NULL, 
                chat_id TEXT NOT NULL, 
                json_content TEXT NOT NULL, 
                update_time TEXT,
                UNIQUE(user_prefix, chat_id)
            );
        """)

    async def _read_chats(self) -> List[Chat]:
        """
        Read all chats from the D1 database for the current user prefix.
        
        Returns:
            List[Chat]: All chats in storage
        """
        # In a real implementation, this would use the D1 API to query the database
        stmt = self.db.prepare("""
            SELECT json_content FROM chat 
            WHERE user_prefix = ?
            ORDER BY update_time DESC
        """).bind(self.user_prefix)
        results = await stmt.all()

        print(results)
        
        chats = []
        # Handle different result formats - could be a dict with 'results' key or a list directly
        if results:
            result_rows = []
            if isinstance(results, dict) and 'results' in results:
                result_rows = results['results']
            elif isinstance(results, list):
                result_rows = results
                
            for row in result_rows:
                try:
                    chat_dict = json.loads(row['json_content'])
                    chats.append(Chat.from_dict(chat_dict))
                except Exception as e:
                    print(f'Error parsing chat JSON: {e}')
        
        return chats

    async def _write_chats(self, chats: List[Chat]) -> None:
        """
        This method is not directly used in the D1 implementation since
        each chat is saved individually using saveChat.
        
        Args:
            chats: The chats to write
        """
        # D1 implementation uses individual operations instead of batch writes
        for chat in chats:
            await self.save_chat(chat)

    async def list_chats(self, keyword: Optional[str] = None, 
                        model: Optional[str] = None,
                        provider: Optional[str] = None, 
                        limit: int = 10) -> Dict[str, Any]:
        """
        List chats with optional filtering using SQL queries
        
        Args:
            keyword: Optional text to filter messages by content
            model: Optional model name to filter by
            provider: Optional provider name to filter by
            limit: Maximum number of chats to return (default: 10)
            
        Returns:
            Dict[str, Any]: Dictionary containing chats and total count
                {
                    'chats': List[Chat],  # The filtered chats
                    'total': int,         # Total number of matching chats
                    'limit': int          # Number of items per page
                }
        """
        # Setup basic query parameters
        bind_params = [self.user_prefix]
        where_clause = "WHERE user_prefix = ?"
        
        # Process keyword search if provided
        if keyword and keyword.strip():
            # Split search by spaces to handle multiple search terms
            search_terms = keyword.strip().split()
            
            if search_terms:
                # Add a LIKE condition for each search term
                search_clauses = " AND ".join(["json_content LIKE ?" for _ in search_terms])
                where_clause += f" AND ({search_clauses})"
                
                # Add each search term as a parameter with wildcards
                for term in search_terms:
                    bind_params.append(f"%{term}%")
        
        # Add model filter if provided
        if model:
            where_clause += " AND json_content LIKE ?"
            bind_params.append(f"%\"model\":\"%{model}%\"%")
            
        # Add provider filter if provided
        if provider:
            where_clause += " AND json_content LIKE ?"
            bind_params.append(f"%\"provider\":\"%{provider}%\"%")
        
        # Get results with limit
        query = f"""
            SELECT json_content FROM chat 
            {where_clause}
            ORDER BY update_time DESC
            LIMIT ?
        """
        
        # Add limit parameter
        bind_params.append(limit)
        
        stmt = self.db.prepare(query).bind(*bind_params)
        results = await stmt.all()
        results = results[-1]
        
        chats = []
        if results:
            result_rows = []
            if isinstance(results, dict) and 'results' in results:
                result_rows = results['results']
                for row in result_rows:
                    try:
                        chat_dict = json.loads(row['json_content'])
                        chats.append(Chat.from_dict(chat_dict))
                    except Exception as e:
                        print(f'Error parsing chat JSON: {e}')
        
        return chats

    async def get_chat(self, chat_id: str) -> Optional[Chat]:
        """
        Get a specific chat by ID
        
        Args:
            chat_id: The ID of the chat to retrieve
            
        Returns:
            Optional[Chat]: The chat if found, None otherwise
        """
        stmt = self.db.prepare("""
            SELECT json_content FROM chat 
            WHERE user_prefix = ? AND chat_id = ?
        """).bind(self.user_prefix, chat_id)
        result = await stmt.first()
        
        if not result:
            return None
        
        result = result['results'][-1]
        
        try:
            return Chat.from_dict(json.loads(result['json_content']))
        except Exception as e:
            print(f'Error parsing chat JSON: {e}')
            return None

    async def add_chat(self, chat: Chat) -> Chat:
        """
        Add a new chat
        
        Args:
            chat: The chat to add
            
        Returns:
            Chat: The added chat
        """
        # For D1, we use save_chat for both adding and updating
        return await self.save_chat(chat)

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
        # Check if the chat exists first
        existing_chat = await self.get_chat(chat.id)
        if not existing_chat:
            raise ValueError(f"Chat with id {chat.id} not found")
        
        # For D1, we use save_chat for both adding and updating
        return await self.save_chat(chat)

    async def delete_chat(self, chat_id: str) -> bool:
        """
        Delete a chat by ID
        
        Args:
            chat_id: The ID of the chat to delete
            
        Returns:
            bool: True if the chat was deleted, False if it wasn't found
        """
        try:
            stmt = self.db.prepare("""
                DELETE FROM chat
                WHERE user_prefix = ? AND chat_id = ?
            """).bind(self.user_prefix, chat_id)
            result = await stmt.run()
            
            # Check if any rows were affected
            return result.get('changes', 0) > 0
        except Exception as e:
            print(f'Error deleting chat: {e}')
            return False

    async def save_chat(self, chat: Chat) -> Chat:
        """
        Save a chat (insert or update)
        
        Args:
            chat: The chat to save
            
        Returns:
            Chat: The saved chat
        """
        # Update the chat's update_time
        from util import get_iso8601_timestamp
        update_time = get_iso8601_timestamp()
        chat.update_time = update_time
        
        try:
            # Insert or replace the chat in the database
            stmt = self.db.prepare("""
                INSERT OR REPLACE INTO chat (user_prefix, chat_id, json_content, update_time)
                VALUES (?, ?, ?, ?)
            """).bind(
                self.user_prefix,
                chat.id,
                json.dumps(chat.to_dict()),
                update_time
            )
            await stmt.run()
            
            return chat
        except Exception as e:
            print(f'Error saving chat to D1: {e}')
            raise ValueError(f"Failed to save chat: {e}")

    async def save_chats(self, chats: List[Chat]) -> Dict[str, int]:
        """
        Save multiple chats in batch
        
        Args:
            chats: Array of chats to save
            
        Returns:
            Dict: Object with operation statistics
        """
        success = 0
        failed = 0
        
        # In a real implementation, this would be a batch operation
        # but for now, we'll use individual operations
        for chat in chats:
            try:
                await self.save_chat(chat)
                success += 1
            except Exception as e:
                print(f'Error migrating chat {chat.id}: {e}')
                failed += 1
        
        return {
            'total': len(chats),
            'success': success,
            'failed': failed
        }
