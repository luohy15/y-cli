from sqlalchemy import Column, Integer, String, Text, UniqueConstraint
from .base import Base, BaseEntity


class ChatEntity(Base, BaseEntity):
    __tablename__ = "chat"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_prefix = Column(String, nullable=False)
    chat_id = Column(String, nullable=False)
    json_content = Column(Text, nullable=False)
    update_time = Column(Text)

    __table_args__ = (
        UniqueConstraint("user_prefix", "chat_id"),
    )
