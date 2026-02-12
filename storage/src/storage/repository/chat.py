"""Chat repository using SQLAlchemy ORM."""

import json
from typing import List, Optional
from dataclasses import dataclass

from sqlalchemy.orm import defer

from storage.entity.chat import ChatEntity
from storage.entity.dto import Chat
from storage.database.base import get_db
from storage.repository.user import get_current_user_db_id


@dataclass
class ChatSummary:
    chat_id: str
    title: str
    created_at: str
    updated_at: str


def _entity_to_chat(entity: ChatEntity) -> Chat:
    return Chat.from_dict(json.loads(entity.json_content))


async def list_chats(limit: int = 10) -> List[ChatSummary]:
    with get_db() as session:
        user_id = get_current_user_db_id(session)
        rows = (session.query(ChatEntity)
                .filter_by(user_id=user_id)
                .options(defer(ChatEntity.json_content))
                .order_by(ChatEntity.updated_at.desc())
                .limit(limit)
                .all())
        return [
            ChatSummary(
                chat_id=row.chat_id,
                title=row.title or "",
                created_at=str(row.created_at) if row.created_at else "",
                updated_at=str(row.updated_at) if row.updated_at else "",
            )
            for row in rows
        ]


async def get_chat(chat_id: str) -> Optional[Chat]:
    with get_db() as session:
        user_id = get_current_user_db_id(session)
        row = session.query(ChatEntity).filter_by(user_id=user_id, chat_id=chat_id).first()
        if not row:
            return None
        try:
            return _entity_to_chat(row)
        except Exception as e:
            print(f"Error parsing chat JSON: {e}")
            return None


async def add_chat(chat: Chat) -> Chat:
    return await save_chat(chat)


async def update_chat(chat: Chat) -> Chat:
    existing = await get_chat(chat.id)
    if not existing:
        raise ValueError(f"Chat with id {chat.id} not found")
    return await save_chat(chat)


async def delete_chat(chat_id: str) -> bool:
    with get_db() as session:
        user_id = get_current_user_db_id(session)
        count = session.query(ChatEntity).filter_by(user_id=user_id, chat_id=chat_id).delete()
        return count > 0


def _extract_title(chat: Chat) -> str:
    for m in chat.messages:
        if m.role == 'user':
            return m.content[:100] if isinstance(m.content, str) else ""
    return ""


def _save_chat_sync(chat: Chat) -> Chat:
    from storage.util import get_iso8601_timestamp
    chat.update_time = get_iso8601_timestamp()

    with get_db() as session:
        user_id = get_current_user_db_id(session)
        entity = session.query(ChatEntity).filter_by(user_id=user_id, chat_id=chat.id).first()
        content = json.dumps(chat.to_dict())
        title = _extract_title(chat)
        if entity:
            entity.json_content = content
            entity.title = title
        else:
            entity = ChatEntity(
                user_id=user_id,
                chat_id=chat.id,
                title=title,
                json_content=content,
            )
            session.add(entity)
        return chat


async def save_chat(chat: Chat) -> Chat:
    return _save_chat_sync(chat)
