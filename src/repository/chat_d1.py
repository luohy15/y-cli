import json
from typing import List, Optional, Dict, Any

from entity.dto import Chat
from config import config
from repository import chat_d1_util


def _get_db():
    d1_config = config.get('cloudflare_d1', {})
    return chat_d1_util.D1Database(
        account_id=d1_config.get('account_id'),
        database_id=d1_config.get('database_id'),
        api_token=d1_config.get('api_token')
    )


def _get_user_prefix():
    return config.get('cloudflare_d1', {}).get('user_prefix', 'default')


async def _read_chats() -> List[Chat]:
    user_prefix = _get_user_prefix()
    db = _get_db()
    stmt = db.prepare("""
        SELECT json_content FROM chat
        WHERE user_prefix = ?
        ORDER BY update_time DESC
    """).bind(user_prefix)
    results = await stmt.all()

    print(results)

    chats = []
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


async def _write_chats(chats: List[Chat]) -> None:
    for chat in chats:
        await save_chat(chat)


async def list_chats(keyword: Optional[str] = None,
                    model: Optional[str] = None,
                    provider: Optional[str] = None,
                    limit: int = 10) -> List[Chat]:
    user_prefix = _get_user_prefix()
    db = _get_db()
    bind_params = [user_prefix]
    where_clause = "WHERE user_prefix = ?"

    if keyword and keyword.strip():
        search_terms = keyword.strip().split()
        if search_terms:
            search_clauses = " AND ".join(["json_content LIKE ?" for _ in search_terms])
            where_clause += f" AND ({search_clauses})"
            for term in search_terms:
                bind_params.append(f"%{term}%")

    if model:
        where_clause += " AND json_content LIKE ?"
        bind_params.append(f"%\"model\":\"%{model}%\"%")

    if provider:
        where_clause += " AND json_content LIKE ?"
        bind_params.append(f"%\"provider\":\"%{provider}%\"%")

    query = f"""
        SELECT json_content FROM chat
        {where_clause}
        ORDER BY update_time DESC
        LIMIT ?
    """
    bind_params.append(limit)

    stmt = db.prepare(query).bind(*bind_params)
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


async def get_chat(chat_id: str) -> Optional[Chat]:
    user_prefix = _get_user_prefix()
    db = _get_db()
    stmt = db.prepare("""
        SELECT json_content FROM chat
        WHERE user_prefix = ? AND chat_id = ?
    """).bind(user_prefix, chat_id)
    result = await stmt.first()

    if not result:
        return None

    result = result['results'][-1]

    try:
        return Chat.from_dict(json.loads(result['json_content']))
    except Exception as e:
        print(f'Error parsing chat JSON: {e}')
        return None


async def add_chat(chat: Chat) -> Chat:
    return await save_chat(chat)


async def update_chat(chat: Chat) -> Chat:
    existing_chat = await get_chat(chat.id)
    if not existing_chat:
        raise ValueError(f"Chat with id {chat.id} not found")
    return await save_chat(chat)


async def delete_chat(chat_id: str) -> bool:
    user_prefix = _get_user_prefix()
    db = _get_db()
    try:
        stmt = db.prepare("""
            DELETE FROM chat
            WHERE user_prefix = ? AND chat_id = ?
        """).bind(user_prefix, chat_id)
        result = await stmt.run()
        return result.get('changes', 0) > 0
    except Exception as e:
        print(f'Error deleting chat: {e}')
        return False


async def save_chat(chat: Chat) -> Chat:
    from util import get_iso8601_timestamp
    user_prefix = _get_user_prefix()
    db = _get_db()
    update_time = get_iso8601_timestamp()
    chat.update_time = update_time

    try:
        stmt = db.prepare("""
            INSERT OR REPLACE INTO chat (user_prefix, chat_id, json_content, update_time)
            VALUES (?, ?, ?, ?)
        """).bind(
            user_prefix,
            chat.id,
            json.dumps(chat.to_dict()),
            update_time
        )
        await stmt.run()
        return chat
    except Exception as e:
        print(f'Error saving chat to D1: {e}')
        raise ValueError(f"Failed to save chat: {e}")


async def save_chats(chats: List[Chat]) -> Dict[str, int]:
    success = 0
    failed = 0
    for chat in chats:
        try:
            await save_chat(chat)
            success += 1
        except Exception as e:
            print(f'Error migrating chat {chat.id}: {e}')
            failed += 1
    return {'total': len(chats), 'success': success, 'failed': failed}
