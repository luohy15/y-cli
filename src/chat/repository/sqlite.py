import json
import aiosqlite
from typing import List, Optional

from chat.models import Chat
from config import config
from . import ChatRepository


class SqliteRepository(ChatRepository):
    """Repository implementation for local SQLite storage."""

    def __init__(self, db_path: Optional[str] = None, user_prefix: Optional[str] = None):
        self.db_path = db_path or config.get('sqlite_file')
        self.user_prefix = user_prefix or config.get('cloudflare_d1', {}).get('user_prefix', 'default')
        self._initialized = False

    async def _get_db(self) -> aiosqlite.Connection:
        db = await aiosqlite.connect(self.db_path)
        db.row_factory = aiosqlite.Row
        if not self._initialized:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS chat (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_prefix TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    json_content TEXT NOT NULL,
                    update_time TEXT,
                    UNIQUE(user_prefix, chat_id)
                )
            """)
            await db.commit()
            self._initialized = True
        return db

    async def _read_chats(self) -> List[Chat]:
        db = await self._get_db()
        try:
            async with db.execute(
                "SELECT json_content FROM chat WHERE user_prefix = ? ORDER BY update_time DESC",
                (self.user_prefix,)
            ) as cursor:
                rows = await cursor.fetchall()
            chats = []
            for row in rows:
                try:
                    chats.append(Chat.from_dict(json.loads(row[0])))
                except Exception as e:
                    print(f"Error parsing chat JSON: {e}")
            return chats
        finally:
            await db.close()

    async def _write_chats(self, chats: List[Chat]) -> None:
        for chat in chats:
            await self.save_chat(chat)

    async def list_chats(self, keyword: Optional[str] = None,
                         model: Optional[str] = None,
                         provider: Optional[str] = None,
                         limit: int = 10) -> List[Chat]:
        params = [self.user_prefix]
        where = "WHERE user_prefix = ?"

        if keyword and keyword.strip():
            for term in keyword.strip().split():
                where += " AND json_content LIKE ?"
                params.append(f"%{term}%")

        if model:
            where += " AND json_content LIKE ?"
            params.append(f"%\"model\":\"%{model}%\"%")

        if provider:
            where += " AND json_content LIKE ?"
            params.append(f"%\"provider\":\"%{provider}%\"%")

        params.append(limit)

        db = await self._get_db()
        try:
            async with db.execute(
                f"SELECT json_content FROM chat {where} ORDER BY update_time DESC LIMIT ?",
                params
            ) as cursor:
                rows = await cursor.fetchall()
            chats = []
            for row in rows:
                try:
                    chats.append(Chat.from_dict(json.loads(row[0])))
                except Exception as e:
                    print(f"Error parsing chat JSON: {e}")
            return chats
        finally:
            await db.close()

    async def get_chat(self, chat_id: str) -> Optional[Chat]:
        db = await self._get_db()
        try:
            async with db.execute(
                "SELECT json_content FROM chat WHERE user_prefix = ? AND chat_id = ?",
                (self.user_prefix, chat_id)
            ) as cursor:
                row = await cursor.fetchone()
            if not row:
                return None
            return Chat.from_dict(json.loads(row[0]))
        except Exception as e:
            print(f"Error parsing chat JSON: {e}")
            return None
        finally:
            await db.close()

    async def add_chat(self, chat: Chat) -> Chat:
        return await self.save_chat(chat)

    async def update_chat(self, chat: Chat) -> Chat:
        existing = await self.get_chat(chat.id)
        if not existing:
            raise ValueError(f"Chat with id {chat.id} not found")
        return await self.save_chat(chat)

    async def delete_chat(self, chat_id: str) -> bool:
        db = await self._get_db()
        try:
            cursor = await db.execute(
                "DELETE FROM chat WHERE user_prefix = ? AND chat_id = ?",
                (self.user_prefix, chat_id)
            )
            await db.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error deleting chat: {e}")
            return False
        finally:
            await db.close()

    async def save_chat(self, chat: Chat) -> Chat:
        from util import get_iso8601_timestamp
        update_time = get_iso8601_timestamp()
        chat.update_time = update_time

        db = await self._get_db()
        try:
            await db.execute(
                "INSERT OR REPLACE INTO chat (user_prefix, chat_id, json_content, update_time) VALUES (?, ?, ?, ?)",
                (self.user_prefix, chat.id, json.dumps(chat.to_dict()), update_time)
            )
            await db.commit()
            return chat
        except Exception as e:
            raise ValueError(f"Failed to save chat: {e}")
        finally:
            await db.close()
