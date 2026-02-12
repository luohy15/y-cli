"""Entity package - SQLAlchemy models and DTOs."""

from .base import Base, BaseEntity
from .bot_config import BotConfigEntity
from .prompt_config import PromptConfigEntity
from .chat import ChatEntity
from .dto import (
    BotConfig, DEFAULT_OPENROUTER_CONFIG,
    PromptConfig,
    Chat, Message, ContentPart,
)
from .preset import time_prompt, deep_research_prompt

__all__ = [
    'Base', 'BaseEntity',
    'BotConfigEntity', 'PromptConfigEntity', 'ChatEntity',
    'BotConfig', 'DEFAULT_OPENROUTER_CONFIG',
    'PromptConfig',
    'Chat', 'Message', 'ContentPart',
    'time_prompt', 'deep_research_prompt',
]
