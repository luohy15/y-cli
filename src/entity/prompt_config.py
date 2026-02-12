from sqlalchemy import Column, String, Text
from .base import Base, BaseEntity


class PromptConfigEntity(Base, BaseEntity):
    __tablename__ = "prompt_config"

    name = Column(String, primary_key=True)
    json_content = Column(Text, nullable=False)
