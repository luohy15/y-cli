import json
import aiosqlite
from typing import List, Optional

from entity.dto import Chat
from config import config

_initialized = False


async def _get_db(db_path=None) -> aiosqlite.Connection:
    global _initialized
    path = db_path or config.get('sqlite_file')
    db = await aiosqlite.connect(path)
    db.row_factory = aiosqlite.Row
    if not _initialized:
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
        _initialized = True
    return db


def _get_user_prefix():
    return config.get('cloudflare_d1', {}).get('user_prefix', 'default')


async def _read_chats(db_path=None) -> List[Chat]:
    user_prefix = _get_user_prefix()
    db = await _get_db(db_path)
    try:
        async with db.execute(
            "SELECT json_content FROM chat WHERE user_prefix = ? ORDER BY update_time DESC",
            (user_prefix,)
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


async def _write_chats(chats: List[Chat], db_path=None) -> None:
    for chat in chats:
        await save_chat(chat, db_path)


async def list_chats(keyword: Optional[str] = None,
                     model: Optional[str] = None,
                     provider: Optional[str] = None,
                     limit: int = 10) -> List[Chat]:
    user_prefix = _get_user_prefix()
    params = [user_prefix]
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

    db = await _get_db()
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


async def get_chat(chat_id: str) -> Optional[Chat]:
    user_prefix = _get_user_prefix()
    db = await _get_db()
    try:
        async with db.execute(
            "SELECT json_content FROM chat WHERE user_prefix = ? AND chat_id = ?",
            (user_prefix, chat_id)
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


async def add_chat(chat: Chat) -> Chat:
    return await save_chat(chat)


async def update_chat(chat: Chat) -> Chat:
    existing = await get_chat(chat.id)
    if not existing:
        raise ValueError(f"Chat with id {chat.id} not found")
    return await save_chat(chat)


async def delete_chat(chat_id: str) -> bool:
    user_prefix = _get_user_prefix()
    db = await _get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM chat WHERE user_prefix = ? AND chat_id = ?",
            (user_prefix, chat_id)
        )
        await db.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Error deleting chat: {e}")
        return False
    finally:
        await db.close()


async def save_chat(chat: Chat, db_path=None) -> Chat:
    from util import get_iso8601_timestamp
    user_prefix = _get_user_prefix()
    update_time = get_iso8601_timestamp()
    chat.update_time = update_time

    db = await _get_db(db_path)
    try:
        await db.execute(
            "INSERT OR REPLACE INTO chat (user_prefix, chat_id, json_content, update_time) VALUES (?, ?, ?, ?)",
            (user_prefix, chat.id, json.dumps(chat.to_dict()), update_time)
        )
        await db.commit()
        return chat
    except Exception as e:
        raise ValueError(f"Failed to save chat: {e}")
    finally:
        await db.close()
